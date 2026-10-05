import tempfile, unittest
from unittest.mock import patch
from platform_intelligence.contracts import PLATFORMS,Source,Review,ICEBERG
from platform_intelligence.adapters import get_adapter,official_url,SafeRedirect,AcquisitionRejected
from platform_intelligence.engine import Engine
from platform_intelligence.briefs import build_brief
from platform_intelligence.integration import EngineCheckedConsumer

class MultiPlatformTests(unittest.TestCase):
 def test_all_platforms_have_scoped_official_source_adapters(self):
  ids=[]
  for platform in PLATFORMS:
   adapter=get_adapter(platform);self.assertEqual(adapter.platform,platform)
   sources=adapter.sources();self.assertGreaterEqual(len(sources),2)
   for source in sources:
    self.assertEqual(source.platform,platform);self.assertTrue(official_url(source.url,platform));ids.append(source.id)
  self.assertEqual(len(ids),len(set(ids)))

 def test_domain_and_product_scope_cannot_cross_platform(self):
  self.assertFalse(official_url('https://support.google.com/mail/answer/9288567?hl=en','YouTube'))
  self.assertFalse(official_url('https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Access_Overview.html','视频号'))
  self.assertFalse(official_url('https://developers.facebook.com/docs/graph-api/','Instagram'))
  self.assertFalse(official_url('https://help.x.com/rules','YouTube'))
  self.assertFalse(official_url('https://redditinc.com.evil.test/policies/reddit-rules','Reddit'))
  self.assertFalse(official_url('http://redditinc.com/policies/reddit-rules','Reddit'))
  with self.assertRaisesRegex(ValueError,'REDIRECT_BLOCKED'):
   SafeRedirect('YouTube').redirect_request(None,None,302,'',{},'https://help.x.com/rules')

 def test_policy_conflict_and_brief_are_platform_isolated(self):
  with tempfile.TemporaryDirectory() as root:
   e=Engine(root)
   try:
    for platform,sid,url,effect in [('X','x','https://help.x.com/rules','DENY'),
                                   ('YouTube','yt','https://support.google.com/youtube/answer/9288567?hl=en','ALLOW')]:
     source=Source(sid,platform,'POLICY',url,platform+' Policy')
     e.register(source);snap=e.capture(sid,b'Official fixture rule')
     layers={k:{'label':'FACT' if k=='FACT' else 'ACTION' if k in ('ACTION','MEASURE') else 'INFERENCE',
                'text':'Official fixture rule' if k=='FACT' else 'Bounded fixture'} for k in ICEBERG}
     e.verify(Review(sid,snap['hash'],'lines:1-1','Official fixture rule','fixture',platform+' independent rule','capability',
                     layers,'AVOID' if effect=='DENY' else 'MUST','measure','POLICY',hard=True,effect=effect,topic='same-topic'))
    self.assertTrue(all(a['status']=='ACTIVE' for a in e.state()['actions'].values()))
    self.assertEqual(e.envelope('YouTube')['policy_gate'],'VALID_SCOPED')
    self.assertEqual({a['platform'] for a in e.envelope('YouTube')['actions']},{'YouTube'})
    text=build_brief(e,'YouTube')['text'];self.assertIn('YouTube independent rule',text);self.assertNotIn('X independent rule',text)
    EngineCheckedConsumer(e).consume(e.envelope('YouTube'))
    self.assertEqual(e.replay()['state'],e.state())
   finally:e.store.close()

 def test_first_capture_is_not_an_active_rule_and_runs_are_scoped(self):
  with tempfile.TemporaryDirectory() as root:
   e=Engine(root)
   try:
    for platform in ('YouTube','Reddit'):
     original=get_adapter(platform);source=original.sources()[0]
     class Fixture:
      def sources(self):return [source]
      def fetch(self,s):return ('Official '+platform+' fixture body').encode(),'text/plain'
     adapter=Fixture();adapter.platform=platform;e.monitor(adapter,True)
    brief=build_brief(e,'YouTube')
    self.assertEqual(brief['checked_count'],1);self.assertEqual(brief['actions'],[])
    self.assertNotIn('Reddit',brief['text'])
    self.assertEqual(e.envelope('YouTube')['policy_gate'],'BLOCKED')
    self.assertEqual(e.state()['sources']['reddit-policy']['platform'],'Reddit')
    self.assertTrue(all(i['blast_radius']['platforms']==[i['platform']] for i in e.state()['incidents'].values()))
   finally:e.store.close()

 def test_shell_response_is_rejected_before_snapshot(self):
  adapter=get_adapter('小红书');source=adapter.sources()[0]
  class Response:
   headers={'Content-Type':'text/html'}
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return '<title>小红书</title><p>扫码登录</p>'.encode()
  class Opener:
   def open(self,*args,**kwargs):return Response()
  with patch('platform_intelligence.adapters.build_opener',return_value=Opener()),self.assertRaises(AcquisitionRejected):
   adapter.fetch(source)

 def test_ops_all_platforms_health_has_independent_blast_radius(self):
  with tempfile.TemporaryDirectory() as root:
   e=Engine(root)
   try:
    for platform in PLATFORMS:
     for source in get_adapter(platform).sources():e.register(source)
    from platform_intelligence.contracts import canonical
    from platform_intelligence.store import digest
    events=[]
    class Sink:
     def accept(self,event):events.append(event);return {'code':0,'data':{'event_hash':digest(canonical(event).encode())}}
    e.ops(Sink())
    self.assertEqual({i['platform'] for i in events if i['kind']=='HEALTH'},set(PLATFORMS))
    self.assertTrue(all(i['blast_radius']['platforms']==[i['platform']] for i in events))
   finally:e.store.close()
