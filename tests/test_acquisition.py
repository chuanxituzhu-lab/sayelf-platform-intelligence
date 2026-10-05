import tempfile, unittest
from platform_intelligence.adapters import check_acquisition, AcquisitionRejected
from platform_intelligence.contracts import Source, Review, ICEBERG
from platform_intelligence.engine import Engine

class AcquisitionTests(unittest.TestCase):
    def test_known_challenge_titles_rejected(self):
        for title in ('Just a moment...', 'Access Denied', 'Attention Required! | Cloudflare',
                      'Verify you are human', '安全验证'):
            with self.subTest(title=title),self.assertRaises(AcquisitionRejected):
                check_acquisition(f'<title>{title}</title><p>nonempty challenge</p>'.encode(),'text/html')

    def test_policy_can_discuss_captcha_and_access_denied(self):
        check_acquisition(b'<title>Automation policy</title><p>Access denied and CAPTCHA requirements.</p>','text/html')
        check_acquisition(b'Access denied','text/plain')

    def test_failed_challenge_preserves_baseline_and_action(self):
        with tempfile.TemporaryDirectory() as root:
            e=Engine(root)
            try:
                source=Source('policy','X','POLICY','https://help.x.com/en/rules-and-policies/x-automation','Rules')
                e.register(source);snap=e.capture(source.id,b'Do not automate website.')
                layers={k:{'label':'FACT' if k=='FACT' else 'ACTION' if k in ('ACTION','MEASURE') else 'INFERENCE',
                           'text':'Do not automate website.' if k=='FACT' else 'Bounded analysis'} for k in ICEBERG}
                action=e.verify(Review(source.id,snap['hash'],'lines:1-1','Do not automate website.','test',
                                       'Avoid website automation','automation',layers,'AVOID','Count violations','POLICY',
                                       hard=True,effect='DENY',topic='automation'))
                class ChallengeAdapter:
                    platform='X'
                    def sources(self):return [source]
                    def fetch(self,s):return b'<title>Just a moment...</title><p>Challenge</p>','text/html'
                result=e.monitor(ChallengeAdapter(),force=True)
                state=e.state()
                self.assertEqual(result[0]['status'],'UNAVAILABLE')
                self.assertEqual(result[0]['error'],'AcquisitionRejected')
                self.assertEqual(len(state['snapshots'][source.id]),1)
                self.assertEqual(state['actions'][action['id']]['status'],'ACTIVE')
                self.assertFalse(any(i['kind']=='SOURCE_CHANGED' for i in state['incidents'].values()))
                self.assertTrue(any(i['kind']=='SOURCE_UNAVAILABLE' and i['status']=='OPEN' for i in state['incidents'].values()))
                self.assertEqual(e.replay()['state'],state)
                new=e.capture(source.id,b'<title>Automation policy</title><p>Changed official body.</p>','text/html')
                self.assertTrue(new['changed'])
                self.assertEqual(e.state()['actions'][action['id']]['status'],'REVIEW_REQUIRED')
            finally:e.store.close()

    def test_rejected_first_capture_does_not_create_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            e=Engine(root)
            try:
                e.register(Source('policy','X','POLICY','https://help.x.com/rules','Rules'))
                with self.assertRaises(AcquisitionRejected):
                    e.capture('policy',b'<title>Access denied</title><p>Not a policy</p>','text/html')
                self.assertNotIn('policy',e.state()['snapshots'])
            finally:e.store.close()
