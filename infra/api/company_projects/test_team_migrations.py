"""Isolated schema-1 upgrades: repeat, race, drift and transactional DDL."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa

from company_projects import store, team_migrations as migrations
from company_projects.test_access import ProjectDatabaseFixture
from extensions.ext_database import db


class TeamMigrationTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.schema_name = 'kp01_' + uuid4().hex
        with db.engine.begin() as c:
            c.execute(sa.text(f'CREATE SCHEMA {self.schema_name}'))
        def cleanup():
            self.engine.dispose()
            with db.engine.begin() as c:
                c.execute(sa.text(f'DROP SCHEMA {self.schema_name} CASCADE'))
        self.engine = sa.create_engine(db.engine.url, connect_args={'options': f'-csearch_path={self.schema_name}'})
        self.addCleanup(cleanup)
        store.migrate(self.engine)
        with self.engine.begin() as c:
            c.execute(sa.text('CREATE TABLE tenant_account_joins (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, account_id uuid NOT NULL, role varchar(16), UNIQUE(tenant_id, account_id))'))
            self.ids = [str(uuid4()) for _ in range(4)]
            c.execute(sa.text('INSERT INTO tenant_account_joins VALUES (:id, :tenant, :account, :role)'),
                dict(id=self.ids[0], tenant=self.ids[1], account=self.ids[2], role='owner'))
            p = store.create_project(c, self.ids[3], self.ids[2], 'Existing synthetic project')
            c.execute(store.workspaces.insert().values(project_id=p['id'], workspace_id=self.ids[1]))
            store.assign(c, self.ids[3], p['id'], str(uuid4()))
            self.before = {name: list(c.execute(sa.text(f'SELECT * FROM {name}'))) for name in (
                'company_projects', 'company_project_apps', 'company_project_workspaces', 'tenant_account_joins')}

    def test_upgrade_is_additive_and_idempotent_with_empty_business_roles(self):
        migrations.migrate(self.engine)
        migrations.migrate(self.engine)
        with self.engine.connect() as c:
            for name, rows in self.before.items():
                self.assertEqual(list(c.execute(sa.text(f'SELECT * FROM {name}'))), rows)
            self.assertEqual(c.scalar(sa.text('SELECT version FROM company_project_schema')), 1)
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_migrations')), 1)
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_roles')), 0)

    def test_concurrent_runners_apply_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: migrations.migrate(self.engine), range(2)))
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_migrations')), 1)

    def test_failure_rolls_back_ddl_and_marker(self):
        with patch.object(migrations, 'MIGRATIONS', (('001_team_roles', migrations.ROLE_SCHEMA + 'INVALID SQL;'),)):
            with self.assertRaises(sa.exc.ProgrammingError):
                migrations.migrate(self.engine)
        with self.engine.connect() as c:
            self.assertNotIn('company_team_migrations', sa.inspect(c).get_table_names())
            self.assertNotIn('company_team_roles', sa.inspect(c).get_table_names())
        migrations.migrate(self.engine)

    def test_changed_checksum_and_unknown_version_are_rejected(self):
        migrations.migrate(self.engine)
        with self.engine.begin() as c:
            c.execute(sa.text("UPDATE company_team_migrations SET checksum = 'drift'"))
        with self.assertRaisesRegex(RuntimeError, 'drift'):
            migrations.migrate(self.engine)
        with self.engine.begin() as c:
            c.execute(sa.text('UPDATE company_team_migrations SET checksum = :checksum'), dict(checksum=migrations.checksum(migrations.ROLE_SCHEMA)))
            c.execute(sa.text("INSERT INTO company_team_migrations VALUES ('999_unknown', 'unknown', now())"))
        with self.assertRaisesRegex(RuntimeError, 'drift'):
            migrations.migrate(self.engine)
