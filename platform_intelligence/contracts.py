from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Protocol

VERSION = '0.8.0'
STAGES = ('Monitor', 'Evidence', 'Verify', 'Diff', 'Version', 'Iceberg', 'Impact', 'Benchmark', 'Action Intelligence', 'Distribute')
ICEBERG = ('FACT', 'PHENOMENON', 'RELATION', 'MECHANISM', 'BOUNDARY', 'IMPACT', 'ACTION', 'MEASURE')
PRIORITY = ('LEGAL', 'POLICY', 'API', 'SAFETY', 'PRODUCT', 'OFFICIAL_ALGORITHM', 'RESEARCH', 'OBSERVATION', 'COMMUNITY')
PLATFORMS = ('X', 'YouTube', 'Instagram', 'Facebook', 'Reddit', 'TikTok', '小红书', '视频号', '抖音', '公众号', '哔哩哔哩')

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def canonical(value):
    import json
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def parse_time(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return dt.astimezone(timezone.utc)

@dataclass(frozen=True)
class Source:
    id: str
    platform: str
    kind: str
    url: str
    title: str
    provenance: str = 'OFFICIAL'
    classification: str = 'Public'
    ttl_hours: int = 168
    importance: str = 'HIGH'

@dataclass(frozen=True)
class Review:
    source_id: str
    snapshot_hash: str
    locator: str
    excerpt: str
    reviewer: str
    statement: str
    capability: str
    iceberg: dict
    action_class: str
    measure: str
    authority: str
    provenance: str = 'OFFICIAL'
    hard: bool = False
    effect: str = 'ALLOW'
    topic: str = ''
    risk: str = 'MEDIUM'
    ttl_hours: int = 168
    counter_evidence: list = field(default_factory=list)
    counter_resolution: dict = field(default_factory=dict)

class MonitorAdapter(Protocol):
    platform: str
    def sources(self) -> list[Source]: ...
    def fetch(self, source: Source) -> tuple[bytes, str]: ...

class BenchmarkAdapter(Protocol):
    def compare(self, intelligence: dict) -> list[dict]: ...

class OpsSink(Protocol):
    def accept(self, event: dict) -> dict: ...

class DistributeSink(Protocol):
    def accept(self, envelope: dict) -> dict: ...

class LocalReferenceAdapter(Protocol):
    def collect(self, path, platform: str = 'X') -> dict: ...

def validate_review(review):
    r = asdict(review)
    if not all(r[k] for k in ('source_id', 'snapshot_hash', 'locator', 'excerpt', 'reviewer', 'statement', 'capability', 'measure', 'topic')):
        raise ValueError('REVIEW_INCOMPLETE')
    if set(r['iceberg']) != set(ICEBERG) or not all(isinstance(x, dict) and set(x) == {'label', 'text'} and x['text'] and x['label'] in ('FACT', 'INFERENCE', 'OBSERVATION', 'HYPOTHESIS', 'ACTION') for x in r['iceberg'].values()):
        raise ValueError('ICEBERG_INCOMPLETE')
    if r['action_class'] not in ('MUST', 'SHOULD', 'TEST', 'AVOID') or r['authority'] not in PRIORITY or r['effect'] not in ('ALLOW', 'DENY'):
        raise ValueError('INVALID_ACTION')
    if r['risk'] not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') or r['ttl_hours'] <= 0:
        raise ValueError('INVALID_RISK_OR_TTL')
    if r['hard'] and r['action_class'] not in ('MUST', 'AVOID'):
        raise ValueError('HARD_CLASS_REQUIRED')
    for key,value in r['counter_resolution'].items():
        if not isinstance(value,dict) or value.get('decision') not in ('NOT_APPLICABLE','SUPERSEDED') or not value.get('rationale'):
            raise ValueError('COUNTER_RESOLUTION_REQUIRED')
    return r
