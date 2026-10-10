"""Serialize native submissions so concurrent decisions cannot overwrite each other."""
import sqlalchemy as sa
from models.human_input import HumanInputForm
from libs.datetime_utils import naive_utc_now


def lock_active_form(session, form_id):
    # All native submission paths use this hook, including the original form page.
    form = session.scalar(sa.select(HumanInputForm).where(HumanInputForm.id == form_id).with_for_update())
    if form is None:
        return None
    from services.human_input_service import FormExpiredError, FormSubmittedError
    if form.status == 'submitted' or form.submitted_at is not None:
        raise FormSubmittedError(form.id)
    if form.status != 'waiting' or form.expiration_time <= naive_utc_now():
        raise FormExpiredError(form.id)
    return form
