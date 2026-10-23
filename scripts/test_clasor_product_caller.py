"""Transport safety and setup submission/readback tests; no live model calls."""
import copy
from http.cookiejar import Cookie
from io import BytesIO
import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import Mock
from uuid import UUID
from clasor_agents.pa04.contract import ContractError
from clasor_agents.product_flow.caller import Caller
from clasor_agents.product_flow.flow import template
from scripts import test_clasor_product_flow as flow_fixtures


def uid(i): return str(UUID(int=i))


class Response(BytesIO):
    def __init__(self,value): super().__init__(json.dumps(value).encode())


class CallerTests(unittest.TestCase):
    def setUp(self):
        self.client=Caller('http://127.0.0.1:8080',uid(1))

    def test_dispatch_publication_and_decision_endpoints_are_unreachable(self):
        c=self.client;c.opener=Mock()
        paths=[c.team+'/instances/'+uid(2)+'/stages/'+uid(3)+'/'+action
               for action in ('run','retry','finalize','request_decision','edit_output')]
        paths += [c.team+'/flows/'+uid(2)+'/publish',c.team+'/requests/'+uid(2)+'/intake-decisions']
        for path in paths:
            with self.subTest(path=path),self.assertRaisesRegex(ContractError,'caller_operation_forbidden'):
                c._request('POST',path,{})
        c.opener.open.assert_not_called()

    def test_origin_id_and_redirect_boundaries(self):
        for origin in ['http://example.test','https://user:password@example.test','https://example.test/path']:
            with self.assertRaisesRegex(ContractError,'caller_invalid_origin'):Caller(origin,uid(1))
        with self.assertRaisesRegex(ContractError,'caller_invalid_id'):Caller('http://localhost:8080','../other')
        from clasor_agents.product_flow.caller import NoRedirect
        with self.assertRaisesRegex(ContractError,'caller_redirect_rejected'):
            NoRedirect().redirect_request(None,None,302,'',{},'https://other.test')

    def test_http_failure_details_and_credentials_are_not_in_error(self):
        for error,code in [(HTTPError('http://private',403,'fixture-secret',{},BytesIO(b'private-response')),'caller_http_403'),
                           (URLError('fixture-secret'),'caller_transport_failed')]:
            self.client.opener=Mock();self.client.opener.open.side_effect=error
            with self.assertRaisesRegex(ContractError,'^'+code+'$') as caught:self.client.options()
            self.assertNotIn('fixture-secret',str(caught.exception))

    def test_identity_is_read_from_profile_project_and_current_membership(self):
        c=self.client
        c._request=Mock(side_effect=[dict(id=uid(2)),dict(current_project=dict(id=uid(1),workspace_id=uid(3))),
            dict(project_id=uid(1),workspace_id=uid(3),account_id=uid(2),membership_id=uid(4))])
        self.assertEqual(c.actor(uid(2),uid(3)),dict(account_id=uid(2),membership_id=uid(4)))
        c._request=Mock(return_value=dict(id=uid(99)))
        with self.assertRaisesRegex(ContractError,'caller_actor_mismatch'):c.actor(uid(2),uid(3))

    def test_csrf_and_idempotency_are_sent_once_without_automatic_retry(self):
        c=self.client
        c.cookies.set_cookie(Cookie(0,'csrf_token','synthetic-csrf',None,False,'127.0.0.1',False,False,
            '/',True,False,None,True,None,None,{},False))
        c.opener=Mock();c.opener.open.return_value=Response(dict(id=uid(8)))
        key=uid(9);c._request('POST',c.team+'/flows',template(),key)
        request=c.opener.open.call_args.args[0]
        self.assertEqual(request.get_header('X-csrf-token'),'synthetic-csrf')
        self.assertEqual(request.get_header('Idempotency-key'),key)
        self.assertEqual(c.opener.open.call_count,1)

    def test_draft_readback_checks_content_revision_and_preserves_publication(self):
        c=self.client;body=template()
        flow=dict(id=uid(5),draft_stages=body['stages'],name=body['name'],description=body['description'],revision=1,current_version_id=None)
        c._request=Mock(side_effect=[dict(id=uid(5)),flow])
        self.assertEqual(c.save_draft(body,uid(9)),flow)
        bad=copy.deepcopy(flow);bad['current_version_id']=uid(6)
        c._request=Mock(side_effect=[dict(id=uid(5)),bad])
        with self.assertRaisesRegex(ContractError,'caller_draft_readback_mismatch'):c.save_draft(body,uid(9))

    def test_setup_posts_only_feedback_then_reads_and_verifies_effective_input(self):
        fixture=flow_fixtures.ProductFlowTests();fixture.setUp()
        # Native IDs and context are synthetic but canonical; no human decision is made.
        fixture.instance['id']=uid(50);fixture.package['provenance']['instance_id']=uid(50)
        fixture.stage.update(id=uid(51),instance_id=uid(50))
        packet=fixture.setup_packet();after=fixture.readback(packet)
        c=self.client;c.actor=Mock(return_value=fixture.actor)
        c.snapshot=Mock(side_effect=[(fixture.request,fixture.instance,fixture.stage),
                                    (fixture.request,fixture.instance,after)])
        c.published_binding=Mock(return_value=fixture.binding);c._request=Mock(return_value=after)
        result=c.apply_setup(packet,fixture.package,fixture.actor['account_id'],fixture.stage['workspace_id'])
        self.assertTrue(result['verified']);self.assertFalse(result['model_dispatched'])
        call=c._request.call_args.args
        self.assertEqual(call[0],'POST');self.assertTrue(call[1].endswith('/feedback'))
        self.assertEqual(call[3],packet['idempotency_key'])
        self.assertEqual(result['run_body'],dict(expected_revision=after['revision']))
        # An uncertain submission can be resolved by readback; no new POST or run.
        c.snapshot=Mock(return_value=(fixture.request,fixture.instance,after));c._request.reset_mock()
        c.apply_setup(packet,fixture.package,fixture.actor['account_id'],fixture.stage['workspace_id'])
        c._request.assert_not_called()
        after['preview_inputs']['analysis']='{}'
        with self.assertRaises(ContractError):
            c.apply_setup(packet,fixture.package,fixture.actor['account_id'],fixture.stage['workspace_id'])
