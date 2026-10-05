"""Explicit local receivers; no network dispatch or operation of platform accounts."""
from pathlib import Path
import json
import sys
from dataclasses import asdict
from .contracts import canonical, parse_time, PLATFORMS
from .store import digest

class LocalRegistrySink:
    def __init__(self, root): self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def accept(self, envelope):
        h=digest(canonical(envelope).encode()); path=self.root/(h+'.json')
        path.write_text(canonical(envelope),encoding='utf-8')
        if digest(path.read_bytes())!=h: return {'code':1,'msg':'blocked','data':{}}
        return {'code':0,'msg':'accepted-local','data':{'envelope_hash':h,'receiver':'local-registry','path':str(path)}}

class EngineCheckedConsumer:
    """A stored receipt is not an execution authorization. Validate at each read."""
    def __init__(self, engine): self.engine=engine
    def consume(self, envelope, require_policy=True, require_api=False):
        if envelope.get('contract_version')!='0.8.0' or envelope.get('platform') not in PLATFORMS: raise ValueError('CONTRACT_MISMATCH')
        if parse_time(envelope['valid_until']) <= parse_time(self.engine.clock()): raise ValueError('ENVELOPE_EXPIRED')
        current=self.engine.envelope(envelope['platform'])
        for key in ('actions','withheld_actions','policy_gate','api_gate'):
            if canonical(envelope.get(key)) != canonical(current[key]): raise ValueError('ENVELOPE_REVOKED_OR_CHANGED')
        if require_policy and current['policy_gate']!='VALID_SCOPED': raise ValueError('POLICY_FAIL_CLOSED')
        if require_api and current['api_gate']!='VALID_SCOPED': raise ValueError('API_FAIL_CLOSED')
        return {'code':0,'msg':'verified-for-intelligence-consumption','data':{'actions':current['actions'],'coverage':'REVIEWED_TOPICS_ONLY','execution_authorized':False}}

class AgentOpsSink:
    """Consumes with actual Agent Ops model/state engine, in isolated local inbox.

    SCOPED represents an attention work item; never assign READY/PRODUCTION.
    Desktop runtime integration may consume these versioned local work items.
    """
    def __init__(self, ops_source, inbox):
        self.source=Path(ops_source).resolve(); self.inbox=Path(inbox).resolve()
        if not (self.source/'sayelf_agent_ops/models.py').is_file(): raise ValueError('OPS_SOURCE_UNAVAILABLE')
        sys.path.insert(0,str(self.source))
        from sayelf_agent_ops.models import WorkItem
        from sayelf_agent_ops.state import StateEngine, WorkState
        self.WorkItem=WorkItem; self.StateEngine=StateEngine; self.WorkState=WorkState
        self.inbox.mkdir(parents=True,exist_ok=True)
    def accept(self,event):
        h=digest(canonical(event).encode()); path=self.inbox/(event['id']+'.json')
        wi=self.WorkItem(id='platform-intelligence:'+event['id'], input=event['platform']+' 平台情报状态：'+event['kind'],
                         goal='审查官方证据与受影响行动',deliverable='platform-intelligence-review',industry='media')
        self.StateEngine().transition(wi,self.WorkState.SCOPED)
        wi.outputs.append({'type':'platform-intelligence-health' if event['kind']=='HEALTH' else 'platform-intelligence-attention',
                           'contract_version':'0.8.0','health':event['health'],'status':event['status'],
                           'requires_attention':event['requires_attention'],
                           'risk':event['severity'],'anomaly':event['kind'],'blast_radius':event['blast_radius'],
                           'next_check':event['next_check'],'evidence':{'audit_head':event['audit_head'],'event_hash':h}})
        wi.history.append({'event':'platform-intelligence-ingested','id':event['id'],'event_hash':h})
        record={'workitem':asdict(wi),'event':event,'event_hash':h,'receiver_state':'SCOPED','execution':'NOT_EXECUTED'}
        path.write_text(canonical(record),encoding='utf-8')
        if json.loads(path.read_text(encoding='utf-8'))['event_hash']!=h: raise ValueError('OPS_RECEIPT_INVALID')
        return {'code':0,'msg':'accepted-local-agentops','data':{'event_hash':h,'workitem_id':wi.id,'state':wi.state,
                'execution':'NOT_EXECUTED','path':str(path),'receiver':'AgentOps-WorkItem-StateEngine'}}
