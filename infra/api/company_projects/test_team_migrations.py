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
            c.execute(sa.text('CREATE TABLE accounts (id uuid PRIMARY KEY)'))
            c.execute(sa.text('CREATE TABLE apps (id uuid PRIMARY KEY)'))
            c.execute(sa.text('CREATE TABLE workflows (id uuid PRIMARY KEY)'))
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
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_migrations')), len(migrations.MIGRATIONS))
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_roles')), 0)

    def test_concurrent_runners_apply_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: migrations.migrate(self.engine), range(2)))
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_migrations')), len(migrations.MIGRATIONS))

    def test_shared_app_upgrade_preserves_existing_agent_grants_and_attempts(self):
        with patch.object(migrations, 'MIGRATIONS', migrations.MIGRATIONS[:7]):
            migrations.migrate(self.engine)
        with self.engine.begin() as c:
            values = dict(id=str(uuid4()), app=str(uuid4()), workflow=str(uuid4()),
                project=c.scalar(sa.text('SELECT id FROM company_projects')),
                workspace=self.ids[1], actor=self.ids[2], member=self.ids[0], attempt=str(uuid4()), key=str(uuid4()))
            c.execute(sa.text('INSERT INTO apps VALUES (:app)'), values)
            c.execute(sa.text('INSERT INTO workflows VALUES (:workflow)'), values)
            insert_agent = sa.text('''INSERT INTO company_team_agents
                (id,project_id,workspace_id,app_id,workflow_id,name,description,workflow_digest,
                 input_contract,output_contract,created_by,created_at)
                VALUES (:id,:project,:workspace,:app,:workflow,'Synthetic agent','','digest','[]','[]',:actor,now())''')
            c.execute(insert_agent, values)
            c.execute(sa.text('''INSERT INTO company_team_agent_grants VALUES
                (:id,:project,:workspace,:actor,:member,'run',:actor,now())'''), values)
            c.execute(sa.text('''INSERT INTO company_team_agent_attempts
                (id,agent_id,project_id,workspace_id,actor_id,membership_id,workflow_id,inputs,
                 request_digest,correlation_id,status,created_at)
                VALUES (:attempt,:id,:project,:workspace,:actor,:member,:workflow,'{}','digest',:key,'pending',now())'''), values)
            before = {name: list(c.execute(sa.text(f'SELECT * FROM {name}'))) for name in (
                'company_team_agents', 'company_team_agent_grants', 'company_team_agent_attempts')}
        migrations.migrate(self.engine)
        migrations.migrate(self.engine)
        with self.engine.begin() as c:
            for name, rows in before.items():
                self.assertEqual(list(c.execute(sa.text(f'SELECT * FROM {name}'))), rows)
            c.execute(insert_agent, {**values, 'id': str(uuid4())})
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_agents WHERE app_id=:app'), values), 2)

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
            for name, sql in migrations.MIGRATIONS:
                c.execute(sa.text('UPDATE company_team_migrations SET checksum = :checksum WHERE migration_id = :name'),
                    dict(name=name, checksum=migrations.checksum(sql)))
            c.execute(sa.text("INSERT INTO company_team_migrations VALUES ('999_unknown', 'unknown', now())"))
        with self.assertRaisesRegex(RuntimeError, 'drift'):
            migrations.migrate(self.engine)

    def test_upgrade_from_kp01_preserves_roles_and_audit(self):
        with patch.object(migrations, 'MIGRATIONS', migrations.MIGRATIONS[:1]):
            migrations.migrate(self.engine)
        with self.engine.begin() as c:
            project_id = c.scalar(sa.text('SELECT id FROM company_projects'))
            c.execute(sa.text('INSERT INTO company_team_member_policies VALUES (:p,:w,:a,:m,2)'),
                dict(p=project_id, w=self.ids[1], a=self.ids[2], m=self.ids[0]))
            c.execute(sa.text("INSERT INTO company_team_roles VALUES (:p,:w,:a,'po',:a,now())"),
                dict(p=project_id, w=self.ids[1], a=self.ids[2]))
            before = list(c.execute(sa.text('SELECT * FROM company_team_roles')))
        migrations.migrate(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(list(c.execute(sa.text('SELECT * FROM company_team_roles'))), before)
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_agents')), 0)

    def test_failed_kp07_upgrade_keeps_kp05_schema_then_retries_cleanly(self):
        with patch.object(migrations, 'MIGRATIONS', migrations.MIGRATIONS[:5]):
            migrations.migrate(self.engine)
        broken = (*migrations.MIGRATIONS[:5], ('006_team_recovery', migrations.RECOVERY_SCHEMA + '\n-- kara-statement\nINVALID SQL;'))
        with patch.object(migrations, 'MIGRATIONS', broken), self.assertRaises(sa.exc.ProgrammingError):
            migrations.migrate(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_migrations')), 5)
            self.assertNotIn('assignment', {col['name'] for col in sa.inspect(c).get_columns('company_team_stages')})
            self.assertNotIn('company_team_cancellations', sa.inspect(c).get_table_names())
        migrations.migrate(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(sa.text('SELECT count(*) FROM company_team_migrations')), len(migrations.MIGRATIONS))
