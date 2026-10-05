import unittest
import tempfile
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from pathlib import Path
from platform_intelligence.engine import Engine
from platform_intelligence.contracts import Source,Review,ICEBERG,canonical,PLATFORMS
from platform_intelligence.adapters import XAdapter,official_url,adapter_registry
from platform_intelligence.integration import LocalRegistrySink,EngineCheckedConsumer
from platform_intelligence.store import digest

def iceberg(excerpt):
    return {k:{'label':'FACT' if k=='FACT' else 'ACTION' if k in ('ACTION','MEASURE') else 'INFERENCE',
               'text':excerpt if k=='FACT' else {'BOUNDARY':'不推出所有自动化都禁止；仅限本条规则。','MECHANISM':'规则约束可能影响风险，不能推断排序权重。'}.get(k,'有界分析 '+k)} for k in ICEBERG}

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.now=datetime(2026,10,4,tzinfo=timezone.utc)
        self.e=Engine(self.temp.name,lambda:self.now.isoformat())
        self.s=Source('policy','X','POLICY','https://help.x.com/en/rules-and-policies/x-automation','Rules')
        self.e.register(self.s); self.snap=self.e.capture('policy',b'Rules\nDo not automate website.\nBoundary.')
        self.r=Review('policy',self.snap['hash'],'lines:2-2','Do not automate website.','test-reviewer','避免网页脚本操作','automation',
                      iceberg('Do not automate website.'),'AVOID','违规动作次数=0','POLICY',hard=True,effect='DENY',topic='website_automation')
    def tearDown(self): self.e.store.close(); self.temp.cleanup()
    def test_golden_e2e(self):
        a=self.e.verify(self.r); self.assertEqual(a['status'],'ACTIVE')
        receipt=self.e.distribute(LocalRegistrySink(Path(self.temp.name)/'consumer'),'X-Agent')
        self.assertEqual(receipt['code'],0); self.assertEqual(self.e.envelope()['policy_gate'],'VALID_SCOPED')
        replay=self.e.replay(); self.assertEqual(replay['state'],self.e.state())
        self.assertEqual(replay['state_hash'],digest(canonical(self.e.state()).encode()))
        self.assertEqual(len(self.e.state()['intelligence'][a['derived_from'][0]]['benchmark']),len(PLATFORMS)-1)
    def test_locator_mismatch(self):
        with self.assertRaisesRegex(ValueError,'LOCATOR_MISMATCH'): self.e.verify(replace(self.r,locator='lines:1-1'))
    def test_missing_locator(self):
        with self.assertRaises(ValueError): self.e.verify(replace(self.r,locator=''))
    def test_hard_requires_official(self):
        self.e.register(replace(self.s,id='fake',url='https://example.com',provenance='OBSERVATION'))
        s=self.e.capture('fake',b'Do not automate website.')
        with self.assertRaises(ValueError): self.e.verify(replace(self.r,source_id='fake',snapshot_hash=s['hash'],locator='lines:1-1',provenance='OBSERVATION'))
    def test_provenance_firewall(self):
        with self.assertRaisesRegex(ValueError,'FIREWALL'): self.e.verify(replace(self.r,provenance='OBSERVATION'))
    def test_algorithm_cannot_hard(self):
        s=replace(self.s,id='algo',kind='ALGORITHM'); self.e.register(s); snap=self.e.capture('algo',b'Do not automate website.')
        with self.assertRaises(ValueError): self.e.verify(replace(self.r,source_id='algo',snapshot_hash=snap['hash'],locator='lines:1-1'))
    def test_ttl_fail_closed(self):
        a=self.e.verify(self.r); self.now+=timedelta(days=8)
        self.assertEqual(self.e.envelope()['actions'],[]); self.assertEqual(self.e.state()['actions'][a['id']]['status'],'STALE')
    def test_changed_version_pauses(self):
        a=self.e.verify(self.r); snap=self.e.capture('policy',b'Rules\nRule changed.\nBoundary.')
        self.assertTrue(snap['changed']); self.assertEqual(snap['version'],2)
        self.assertEqual(self.e.state()['actions'][a['id']]['status'],'REVIEW_REQUIRED')
        with self.assertRaises(ValueError): self.e.verify(self.r)
    def test_unchanged_no_new_version(self):
        s=self.e.capture('policy',b'Rules\nDo not automate website.\nBoundary.')
        self.assertFalse(s['changed']); self.assertEqual(s['version'],1)
    def test_snapshot_tamper(self):
        a=self.e.verify(self.r); (self.e.store.root/'snapshots'/self.snap['hash']).write_bytes(b'fake')
        self.assertEqual(self.e.envelope()['actions'],[])
        self.assertEqual(self.e.state()['actions'][a['id']]['status'],'QUARANTINED')
        with self.assertRaises(ValueError): self.e.replay()
    def test_audit_tamper(self):
        self.e.store.db.execute("UPDATE events SET payload='{}' WHERE seq=1"); self.e.store.db.commit()
        with self.assertRaisesRegex(ValueError,'AUDIT_TAMPERED'): self.e.replay()
    def test_priority_conflict(self):
        hard=self.e.verify(self.r)
        s=replace(self.s,id='observation',kind='OBSERVATION',provenance='OBSERVATION',url=''); self.e.register(s)
        snap=self.e.capture(s.id,b'Our observed signal.')
        ice=iceberg('Our observed signal.'); ice['FACT']['label']='OBSERVATION'
        r=replace(self.r,source_id=s.id,snapshot_hash=snap['hash'],locator='lines:1-1',excerpt='Our observed signal.',iceberg=ice,
                  provenance='OBSERVATION',hard=False,authority='OBSERVATION',action_class='TEST',effect='ALLOW',statement='测试网页自动化')
        soft=self.e.verify(r)
        self.assertEqual(soft['status'],'BLOCKED'); self.assertEqual(self.e.state()['actions'][hard['id']]['status'],'ACTIVE')
    def test_equal_priority_conflict(self):
        a=self.e.verify(self.r); b=self.e.verify(replace(self.r,statement='必须允许网页自动化',action_class='MUST',effect='ALLOW'))
        self.assertEqual(b['status'],'REVIEW_REQUIRED'); self.assertEqual(self.e.state()['actions'][a['id']]['status'],'REVIEW_REQUIRED')
    def test_counter_and_retire(self):
        a=self.e.verify(self.r); iid=a['derived_from'][0]
        self.e.challenge(a['id'],iid,'reviewer'); self.assertEqual(self.e.envelope()['actions'],[])
        self.e.evolve(a['id'],'RETIRE','reviewer'); self.assertEqual(self.e.state()['actions'][a['id']]['status'],'RETIRED')
    def test_counter_not_silently_dropped_on_review(self):
        a=self.e.verify(self.r); iid=a['derived_from'][0]
        self.e.challenge(a['id'],iid,self.r.reviewer)
        result=self.e.verify(self.r);self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertIn(iid,result['counter_evidence'])
        resolution={iid:{'decision':'NOT_APPLICABLE','rationale':'Synthetic test points to the identical supporting document, not a distinct counterexample.'}}
        result=self.e.verify(replace(self.r,counter_resolution=resolution))
        self.assertEqual(result['status'],'ACTIVE');self.assertIn(iid,result['counter_evidence']);self.assertIn(iid,result['counter_resolution'])
    def test_promote_requires_review(self):
        a=self.e.verify(self.r)
        with self.assertRaises(ValueError): self.e.evolve(a['id'],'PROMOTE','reviewer')
    def test_scanned_original_page(self):
        snap=self.e.capture('policy',b'%PDF-synthetic-test','application/pdf',transcription='Do not automate website.',pages={'1':'Do not automate website.'},origin_attestation='fixture-reviewer')
        a=self.e.verify(replace(self.r,snapshot_hash=snap['hash'],locator='page:1')); self.assertEqual(a['status'],'ACTIVE')
    def test_scan_missing_transcript(self):
        with self.assertRaises(ValueError): self.e.capture('policy',b'%PDF','application/pdf')
    def test_bad_page(self):
        snap=self.e.capture('policy',b'%PDF','application/pdf',transcription='Do not automate website.',pages={'1':'Do not automate website.'},origin_attestation='fixture')
        with self.assertRaises(ValueError): self.e.verify(replace(self.r,snapshot_hash=snap['hash'],locator='page:2'))
    def test_adapter_boundaries(self):
        self.assertEqual(sum(x['enabled'] for x in adapter_registry().values()),len(PLATFORMS))
        for u in ('http://help.x.com','https://help.x.com.evil.test','https://user@help.x.com','https://raw.githubusercontent.com/evil/repo/main/file'):
            self.assertFalse(official_url(u))
    def test_future_evidence(self):
        self.now-=timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'FUTURE_EVIDENCE'): self.e.verify(self.r)
    def test_missing_ack(self):
        self.e.verify(self.r)
        class Sink:
            def accept(self,e): return {'code':0,'data':{}}
        with self.assertRaises(ValueError): self.e.distribute(Sink(),'X-Agent')
    def test_state_driven_check(self):
        self.assertFalse(self.e.due('policy')); self.now+=timedelta(hours=25); self.assertTrue(self.e.due('policy'))
    def test_unavailable_not_success(self):
        class Bad:
            platform='X'
            def sources(inner): return [self.s]
            def fetch(inner,s): raise TimeoutError()
        result=self.e.monitor(Bad(),True); self.assertEqual(result[0]['status'],'UNAVAILABLE')
        self.assertTrue(any(i['kind']=='SOURCE_UNAVAILABLE' for i in self.e.state()['incidents'].values()))
    def test_replay_cutoff(self):
        before=len(self.e.store.events()); self.e.verify(self.r)
        self.assertFalse(self.e.replay(before)['state']['actions'])
    def test_iceberg_missing_boundary(self):
        ice=iceberg(self.r.excerpt); del ice['BOUNDARY']
        with self.assertRaises(ValueError): self.e.verify(replace(self.r,iceberg=ice))
    def test_source_identity_immutable(self):
        with self.assertRaises(ValueError): self.e.register(replace(self.s,url='https://docs.x.com/'))
    def test_community_cannot_promote_research_authority(self):
        s=replace(self.s,id='community',kind='OBSERVATION',provenance='COMMUNITY',url='');self.e.register(s)
        snap=self.e.capture(s.id,b'Community signal.');ice=iceberg('Community signal.');ice['FACT']['label']='OBSERVATION'
        with self.assertRaisesRegex(ValueError,'FIREWALL_AUTHORITY'):
            self.e.verify(replace(self.r,source_id=s.id,snapshot_hash=snap['hash'],locator='lines:1-1',excerpt='Community signal.',
                iceberg=ice,provenance='COMMUNITY',hard=False,authority='RESEARCH',action_class='TEST'))
    def test_retirement_not_revived_by_ordinary_review(self):
        a=self.e.verify(self.r);self.e.evolve(a['id'],'RETIRE',self.r.reviewer)
        with self.assertRaisesRegex(ValueError,'EXPLICIT_PROMOTION'):self.e.verify(self.r)
        self.e.evolve(a['id'],'PROMOTE',self.r.reviewer,self.r)
        self.assertEqual(self.e.state()['actions'][a['id']]['status'],'ACTIVE')
    def test_retired_replaced_constraint_does_not_deadlock(self):
        a=self.e.verify(self.r);self.e.evolve(a['id'],'RETIRE',self.r.reviewer)
        self.assertEqual(self.e.envelope()['policy_gate'],'BLOCKED')
        self.e.verify(replace(self.r,statement='经新审核的同主题约束'))
        self.assertEqual(self.e.envelope()['policy_gate'],'VALID_SCOPED')
    def test_ops_health_and_recovery(self):
        class Sink:
            def __init__(inner):inner.events=[]
            def accept(inner,event):
                inner.events.append(event)
                return {'code':0,'data':{'event_hash':digest(canonical(event).encode())}}
        sink=Sink();self.e.verify(self.r);self.e.capture('policy',b'Rules changed.')
        self.e.ops(sink);self.assertTrue(any(i['kind']=='HEALTH' for i in sink.events))
        self.e.resolve_incidents('SOURCE_CHANGED','policy');self.e.ops(sink)
        self.assertTrue(any(i['kind']=='SOURCE_CHANGED' and i['health']=='RECOVERED' and not i['requires_attention'] for i in sink.events))
    def test_consumer_revocation(self):
        self.e.verify(self.r); envelope=self.e.envelope(); consumer=EngineCheckedConsumer(self.e)
        self.assertEqual(consumer.consume(envelope)['code'],0)
        self.e.capture('policy',b'Rules changed.')
        with self.assertRaisesRegex(ValueError,'REVOKED'): consumer.consume(envelope)
    def test_consumer_expired(self):
        self.e.verify(self.r); env=self.e.envelope(); self.now+=timedelta(days=8)
        with self.assertRaisesRegex(ValueError,'EXPIRED'): EngineCheckedConsumer(self.e).consume(env)
    def test_monitor_diff_reverify_distribute_replay(self):
        self.e.verify(self.r)
        class Changed:
            platform='X'
            def sources(inner): return [self.s]
            def fetch(inner,s): return b'Rules\nDo not automate website.\nNew boundary.','text/plain'
        self.e.monitor(Changed(),True); snap=self.e.state()['snapshots']['policy'][-1]
        self.assertEqual(self.e.envelope()['policy_gate'],'BLOCKED')
        a=self.e.verify(replace(self.r,snapshot_hash=snap['hash']))
        self.assertEqual(a['status'],'ACTIVE'); self.assertTrue(self.e.store.read(snap['diff_hash']))
        self.e.distribute(LocalRegistrySink(Path(self.temp.name)/'receiver'),'fixture-agent')
        self.assertEqual(self.e.replay()['state'],self.e.state())
    def test_demote_and_verified_promote(self):
        a=self.e.verify(self.r); self.e.evolve(a['id'],'DEMOTE',self.r.reviewer)
        self.assertEqual(self.e.envelope()['actions'],[])
        self.e.evolve(a['id'],'PROMOTE',self.r.reviewer,self.r)
        self.assertEqual(self.e.state()['actions'][a['id']]['status'],'ACTIVE')
    def test_promotion_mismatch_no_side_effect(self):
        a=self.e.verify(self.r); before=len(self.e.store.events())
        with self.assertRaises(ValueError): self.e.evolve(a['id'],'PROMOTE',self.r.reviewer,replace(self.r,statement='different'))
        self.assertEqual(len(self.e.store.events()),before)
    def test_observation_cannot_become_fact(self):
        s=replace(self.s,id='observed',kind='OBSERVATION',provenance='OBSERVATION',url=''); self.e.register(s)
        snap=self.e.capture(s.id,b'Observed signal.')
        with self.assertRaises(ValueError):
            self.e.verify(replace(self.r,source_id=s.id,snapshot_hash=snap['hash'],locator='lines:1-1',excerpt='Observed signal.',
                iceberg=iceberg('Observed signal.'),provenance='OBSERVATION',hard=False,authority='OBSERVATION',action_class='TEST'))

if __name__=='__main__': unittest.main()
