import tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from platform_intelligence.engine import Engine
from platform_intelligence.legacy_radar import LegacyRadarAdapter,REVIEW_DAYS,STALE_DAYS

def page(published='2026-08-29',prefix=''):
    return f'''<!doctype html><html><body>
<span class="zh">最近更新</span> <b>{published}</b>
<section class="platform" id="x">
<h2>X ranking reference</h2>
<div class="card"><h3>Official source marker</h3><p>{prefix}Weights are summarized here without item-level citations.</p></div>
<div class="card actions"><h3>Creator playbook</h3><div><ul><li>Write a viral post now</li></ul></div><div>Another action</div></div>
<div class="card"><h3><span>创作者实操建议</span></h3><ul class="tips actions"><li>Do not turn this into an Agent action</li></ul></div>
</section>
<section class="platform" id="youtube"><h2>Youtube exclude</h2><p>Not X.</p></section>
</body></html>'''

class LegacyRadarTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.engine=Engine(Path(self.temp.name)/'data')
        self.html=Path(self.temp.name)/'index.html';self.html.write_text(page(),encoding='utf-8')
        self.adapter=LegacyRadarAdapter()
    def tearDown(self):self.engine.store.close();self.temp.cleanup()
    def test_x_import_is_reference_only(self):
        ref=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        self.assertEqual(ref['status'],'CURRENT_REFERENCE_ONLY')
        self.assertFalse(ref['action_eligible']);self.assertEqual(ref['authority'],'RESEARCH_ONLY')
        self.assertIn('Weights are summarized',ref['excerpt'])
        self.assertNotIn('Creator playbook',ref['excerpt']);self.assertNotIn('Youtube exclude',ref['excerpt'])
        self.assertNotIn('创作者实操建议',ref['excerpt']);self.assertNotIn('viral post',ref['excerpt'])
        self.assertNotIn('Agent action',ref['excerpt'])
        self.assertEqual(ref['source']['locator'].split('#')[-1],'x')
        self.assertEqual(len(self.engine.state()['actions']),0)
        src=self.engine.state()['sources']['local-algo-radar-x']
        self.assertEqual(src['kind'],'OBSERVATION');self.assertEqual(src['provenance'],'RESEARCH')
        self.assertEqual(self.engine.store.read(ref['snapshot_hash']),self.html.read_bytes())
    def test_quarterly_and_stale_thresholds(self):
        published=date(2026,10,4)
        self.html.write_text(page((published-timedelta(days=REVIEW_DAYS-1)).isoformat()),encoding='utf-8')
        self.assertEqual(self.adapter.collect(self.engine,self.html,today=published)['status'],'CURRENT_REFERENCE_ONLY')
        self.html.write_text(page((published-timedelta(days=REVIEW_DAYS)).isoformat()),encoding='utf-8')
        self.assertEqual(self.adapter.collect(self.engine,self.html,today=published)['status'],'REVIEW_DUE')
        self.html.write_text(page((published-timedelta(days=STALE_DAYS)).isoformat()),encoding='utf-8')
        self.assertEqual(self.adapter.collect(self.engine,self.html,today=published)['status'],'STALE')
    def test_future_date_stays_review_only(self):
        self.html.write_text(page('2026-10-05'),encoding='utf-8')
        ref=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        self.assertEqual(ref['status'],'INVALID_FUTURE_DATE');self.assertFalse(ref['action_eligible'])
    def test_missing_x_section_rejected(self):
        self.html.write_text('<b>2026-08-29</b><section id="youtube">Other</section>',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'SECTION_NOT_FOUND'):self.adapter.collect(self.engine,self.html)
    def test_bad_source_date_rejected(self):
        self.html.write_text(page('not-a-date'),encoding='utf-8')
        with self.assertRaises(ValueError):self.adapter.collect(self.engine,self.html)
    def test_file_cap_and_platform_scope(self):
        with self.assertRaisesRegex(ValueError,'TOO_LARGE'):
            self.html.write_bytes(b' '*(2*1024*1024+1));self.adapter.collect(self.engine,self.html)
        with self.assertRaisesRegex(ValueError,'X_ONLY'):self.adapter.collect(self.engine,self.html,platform='YouTube')
    def test_source_edit_requires_review_marker(self):
        self.html.write_text(page(),encoding='utf-8')
        with patch('platform_intelligence.legacy_radar._git_meta',return_value={'revision':'abc123','working_tree_changed':True,'repo':'local-reference'}):
            ref=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        self.assertEqual(ref['status'],'SOURCE_MODIFIED_REVIEW_REQUIRED')
        self.assertTrue(ref['source']['working_tree_changed'])
    def test_changed_revision_keeps_versioned_old_hash(self):
        first=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        old_hash=first['snapshot_hash']
        first_text_hash=first['text_hash']
        # Adapter policy can improve while the source bytes stay the same.
        self.engine.store.append('RADAR_REFERENCE',{**first,'text_hash':'f'*64,'excerpt':first['excerpt']+' legacy contaminated creator advice'})
        second=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        self.assertGreater(second['version'],first['version']);self.assertEqual(second['text_hash'],first_text_hash)
        self.html.write_text(page(prefix='Updated signal. '),encoding='utf-8')
        third=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        self.assertEqual(third['version'],second['version']+1);self.assertNotEqual(old_hash,third['snapshot_hash'])
        self.assertIn(old_hash,[s['hash'] for s in self.engine.state()['snapshots']['local-algo-radar-x']])
    def test_no_network_calls_and_no_actions(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network call')):
            ref=self.adapter.collect(self.engine,self.html,today=date(2026,10,4))
        self.engine.refresh()
        self.assertEqual(ref['kind'],'LEGACY_RESEARCH_REFERENCE')
        self.assertEqual(self.engine.envelope()['actions'],[])
        self.assertFalse(any(i['source_id']=='local-algo-radar-x' and i['kind']=='UNREVIEWED_SOURCE'
                             for i in self.engine.state()['incidents'].values()))

if __name__=='__main__':unittest.main()
