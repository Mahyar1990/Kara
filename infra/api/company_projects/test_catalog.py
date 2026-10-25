"""Native DSL import and dependency isolation, without model calls."""
import json
from uuid import uuid4
import sqlalchemy as sa
from werkzeug.exceptions import Conflict, NotFound
from company_projects.test_access import ProjectDatabaseFixture
from company_projects import catalog, store, runtime_models
from models.dataset import Dataset, Document, DatasetPermissionEnum
from models.model import App
from models.workflow import Workflow


class CatalogTests(ProjectDatabaseFixture):
    def setUp(self):
        super().setUp()
        self.editor.interface_language = 'fa-IR'
        self.editor.set_tenant_id_with_session(self.workspace_a.id, session=self.session)

    def test_native_import_creates_independent_unpublished_drafts_with_provenance(self):
        dataset = Dataset(tenant_id=self.workspace_a.id, name='Synthetic docs', created_by=self.editor.id,
            maintainer=self.editor.id, provider='vendor', permission=DatasetPermissionEnum.ALL_TEAM, indexing_technique='economy')
        self.session.add(dataset); self.session.flush()
        # Only native ready-document evidence is required; no real document is used.
        self.session.add(Document(tenant_id=self.workspace_a.id, dataset_id=dataset.id, position=1,
            data_source_type='upload_file', data_source_info='{}', name='Synthetic doc',
            batch='synthetic-batch', created_from='web', created_by=self.editor.id, indexing_status='completed', enabled=True, archived=False))
        self.session.flush()
        before = self.session.scalar(sa.select(sa.func.count()).select_from(App))
        ids = []
        for spec in catalog.templates():
            result = catalog.instantiate(self.session, self.a['id'], self.workspace_a.id, self.editor,
                    spec['id'], 'Synthetic ' + spec['id'], dataset.id)
            app = self.session.get(App, result['id'])
            self.assertEqual(app.tenant_id, self.workspace_a.id)
            self.assertFalse(app.enable_api); self.assertFalse(app.enable_site)
            self.assertIsNone(app.workflow_id)
            workflow = self.session.scalar(sa.select(Workflow).where(Workflow.app_id == app.id, Workflow.version == 'draft'))
            self.assertIsNotNone(workflow)
            graph = json.loads(workflow.graph)
            llm = next(n['data'] for n in graph['nodes'] if n['data']['type'] == 'llm')
            self.assertEqual(llm['model']['provider'], runtime_models.PROVIDER)
            self.assertIsNotNone(runtime_models.policy(graph))
            if spec['requires_knowledge']:
                retrieval = next(n['data'] for n in graph['nodes'] if n['data']['type'] == 'knowledge-retrieval')
                self.assertEqual(retrieval['dataset_ids'], [dataset.id])
            self.assertEqual(self.session.scalar(sa.select(store.template_copies.c.template_id).where(
                store.template_copies.c.app_id == app.id)), spec['id'])
            ids.append(app.id)
        self.assertEqual(len(set(ids)), 3)
        self.session.close(); self.transaction.rollback()
        with db_connection(self) as connection:
            self.assertEqual(connection.scalar(sa.select(sa.func.count()).select_from(App)), before)

    def test_foreign_or_unready_knowledge_still_blocks_creation(self):
        dataset = Dataset(tenant_id=self.workspace_b.id, name='Other docs', created_by=self.other.id)
        self.session.add(dataset); self.session.flush()
        with self.assertRaises(NotFound):
            catalog.ready_dataset(self.session, self.workspace_a.id, self.editor, dataset.id)
        dataset.tenant_id = self.workspace_a.id; dataset.permission = DatasetPermissionEnum.ALL_TEAM; self.session.flush()
        with self.assertRaises(Conflict):
            catalog.ready_dataset(self.session, self.workspace_a.id, self.editor, dataset.id)


def db_connection(test):
    from extensions.ext_database import db
    return db.engine.connect()
