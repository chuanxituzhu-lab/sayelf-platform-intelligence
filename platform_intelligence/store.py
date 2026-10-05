import hashlib
import json
import sqlite3
from pathlib import Path
from .contracts import canonical, utcnow

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

class Store:
    """Append-only hash-linked audit; projection rebuildable from its events."""
    def __init__(self, root):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        (self.root/'snapshots').mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root/'intelligence.sqlite3', timeout=15)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, time TEXT, type TEXT, payload TEXT, previous TEXT, hash TEXT)')
        self.db.commit()
    def close(self): self.db.close()
    def blob(self, raw):
        h = digest(raw); path = self.root/'snapshots'/h
        if path.exists():
            if digest(path.read_bytes()) != h: raise ValueError('SNAPSHOT_TAMPERED')
        else:
            temp = path.with_suffix('.tmp'); temp.write_bytes(raw); temp.replace(path)
        return h
    def read(self, h):
        if len(h) != 64 or any(c not in '0123456789abcdef' for c in h): raise ValueError('INVALID_HASH')
        raw = (self.root/'snapshots'/h).read_bytes()
        if digest(raw) != h: raise ValueError('SNAPSHOT_TAMPERED')
        return raw
    def append(self, kind, payload, at=None):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
            seq, previous = (row[0]+1,row[1]) if row else (1,'0'*64)
            t = at or utcnow(); body = canonical(payload)
            h = digest(canonical([seq,t,kind,body,previous]).encode())
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(seq,t,kind,body,previous,h))
        return seq
    def events(self, until=None):
        rows = self.db.execute('SELECT * FROM events ORDER BY seq').fetchall()
        previous='0'*64; result=[]
        for seq,t,kind,body,prev,h in rows:
            if until is not None and seq > until: break
            if prev != previous or digest(canonical([seq,t,kind,body,prev]).encode()) != h:
                raise ValueError('AUDIT_TAMPERED')
            previous=h; result.append({'seq':seq,'time':t,'type':kind,'payload':json.loads(body),'hash':h})
        return result
    def projection(self, until=None):
        state={'sources':{},'snapshots':{},'intelligence':{},'actions':{},'incidents':{},'deliveries':{},'runs':[],'legacy_references':{}}
        for event in self.events(until):
            p=event['payload']; k=event['type']
            if k=='SOURCE': state['sources'][p['id']]=p
            elif k=='SNAPSHOT':
                state['snapshots'].setdefault(p['source_id'],[]).append(p)
            elif k=='INTELLIGENCE': state['intelligence'][p['id']]=p
            elif k=='ACTION': state['actions'][p['id']]=p
            elif k=='INCIDENT': state['incidents'][p['id']]=p
            elif k=='DELIVERY': state['deliveries'][p['id']]=p
            elif k=='RUN': state['runs'].append(p)
            elif k=='RADAR_REFERENCE': state['legacy_references'][p['id']]=p
        return state
