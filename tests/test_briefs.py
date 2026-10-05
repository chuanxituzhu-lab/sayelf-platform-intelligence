import unittest
from platform_intelligence.briefs import build_brief


HASH='a'*64
NOW='2026-10-04T12:00:00+00:00'


def fixture_state(changed=False, unavailable=False):
    latest_hash='b'*64 if changed else HASH
    source={'id':'x-algorithm','platform':'X','kind':'ALGORITHM','provenance':'OFFICIAL',
            'classification':'Public','title':'X 官方算法说明','url':'https://docs.x.com/algorithm'}
    snapshot={'source_id':'x-algorithm','hash':latest_hash,'text_hash':'c'*64,'version':2 if changed else 1,
              'changed':changed,'previous_hash':HASH if changed else None,'diff_hash':'d'*64,'time':NOW}
    evidence={'source_id':'x-algorithm','url':source['url'],'locator':'README.md:27','hash':HASH,
              'text_hash':'c'*64,'snapshot_version':1,'captured_at':NOW,'reviewed_at':NOW}
    action={'id':'active-test','platform':'X','status':'ACTIVE','confidence':'VERIFIED_OFFICIAL',
            'action_class':'TEST','statement':'将互动计数比例视为待验证假设',
            'iceberg':{'BOUNDARY':{'text':'官方权重作用于预测概率，不等于原始互动数的倍数。'}},
            'evidence':[evidence]}
    result={'source_id':'x-algorithm','status':'UNAVAILABLE'} if unavailable else {
        'source_id':'x-algorithm','status':'CAPTURED','hash':latest_hash}
    return {
        'sources':{'x-algorithm':source},
        'snapshots':{'x-algorithm':[snapshot]},
        'runs':[{'time':NOW,'results':[result]}],
        'actions':{'active-test':action},
        'intelligence':{},'incidents':{},'deliveries':{},'legacy_references':{},
    }, action


class FakeEngine:
    def __init__(self,state,actions=None):
        self._state=state
        self._actions=actions if actions is not None else list(state['actions'].values())
    def envelope(self,platform='X'):
        return {'platform':'X','actions':self._actions}
    def state(self):
        return self._state


class BriefTests(unittest.TestCase):
    def test_brief_cites_only_current_official_active_evidence(self):
        state,action=fixture_state()
        action['evidence'].append({'source_id':'local-radar','url':'local://radar','locator':'#x',
                                   'hash':HASH,'snapshot_version':1,'reviewed_at':NOW})
        state['sources']['local-radar']={'id':'local-radar','platform':'X','kind':'OBSERVATION',
                                         'provenance':'RESEARCH','classification':'Internal',
                                         'title':'Algo Radar','url':'local://radar'}
        state['snapshots']['local-radar']=[{'hash':HASH,'version':1}]
        brief=build_brief(FakeEngine(state))
        self.assertIn('【推荐算法】',brief['text'])
        self.assertIn('将互动计数比例视为待验证假设',brief['text'])
        self.assertIn('https://docs.x.com/algorithm',brief['text'])
        self.assertIn('README.md:27',brief['text'])
        self.assertNotIn('local://radar',brief['text'])
        self.assertEqual(brief['checked_count'],1)

    def test_changed_source_is_pending_and_old_action_is_not_reused(self):
        state,action=fixture_state(changed=True)
        brief=build_brief(FakeEngine(state,[action]))
        self.assertEqual(brief['change_count'],1)
        self.assertIn('正文变化待审核',brief['text'])
        self.assertNotIn('将互动计数比例视为待验证假设',brief['text'])
        self.assertIn('语义尚未审核',brief['text'])

    def test_raw_file_version_change_is_not_called_a_text_change(self):
        state,_=fixture_state(changed=True)
        state['snapshots']['x-algorithm'][0]['changed']=False
        brief=build_brief(FakeEngine(state,[]))
        self.assertEqual(brief['change_count'],0)
        self.assertEqual(brief['source_update_count'],1)
        self.assertIn('原文件版本变化，提取正文未见变化',brief['text'])

    def test_unavailable_source_is_not_reported_unchanged(self):
        state,_=fixture_state(unavailable=True)
        brief=build_brief(FakeEngine(state,[]))
        self.assertEqual(brief['unavailable_count'],1)
        self.assertIn('相关内容不据此推断为未变化',brief['text'])

    def test_other_platform_and_unverified_action_are_excluded(self):
        state,action=fixture_state()
        other=dict(action,platform='YouTube')
        research=dict(action,confidence='RESEARCH')
        brief=build_brief(FakeEngine(state,[other,research]))
        self.assertEqual(brief['actions'],[])
        self.assertIn('当前没有可公开引用的有效审核结论',brief['text'])


if __name__=='__main__':
    unittest.main()
