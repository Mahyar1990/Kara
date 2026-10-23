"""Session/CSRF caller for Klassor preparation only. No run/decision/publication API."""
import base64
from http.cookiejar import CookieJar
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler)
from uuid import UUID
from clasor_agents.pa04.contract import ContractError, canonical
from .flow import planning_setup, planning_run, template


def uid(value):
    try:
        if str(UUID(value)) != value: raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise ContractError('caller_invalid_id') from None
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ContractError('caller_redirect_rejected')


class Caller:
    def __init__(self, origin, project_id, *, timeout=20):
        try:
            url=urlsplit(origin)
            _=url.port
        except ValueError:
            raise ContractError('caller_invalid_origin') from None
        if (url.scheme not in ('http','https') or not url.hostname or url.username or url.password
                or url.path not in ('','/') or url.query or url.fragment
                or (url.scheme=='http' and url.hostname not in ('localhost','127.0.0.1','::1'))):
            raise ContractError('caller_invalid_origin')
        self.origin=origin.rstrip('/')+'/console/api'
        self.project_id=uid(project_id)
        self.base='/company/projects/'+self.project_id
        self.team=self.base+'/team'
        self.timeout=timeout
        self.cookies=CookieJar()
        self.opener=build_opener(NoRedirect(),HTTPCookieProcessor(self.cookies))

    def _allowed(self, method, path):
        # Even accidental calls cannot reach model dispatch or human decisions.
        ident=r'[0-9a-f-]{36}'
        if method=='POST':
            return path in ('/login',self.base+'/enter',self.team+'/flows') or bool(re.fullmatch(
                re.escape(self.team)+r'/instances/'+ident+r'/stages/'+ident+r'/feedback',path))
        if method=='PUT':
            return bool(re.fullmatch(re.escape(self.team)+r'/flows/'+ident,path))
        if method!='GET': return False
        if path in ('/account/profile','/company/context',self.team+'/flows/options',self.team+'/agents',self.team+'/instances'):
            return True
        return bool(re.fullmatch(re.escape(self.team)+r'/(flows/'+ident+r'(/versions/'+ident+r')?|requests/'+ident+
            r'|members/'+ident+r'/roles|instances/'+ident+r'/stages/'+ident+r')',path))

    def _request(self, method, path, body=None, key=None):
        if not self._allowed(method,path): raise ContractError('caller_operation_forbidden')
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if key is not None: headers['Idempotency-Key']=uid(key)
        for cookie in self.cookies:
            if cookie.name in ('csrf_token','__Host-csrf_token'):
                headers['X-CSRF-Token']=cookie.value
        req=Request(self.origin+path,method=method,headers=headers,
                    data=canonical(body).encode() if body is not None else None)
        try:
            with self.opener.open(req,timeout=self.timeout) as response:
                raw=response.read(1048577)
                if len(raw)>1048576: raise ContractError('caller_response_too_large')
                return json.loads(raw)
        except ContractError:
            raise
        except HTTPError as error:
            status=error.code;error.close()
            raise ContractError('caller_http_'+str(status)) from None
        except (URLError,TimeoutError,OSError):
            raise ContractError('caller_transport_failed') from None
        except (ValueError,UnicodeError):
            raise ContractError('caller_invalid_response') from None

    def login(self, email, password):
        result=self._request('POST','/login',dict(email=email,
            password=base64.b64encode(password.encode()).decode(),remember_me=False))
        if result.get('result')!='success': raise ContractError('caller_login_failed')

    def enter(self, workspace_id):
        result=self._request('POST',self.base+'/enter',{})
        if result.get('workspace_id')!=uid(workspace_id): raise ContractError('caller_scope_mismatch')

    def actor(self, account_id, workspace_id):
        profile=self._request('GET','/account/profile')
        if profile.get('id')!=uid(account_id): raise ContractError('caller_actor_mismatch')
        context=self._request('GET','/company/context').get('current_project')
        if not context or context['id']!=self.project_id or context['workspace_id']!=uid(workspace_id):
            raise ContractError('caller_scope_mismatch')
        member=self._request('GET',self.team+'/members/'+account_id+'/roles')
        if member['account_id']!=account_id or member['workspace_id']!=workspace_id or member['project_id']!=self.project_id:
            raise ContractError('caller_scope_mismatch')
        return dict(account_id=account_id,membership_id=member['membership_id'])

    def options(self): return self._request('GET',self.team+'/flows/options')

    def snapshot(self, request_id, instance_id, stage_id):
        request=self._request('GET',self.team+'/requests/'+uid(request_id))
        instances=self._request('GET',self.team+'/instances')['data']
        found=[i for i in instances if i['id']==uid(instance_id)]
        if len(found)!=1: raise ContractError('caller_instance_missing')
        stage=self._request('GET',self.team+'/instances/'+instance_id+'/stages/'+uid(stage_id))
        return request,found[0],stage

    def published_binding(self, instance, step_key):
        version=self._request('GET',self.team+'/flows/'+uid(instance['flow_id'])+'/versions/'+uid(instance['flow_version_id']))
        if version['id']!=instance['flow_version_id'] or version['digest']!=instance['flow_digest']:
            raise ContractError('caller_flow_version_mismatch')
        found=[s for s in version['stage_bindings'] if s['key']==step_key]
        if len(found)!=1: raise ContractError('caller_binding_missing')
        return found[0]

    def save_draft(self, body, key, flow_id=None):
        # Supports an incomplete template too; never substitutes unrelated agents.
        if (set(body)!=set(template()) or [s['key'] for s in body['stages']]!=['analysis','planning']
                or any(s['inputs']!=t['inputs'] for s,t in zip(body['stages'],template()['stages']))):
            raise ContractError('caller_draft_mismatch')
        path=self.team+'/flows'+('/'+uid(flow_id) if flow_id else '')
        before=self._request('GET',path) if flow_id else None
        result=self._request('PUT' if flow_id else 'POST',path,body,key)
        flow=self._request('GET',self.team+'/flows/'+uid(result['id']))
        if (flow['draft_stages']!=body['stages'] or flow['name']!=body['name'].strip()
                or flow['description']!=body['description'].strip()
                or flow['revision']!=body['expected_revision']+(1 if flow_id else 0)
                or flow['current_version_id']!=(before['current_version_id'] if before else None)):
            raise ContractError('caller_draft_readback_mismatch')
        return flow

    def prepare_setup(self, package, account_id, workspace_id, instance_id, stage_id, receipt, repositories):
        actor=self.actor(account_id,workspace_id)
        request,instance,stage=self.snapshot(package['expected_binding']['request_id'],instance_id,stage_id)
        binding=self.published_binding(instance,'planning')
        return planning_setup(package,request,instance,stage,actor,binding,receipt,repositories)

    def apply_setup(self, setup, package, account_id, workspace_id):
        actor=self.actor(account_id,workspace_id)
        e=setup['expectation']
        request,instance,stage=self.snapshot(package['expected_binding']['request_id'],e['instance_id'],e['stage_id'])
        # Recover an uncertain prior submission by readback, without dispatch/retry.
        if stage['revision']!=e['revision']:
            fresh=planning_setup(package,request,instance,stage,actor,
                self.published_binding(instance,'planning'),setup['prepared_input']['binding']['finalization'],
                setup['prepared_input']['repositories'])
            if any(fresh[k]!=setup[k] for k in ('body','prepared_input','expected_input_sha256','expectation')):
                raise ContractError('caller_setup_changed')
            path=self.team+'/instances/'+e['instance_id']+'/stages/'+e['stage_id']+'/feedback'
            self._request('POST',path,setup['body'],setup['idempotency_key'])
            request,instance,stage=self.snapshot(package['expected_binding']['request_id'],e['instance_id'],e['stage_id'])
        body=planning_run(setup,package,request,instance,stage,actor)
        return dict(verified=True,stage_revision=body['expected_revision'],run_body=body,
                    run_idempotency_key=setup['run_idempotency_key'],model_dispatched=False)
