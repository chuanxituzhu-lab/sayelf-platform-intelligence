from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
import difflib
import uuid
from .contracts import (Source, Review, STAGES, PRIORITY, PLATFORMS, canonical, utcnow, parse_time, validate_review)
from .adapters import extract, official_url, CapabilityBenchmark, check_acquisition
from .store import Store, digest

class Engine:
    def __init__(self, root, clock=utcnow):
        self.store=Store(root); self.clock=clock
    def state(self): return self.store.projection()
    def register(self, source):
        if source.platform not in PLATFORMS or source.kind not in ('POLICY','API','ALGORITHM','PRODUCT','OBSERVATION') or source.ttl_hours <= 0:
            raise ValueError('SOURCE_SCOPE_INVALID')
        if source.provenance not in ('OFFICIAL','RESEARCH','OBSERVATION','HYPOTHESIS','COMMUNITY'):
            raise ValueError('SOURCE_PROVENANCE_INVALID')
        old=self.state()['sources'].get(source.id)
        record=asdict(source)
        if old and old != record: raise ValueError('SOURCE_ID_IMMUTABLE')
        if not old: self.store.append('SOURCE',record,self.clock())
    def capture(self, source_id, raw, media='text/plain', transcription=None, pages=None, origin_attestation=None, acquisition='DIRECT_DOCUMENT_GET'):
        source=self.state()['sources'][source_id]
        if len(raw) > 8*1024*1024: raise ValueError('SOURCE_TOO_LARGE')
        scan = not (media.startswith('text/') or media in ('application/json',))
        if scan and (not transcription or not pages or not origin_attestation):
            raise ValueError('SCAN_REQUIRES_REVIEWED_TRANSCRIPT_PAGES_AND_ORIGIN')
        check_acquisition(raw,media)
        text=transcription if scan else extract(raw,media)
        if not text.strip(): raise ValueError('EMPTY_SOURCE')
        h=self.store.blob(raw); th=self.store.blob(text.encode())
        history=self.state()['snapshots'].get(source_id,[]); previous=history[-1] if history else None
        changed=previous is not None and previous['text_hash'] != th
        diff=''.join(difflib.unified_diff(self.store.read(previous['text_hash']).decode().splitlines(True), text.splitlines(True),fromfile=previous['hash'],tofile=h)) if changed else ''
        version=(previous['version']+1 if previous['hash'] != h else previous['version']) if previous else 1
        record={'source_id':source_id,'hash':h,'text_hash':th,'url':source['url'],'media':media,'time':self.clock(),
                'version':version,'previous_hash':previous['hash'] if previous else None,'diff_hash':self.store.blob(diff.encode()),
                'changed':changed,'pages':pages or {},'origin_attestation':origin_attestation,'scan':scan,'acquisition':acquisition}
        self.store.append('SNAPSHOT',record,self.clock())
        if changed or (previous and previous['hash'] != h):
            for a in self.state()['actions'].values():
                if source_id in a['source_ids'] and a['status'] not in ('RETIRED',):
                    self._status(a,'REVIEW_REQUIRED','SOURCE_VERSION_CHANGED')
            self.incident('SOURCE_CHANGED', source_id, 'HIGH' if source['kind'] in ('POLICY','API') else 'MEDIUM')
        self.resolve_incidents('SOURCE_UNAVAILABLE',source_id)
        return record
    def monitor(self, adapter, force=False):
        results=[]
        for source in adapter.sources():
            if source.platform!=adapter.platform:raise ValueError('ADAPTER_PLATFORM_MISMATCH')
            self.register(source)
            if not force and not self.due(source.id): continue
            try:
                raw,media=adapter.fetch(source); snap=self.capture(source.id,raw,media)
                results.append({'source_id':source.id,'status':'CAPTURED','hash':snap['hash']})
            except Exception as exc:
                # Do not leak source/server responses into logs.
                self.incident('SOURCE_UNAVAILABLE',source.id,'HIGH',error=type(exc).__name__)
                results.append({'source_id':source.id,'status':'UNAVAILABLE','error':type(exc).__name__})
        self.refresh()
        self.store.append('RUN',{'id':str(uuid.uuid4()),'platform':adapter.platform,'time':self.clock(),'results':results,'stages':['Monitor','Evidence','Diff','Version']},self.clock())
        return results
    def due(self, source_id):
        return parse_time(self.clock()) >= parse_time(self.next_check(source_id))
    def next_check(self, source_id):
        state=self.state(); s=state['sources'][source_id]; history=state['snapshots'].get(source_id,[])
        failures=[i for i in state['incidents'].values() if i['source_id']==source_id and i['kind']=='SOURCE_UNAVAILABLE' and i['status']=='OPEN']
        if failures:
            last=failures[-1]; return (parse_time(last['time'])+timedelta(hours=min(24,2**min(last.get('attempts',1),4)))).isoformat()
        if not history: return self.clock()
        hours=min(s['ttl_hours'],24 if s['importance']=='HIGH' or history[-1]['changed'] else 168)
        return (parse_time(history[-1]['time'])+timedelta(hours=hours)).isoformat()
    def incident(self, kind, source_id, severity, error=None):
        state=self.state(); affected=[a['id'] for a in state['actions'].values() if source_id in a['source_ids']]
        platform=state['sources'].get(source_id,{}).get('platform','X')
        consumers=sorted({c for d in state['deliveries'].values() for c in [d['consumer']] if set(d.get('action_ids',[])) & set(affected)})
        key=digest(canonical([kind,source_id]).encode())[:24]; old=state['incidents'].get(key)
        if old and old['status']=='OPEN' and kind!='SOURCE_UNAVAILABLE' and old['blast_radius']=={'actions':affected,'consumers':consumers,'platforms':[platform]} and old['error']==error:
            return old
        event={'id':key,'kind':kind,'source_id':source_id,'platform':platform,'severity':severity,'status':'OPEN','time':self.clock(),
               'attempts':old.get('attempts',0)+1 if old and old['status']=='OPEN' else 1,
               'blast_radius':{'actions':affected,'consumers':consumers,'platforms':[platform]},'error':error,'next_check':None}
        self.store.append('INCIDENT',event,self.clock()); return event
    def resolve_incidents(self, kind, source_id):
        for i in self.state()['incidents'].values():
            if i['kind']==kind and i['source_id']==source_id and i['status']=='OPEN':
                self.store.append('INCIDENT',{**i,'status':'RESOLVED','resolved_at':self.clock()},self.clock())
    def verify(self, review, revive=False):
        r=validate_review(review); state=self.state(); s=state['sources'][r['source_id']]
        history=state['snapshots'].get(s['id'],[])
        if not history or history[-1]['hash'] != r['snapshot_hash']: raise ValueError('LATEST_SNAPSHOT_REQUIRED')
        snap=history[-1]; self.store.read(snap['hash']); text=self.store.read(snap['text_hash']).decode()
        if parse_time(snap['time'])+timedelta(hours=s['ttl_hours']) <= parse_time(self.clock()): raise ValueError('EVIDENCE_EXPIRED')
        if parse_time(snap['time']) > parse_time(self.clock()): raise ValueError('FUTURE_EVIDENCE')
        if r['excerpt'] not in text: raise ValueError('EXCERPT_NOT_IN_SNAPSHOT')
        # Locator is deterministic line interval, or verified page in imported original.
        if r['locator'].startswith('lines:'):
            start,end=map(int,r['locator'][6:].split('-'))
            lines=text.splitlines()
            if start < 1 or end < start or end > len(lines) or r['excerpt'] not in '\n'.join(lines[start-1:end]): raise ValueError('LOCATOR_MISMATCH')
        elif r['locator'].startswith('page:') and snap['scan']:
            page=r['locator'][5:]
            if page not in snap['pages'] or r['excerpt'] not in snap['pages'][page] or snap['pages'][page] not in text: raise ValueError('PAGE_MISMATCH')
        else: raise ValueError('LOCATOR_REQUIRED')
        official=s['provenance']=='OFFICIAL' and r['provenance']=='OFFICIAL' and official_url(s['url'],s['platform'])
        if r['provenance'] != s['provenance']: raise ValueError('LEARNING_FIREWALL_PROVENANCE')
        if r['hard'] and (s['kind'] not in ('POLICY','API') or not official or r['authority'] != s['kind']):
            raise ValueError('OFFICIAL_LOCATABLE_POLICY_API_REQUIRED')
        if r['authority'] in ('POLICY','API','OFFICIAL_ALGORITHM') and not official: raise ValueError('AUTHORITY_PROMOTION_BLOCKED')
        if not official and r['authority'] != {'RESEARCH':'RESEARCH','OBSERVATION':'OBSERVATION','HYPOTHESIS':'OBSERVATION','COMMUNITY':'COMMUNITY'}.get(r['provenance']):
            raise ValueError('LEARNING_FIREWALL_AUTHORITY')
        expected={'POLICY':'POLICY','API':'API','PRODUCT':'PRODUCT','ALGORITHM':'OFFICIAL_ALGORITHM'}
        if official and r['authority'] != expected.get(s['kind']): raise ValueError('AUTHORITY_KIND_MISMATCH')
        if s['kind']=='ALGORITHM' and r['hard']: raise ValueError('ALGORITHM_NOT_HARD')
        if r['provenance']!='OFFICIAL' and r['iceberg']['FACT']['label']=='FACT': raise ValueError('NONOFFICIAL_NOT_OFFICIAL_FACT')
        if r['iceberg']['FACT']['label']=='FACT' and r['iceberg']['FACT']['text'] != r['excerpt']: raise ValueError('FACT_MUST_MATCH_EVIDENCE')
        if r['iceberg']['MECHANISM']['label']=='FACT': raise ValueError('MECHANISM_REQUIRES_BOUNDED_INFERENCE')
        if r['action_class'] in ('MUST','AVOID') and not r['hard']: raise ValueError('HARD_EVIDENCE_CLASS_REQUIRED')
        if r['provenance'] in ('OBSERVATION','HYPOTHESIS','COMMUNITY') and r['action_class']!='TEST': raise ValueError('LEARNING_FIREWALL_TEST_ONLY')
        aid=digest(canonical([s['platform'],r['topic'],r['statement']]).encode())[:24]
        old=state['actions'].get(aid)
        if old and old['status']=='RETIRED' and not revive: raise ValueError('RETIRED_REQUIRES_EXPLICIT_PROMOTION')
        counters=sorted(set(r['counter_evidence']+(old['counter_evidence'] if old else [])))
        resolutions={**(old.get('counter_resolution',{}) if old else {}),**r['counter_resolution']}
        for eid in counters:
            if eid not in state['intelligence']: raise ValueError('UNKNOWN_COUNTER_EVIDENCE')
        if any(eid not in counters for eid in resolutions): raise ValueError('RESOLUTION_WITHOUT_COUNTER')
        iid=digest(canonical([s['id'],snap['hash'],r,counters,resolutions]).encode())[:24]
        evidence={'source_id':s['id'],'url':s['url'],'hash':snap['hash'],'text_hash':snap['text_hash'],'locator':r['locator'],
                  'excerpt':r['excerpt'],'snapshot_version':snap['version'],'captured_at':snap['time'],'reviewed_at':self.clock(),'reviewer':r['reviewer'],
                  'acquisition':snap.get('acquisition','DIRECT_DOCUMENT_GET'),'origin_attestation':snap['origin_attestation']}
        intel={'id':iid,'platform':s['platform'],'kind':s['kind'],'capability':r['capability'],'provenance':r['provenance'],
               'iceberg':r['iceberg'],'evidence':[evidence],'counter_evidence':counters,'counter_resolution':resolutions,'version':snap['version'],'status':'VERIFIED',
               'impact':{'risk':r['risk'],'topic':r['topic']},'benchmark':CapabilityBenchmark().compare({**r,'platform':s['platform']})}
        self.store.append('INTELLIGENCE',intel,self.clock())
        expires=min(parse_time(self.clock())+timedelta(hours=r['ttl_hours']),parse_time(snap['time'])+timedelta(hours=s['ttl_hours']))
        action={'id':aid,'action_id':aid,'platform':s['platform'],'capability':r['capability'],'topic':r['topic'],'statement':r['statement'],
                'action_class':r['action_class'],'authority':r['authority'],'hard':r['hard'],'effect':r['effect'],
                'derived_from':[iid],'support_evidence':sorted(set([iid]+(old['support_evidence'] if old else []))),
                'counter_evidence':counters,'counter_resolution':resolutions,'source_ids':[s['id']],
                'iceberg':r['iceberg'],'evidence':[evidence],
                'fact':[x['text'] for x in r['iceberg'].values() if x['label']=='FACT'],
                'inference':[x['text'] for x in r['iceberg'].values() if x['label']=='INFERENCE'],
                'hypothesis':[x['text'] for x in r['iceberg'].values() if x['label']=='HYPOTHESIS'],
                'boundary':[r['iceberg']['BOUNDARY']['text']],
                'measure':r['measure'],'rationale':r['iceberg']['BOUNDARY']['text'],
                'confidence':'VERIFIED_OFFICIAL' if official else 'BOUNDED','risk':r['risk'],'status':'REVIEW_REQUIRED' if any(eid not in resolutions for eid in counters) else 'ACTIVE',
                'valid_from':self.clock(),'last_verified':self.clock(),'next_review':expires.isoformat(),'ttl':r['ttl_hours']*3600,'ttl_hours':r['ttl_hours'],
                'expires_at':expires.isoformat(),'version':old['version']+1 if old else 1,'reason':'REVIEWED_EVIDENCE'}
        self.store.append('ACTION',action,self.clock())
        self.resolve_incidents('SOURCE_CHANGED',s['id']); self.resolve_incidents('UNREVIEWED_SOURCE',s['id'])
        self.refresh(); self.resolve_conflicts()
        return self.state()['actions'][aid]
    def _status(self, action, status, reason):
        if action['status']==status and action['reason']==reason: return
        self.store.append('ACTION',{**action,'status':status,'reason':reason,'version':action['version']+1},self.clock())
    def refresh(self):
        state=self.state()
        for a in state['actions'].values():
            if a['status']=='RETIRED': continue
            if parse_time(a['expires_at']) <= parse_time(self.clock()):
                self._status(a,'STALE','TTL_EXPIRED'); self.incident('TTL_EXPIRED',a['source_ids'][0],a['risk']); continue
            for iid in a['derived_from']:
                intel=state['intelligence'][iid]
                try:
                    for e in intel['evidence']:
                        self.store.read(e['hash']); self.store.read(e['text_hash'])
                        if state['snapshots'][e['source_id']][-1]['hash'] != e['hash']:
                            self._status(a,'REVIEW_REQUIRED','SOURCE_VERSION_CHANGED')
                except (ValueError,OSError):
                    self._status(a,'QUARANTINED','EVIDENCE_TAMPERED'); self.incident('EVIDENCE_TAMPERED',a['source_ids'][0],'CRITICAL')
        for sid in state['sources']:
            history=state['snapshots'].get(sid,[])
            reference_only=any(ref.get('action_eligible') is False and ref.get('snapshot_hash')==history[-1]['hash']
                              for ref in state['legacy_references'].values()) if history else False
            if not any(sid in a['source_ids'] for a in state['actions'].values()) and not reference_only:
                self.incident('UNREVIEWED_SOURCE',sid,'MEDIUM')
    def resolve_conflicts(self):
        actions=[a for a in self.state()['actions'].values() if a['status']=='ACTIVE']
        for a in actions:
            opposite=[b for b in actions if b['platform']==a['platform'] and b['topic']==a['topic'] and b['effect'] != a['effect'] and b['id']!=a['id']]
            for b in opposite:
                pa,pb=PRIORITY.index(a['authority']),PRIORITY.index(b['authority'])
                if pb < pa: self._status(a,'BLOCKED','HIGHER_AUTHORITY_CONFLICT')
                elif pa==pb:
                    self._status(a,'REVIEW_REQUIRED','EQUAL_AUTHORITY_CONFLICT'); self._status(b,'REVIEW_REQUIRED','EQUAL_AUTHORITY_CONFLICT')
                    self.incident('CONFLICT',a['source_ids'][0],'HIGH')
    def challenge(self, action_id, counter_id, reviewer):
        state=self.state()
        if not reviewer or counter_id not in state['intelligence']: raise ValueError('VERIFIED_COUNTER_REQUIRED')
        a=state['actions'][action_id]
        if a['status']=='RETIRED': raise ValueError('RETIRED_CANNOT_CHALLENGE')
        self.store.append('ACTION',{**a,'counter_evidence':sorted(set(a['counter_evidence']+[counter_id])),
                'counter_resolution':{k:v for k,v in a.get('counter_resolution',{}).items() if k!=counter_id},
                'status':'REVIEW_REQUIRED','reason':'COUNTER_EVIDENCE','version':a['version']+1},self.clock())
        self.incident('COUNTER_EVIDENCE',a['source_ids'][0],'HIGH')
        self.store.append('LEARNING',{'action_id':action_id,'counter_id':counter_id,'reviewer':reviewer,'decision':'CHALLENGE'},self.clock())
    def evolve(self, action_id, decision, reviewer, review=None):
        if not reviewer: raise ValueError('REVIEWER_REQUIRED')
        a=self.state()['actions'][action_id]
        if decision=='PROMOTE':
            if not review or review.reviewer != reviewer: raise ValueError('NEW_VERIFIED_REVIEW_REQUIRED')
            expected=digest(canonical([a['platform'],review.topic,review.statement]).encode())[:24]
            if expected != action_id: raise ValueError('PROMOTION_ID_MISMATCH')
            result=self.verify(review,revive=True)
        elif decision=='DEMOTE': self._status(a,'REVIEW_REQUIRED','MANUAL_DEMOTION')
        elif decision=='RETIRE': self._status(a,'RETIRED','MANUAL_RETIREMENT')
        else: raise ValueError('UNKNOWN_EVOLUTION')
        self.store.append('LEARNING',{'action_id':action_id,'decision':decision,'reviewer':reviewer,
                                     'outcome':self.state()['actions'][action_id]['status']},self.clock())
    def envelope(self,platform='X'):
        if platform not in PLATFORMS:raise ValueError('PLATFORM_INVALID')
        self.refresh(); self.resolve_conflicts(); state=self.state()
        active=[a for a in state['actions'].values() if a['platform']==platform and a['status']=='ACTIVE']
        blocked=[a for a in state['actions'].values() if a['platform']==platform and a['status']!='ACTIVE']
        hard_blocked=any(a['hard'] and a['authority']=='POLICY' and a['status']!='RETIRED' for a in blocked)
        audit=self.store.events()
        return {'contract_version':'0.8.0','platform':platform,'generated_at':self.clock(),'audit_head':audit[-1]['hash'] if audit else None,
                'policy_gate':'BLOCKED' if hard_blocked or not any(a['hard'] and a['authority']=='POLICY' for a in active) else 'VALID_SCOPED',
                'api_gate':'VALID_SCOPED' if any(a['hard'] and a['authority']=='API' for a in active) and not any(a['hard'] and a['authority']=='API' and a['status']!='RETIRED' for a in blocked) else 'BLOCKED',
                'coverage':'REVIEWED_TOPICS_ONLY','actions':active,'withheld_actions':[{'id':a['id'],'status':a['status'],'reason':a['reason']} for a in blocked],
                'valid_until':min((a['expires_at'] for a in active), default=self.clock())}
    def distribute(self, sink, consumer,platform='X'):
        if not consumer: raise ValueError('CONSUMER_REQUIRED')
        envelope=self.envelope(platform); key=digest(canonical([consumer,envelope]).encode())
        receipt=sink.accept(envelope)
        if not isinstance(receipt,dict) or receipt.get('code')!=0 or receipt.get('data',{}).get('envelope_hash') != digest(canonical(envelope).encode()):
            sid=next((sid for sid,s in self.state()['sources'].items() if s['platform']==platform),'x-automation')
            self.incident('DISTRIBUTION_FAILED',sid,'HIGH'); raise ValueError('DELIVERY_NOT_ACKNOWLEDGED')
        self.store.append('DELIVERY',{'id':key,'consumer':consumer,'time':self.clock(),'action_ids':[a['id'] for a in envelope['actions']],
                                    'envelope':envelope,'receipt':receipt,'status':'ACCEPTED'},self.clock())
        return receipt
    def ops(self, sink):
        envelope=self.envelope(); state=self.state(); receipts=[]
        open_incidents=[i for i in state['incidents'].values() if i['status']=='OPEN']
        healthy=not open_incidents and envelope['policy_gate']=='VALID_SCOPED' and envelope['api_gate']=='VALID_SCOPED'
        rollup={'id':'x-platform-health','kind':'HEALTH','source_id':'','platform':'X','severity':'LOW' if healthy else 'HIGH',
                'status':'HEALTHY_SCOPED' if healthy else 'NEEDS_ATTENTION','time':self.clock(),
                'blast_radius':{'actions':list(state['actions']),'consumers':sorted({d['consumer'] for d in state['deliveries'].values()}),'platforms':['X']}}
        rollups=[rollup]
        for platform in sorted({s['platform'] for s in state['sources'].values()}-{'X'}):
            env=self.envelope(platform)
            pending=[i for i in state['incidents'].values() if i['platform']==platform and i['status']=='OPEN']
            ok=not pending and env['policy_gate']=='VALID_SCOPED' and env['api_gate']=='VALID_SCOPED'
            rollups.append({'id':'platform-health-'+digest(platform.encode())[:12],'kind':'HEALTH','source_id':'','platform':platform,
                            'severity':'LOW' if ok else 'HIGH','status':'HEALTHY_SCOPED' if ok else 'NEEDS_ATTENTION','time':self.clock(),
                            'blast_radius':{'actions':[a['id'] for a in state['actions'].values() if a['platform']==platform],
                                            'consumers':sorted({d['consumer'] for d in state['deliveries'].values() if d['envelope']['platform']==platform}),
                                            'platforms':[platform]}})
        rollup['blast_radius']['actions']=[a['id'] for a in state['actions'].values() if a['platform']=='X']
        rollup['blast_radius']['consumers']=sorted({d['consumer'] for d in state['deliveries'].values() if d['envelope']['platform']=='X'})
        # X health must not inherit another platform's incidents.
        x_pending=[i for i in open_incidents if i['platform']=='X']
        healthy=not x_pending and envelope['policy_gate']=='VALID_SCOPED' and envelope['api_gate']=='VALID_SCOPED'
        rollup.update(status='HEALTHY_SCOPED' if healthy else 'NEEDS_ATTENTION',severity='LOW' if healthy else 'HIGH')
        for i in rollups+list(state['incidents'].values()):
            item_healthy=i['status']=='HEALTHY_SCOPED' if i['kind']=='HEALTH' else False
            event={**i,'next_check':self.next_check(i['source_id']) if i['source_id'] in state['sources'] else self.clock(),
                   'health':('HEALTHY_SCOPED' if item_healthy else 'DEGRADED') if i['kind']=='HEALTH' else 'RECOVERED' if i['status']=='RESOLVED' else 'DEGRADED',
                   'requires_attention':not item_healthy if i['kind']=='HEALTH' else i['status']=='OPEN',
                   'contract_version':'0.8.0','audit_head':self.store.events()[-1]['hash']}
            receipt=sink.accept(event)
            if receipt.get('code')!=0 or receipt.get('data',{}).get('event_hash') != digest(canonical(event).encode()): raise ValueError('OPS_NOT_ACKNOWLEDGED')
            self.store.append('OPS_RECEIPT',{'event':event,'receipt':receipt},self.clock()); receipts.append(receipt)
        return receipts
    def replay(self, until=None):
        state=self.store.projection(until)
        for snapshots in state['snapshots'].values():
            for s in snapshots:
                for key in ('hash','text_hash','diff_hash'): self.store.read(s[key])
        return {'mode':'HISTORICAL_READ_ONLY','state':state,'state_hash':digest(canonical(state).encode()),'verified_events':len(self.store.events(until))}
