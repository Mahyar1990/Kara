"""Bounded HTTPS-only scoped API client, with loopback HTTP for local Kara."""
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError

class ApiError(Exception): pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def server_url(value):
    p=urlsplit(value)
    if p.username or p.password or p.query or p.fragment or p.path not in ('','/') or not p.hostname or any(c.isspace() for c in value): raise ValueError('Kara server must be an origin URL')
    if p.scheme!='https' and not (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1','::1')): raise ValueError('HTTPS is required outside loopback')
    return value.rstrip('/')

class Client:
    def __init__(self,server,secret=None): self.server=server_url(server); self.secret=secret
    def post(self,path,data=None):
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if self.secret: headers['Authorization']='Bearer '+self.secret
        request=Request(self.server+'/console/api/company/source-runner/'+path,data=json.dumps(data or {}).encode(),headers=headers,method='POST')
        try:
            # No environment proxy or redirect may receive the device secret.
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=25) as response:
                body=response.read(2097153)
                if len(body)>2097152: raise ApiError('Response limit exceeded')
                return json.loads(body)
        except HTTPError as exc: raise ApiError('Kara rejected request (HTTP '+str(exc.code)+')') from None
        except (URLError,TimeoutError,ValueError,OSError): raise ApiError('Kara connection failed') from None
