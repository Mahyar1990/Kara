"""Validate native run evidence read by a trusted caller; never authorize a user."""
from .contract import ContractError,validate_attempt


def validate_native_result(result, expected_identity, envelope, expected_binding):
    """Identity comes from the server's saved attempt, not from model text.

    result includes id/created_by/workflow_id/status/finish_reason/outputs from
    native run and node records. expected_identity is an independent trusted
    snapshot of id/created_by/workflow_id. Kara still owns ACL and revision checks.
    """
    keys={'id','created_by','workflow_id'}
    if (type(result) is not dict or type(expected_identity) is not dict
            or set(expected_identity)!=keys or any(not isinstance(expected_identity[k],str)
                or not expected_identity[k] or result.get(k)!=expected_identity[k] for k in keys)):
        raise ContractError('native_identity_mismatch')
    return validate_attempt({k:result.get(k) for k in ('status','finish_reason','outputs')},envelope,expected_binding)
