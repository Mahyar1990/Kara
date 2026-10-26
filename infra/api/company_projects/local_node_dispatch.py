"""Editor single-node preview uses the same authorized device execution ledger."""
from sqlalchemy.orm import Session,selectinload
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest,Forbidden
from extensions.ext_database import db
from company_projects import local_execution as local


def run_node(app,workflow,node_id,inputs,account):
    from company_projects.personal_model_runtime import require_account_execution
    require_account_execution(app.tenant_id,account)
    if node_id not in {n['id'] for n in workflow.graph_dict['nodes']}:raise BadRequest('گره وجود ندارد.')
    with Session(db.engine) as s,s.begin():
        job=local.enqueue(s,app,workflow,account,dict(inputs),preview=node_id,triggered_from='debugging')
    from company_projects.local_dispatch import relay
    relay(job,streaming=False)
    from models.workflow import WorkflowNodeExecutionModel
    with Session(db.engine) as s:
        result=s.scalar(sa.select(WorkflowNodeExecutionModel).where(WorkflowNodeExecutionModel.workflow_run_id==job['id'],WorkflowNodeExecutionModel.node_id==node_id).options(selectinload(WorkflowNodeExecutionModel.offload_data)))
        if result is None:raise BadRequest('Runner نتیجهٔ پیش‌نمایش را ثبت نکرد.')
        s.expunge(result);return result
