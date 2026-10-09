"""Real database tests for persistent grouping and tenant boundaries."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('project_store', ROOT / 'infra/api/company_projects/store.py')
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.url = 'sqlite:///' + str(Path(self.directory.name) / 'test.db')
        self.engine = sa.create_engine(self.url)
        store.migrate(self.engine)
        self.tenant, self.other, self.user, self.app = [str(uuid4()) for _ in range(4)]
        with self.engine.begin() as conn:
            self.a = store.create_project(conn, self.tenant, self.user, 'پروژهٔ الف')
            self.b = store.create_project(conn, self.tenant, self.user, 'پروژهٔ ب')

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def test_restart_preserves_records_and_migration_is_idempotent(self):
        self.engine.dispose()
        self.engine = sa.create_engine(self.url)
        store.migrate(self.engine)
        with self.engine.connect() as conn:
            self.assertEqual(len(store.list_projects(conn, self.tenant)), 2)
            self.assertEqual(conn.scalar(sa.select(sa.func.count()).select_from(store.schema)), 1)

    def test_tenant_cannot_read_update_or_assign_another_project(self):
        with self.engine.begin() as conn:
            self.assertEqual(store.list_projects(conn, self.other), [])
            for action in (lambda: store.get_project(conn, self.other, self.a['id']),
                           lambda: store.update_project(conn, self.other, self.a['id'], 'نام'),
                           lambda: store.assign(conn, self.other, self.a['id'], self.app)):
                with self.assertRaises(store.MissingProject):
                    action()

    def test_unique_names_are_scoped_to_tenant(self):
        with self.engine.begin() as conn:
            store.create_project(conn, self.other, self.user, self.a['name'])
        with self.assertRaises(IntegrityError), self.engine.begin() as conn:
            store.create_project(conn, self.tenant, self.user, '  پروژهٔ    الف  ')

    def test_move_retains_exactly_one_owner_and_old_list_is_empty(self):
        with self.engine.begin() as conn:
            store.assign(conn, self.tenant, self.a['id'], self.app)
            store.assign(conn, self.tenant, self.a['id'], self.app)
            store.assign(conn, self.tenant, self.b['id'], self.app)
            self.assertEqual(list(conn.scalars(store.app_ids(self.a['id'], self.tenant))), [])
            self.assertEqual(list(conn.scalars(store.app_ids(self.b['id'], self.tenant))), [self.app])
            self.assertEqual(conn.scalar(sa.select(sa.func.count()).select_from(store.bindings)), 1)

    def test_assignment_participates_in_callers_transaction(self):
        with self.assertRaises(RuntimeError), self.engine.begin() as conn:
            store.assign(conn, self.tenant, self.a['id'], self.app)
            raise RuntimeError('synthetic creation failed')
        with self.engine.connect() as conn:
            self.assertEqual(list(conn.scalars(store.app_ids(self.a['id'], self.tenant))), [])

    def test_remove_from_wrong_project_does_not_remove_owner(self):
        with self.engine.begin() as conn:
            store.assign(conn, self.tenant, self.a['id'], self.app)
            store.unassign(conn, self.tenant, self.b['id'], self.app)
            self.assertEqual(list(conn.scalars(store.app_ids(self.a['id'], self.tenant))), [self.app])
            store.unassign(conn, self.tenant, self.a['id'], self.app)
            self.assertEqual(list(conn.scalars(store.app_ids(self.a['id'], self.tenant))), [])

    def test_invalid_names_descriptions_and_identifiers_are_rejected(self):
        for name, description in (('', ''), ('  ', ''), ('x' * 121, ''), ('نام', 'x' * 2001), (12, ''), ('نام', [])):
            with self.assertRaises(store.ProjectError):
                store.details(name, description)
        with self.assertRaises(store.ProjectError):
            store.uid('untrusted-not-uuid')

    def test_rename_retains_membership(self):
        with self.engine.begin() as conn:
            store.assign(conn, self.tenant, self.a['id'], self.app)
            result = store.update_project(conn, self.tenant, self.a['id'], 'نام تازه', 'توضیح')
            self.assertEqual(result['id'], self.a['id'])
            self.assertEqual(result['name'], 'نام تازه')
            self.assertEqual(list(conn.scalars(store.app_ids(self.a['id'], self.tenant))), [self.app])


if __name__ == '__main__':
    unittest.main()
