"""Read-only bridge for the existing sayelf-algo-radar X section.

The page is a secondary summary. Its badges cannot confer primary-source
status on individual claims. This adapter creates reference records only.
"""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
from .contracts import Source, utcnow

MAX_BYTES=2*1024*1024
REVIEW_DAYS=90
STALE_DAYS=120

class XSectionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside=False;self.skip=[];self.depth=0;self.parts=[];self.start_line=None;self.end_line=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if not self.inside and tag=='section' and attrs.get('id')=='x':
            self.inside=True;self.depth=1;self.start_line=self.getpos()[0]
            self.parts.append('\n');return
        if not self.inside:return
        line=self.getpos()[0];self.end_line=line
        if self.skip and self.skip[-1][0]=='actions':
            if tag==self.skip[-1][1]:self.skip[-1][2]+=1
            return
        if self.skip:return
        if 'actions' in attrs.get('class','').split():
            self.skip.append(['actions',tag,1]);return
        if tag in ('script','style'):
            self.skip.append([tag,0]);return
        if tag=='section':self.depth+=1
        if not self.skip and tag in ('h2','h3','h4','p','li','div','br','article'):
            self.parts.append('\n')
    def handle_endtag(self,tag):
        if not self.inside:return
        self.end_line=self.getpos()[0]
        if self.skip:
            item=self.skip[-1]
            if item[0]=='actions' and tag==item[1]:
                item[2]-=1
                if item[2]==0:self.skip.pop()
            elif item[0]==tag:self.skip.pop()
            return
        if tag in ('h2','h3','h4','p','li','div','article'):self.parts.append('\n')
        if tag=='section':
            self.depth-=1
            if self.depth==0:self.inside=False
    def handle_data(self,data):
        if self.inside and not self.skip:
            clean=' '.join(data.split())
            if clean and clean not in ('创作者实操建议','Creator playbook'):
                self.parts.append(clean+' ')
    def text(self):
        return '\n'.join(' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip())

def _git_meta(index):
    result={'revision':'UNVERSIONED_LOCAL','working_tree_changed':None,'repo':'local-reference'}
    for args,key in ((['rev-parse','--show-toplevel'],'root'),(['rev-parse','HEAD'],'revision')):
        try:
            p=subprocess.run(['git','-C',str(index.parent),*args],capture_output=True,text=True,timeout=4,check=True)
            value=p.stdout.strip()
            if key=='root' and Path(value).name!='sayelf-algo-radar':return result
            result[key]=value
            if key=='root':result['repo']='git'
        except (OSError,subprocess.SubprocessError):return result
    try:
        p=subprocess.run(['git','-C',str(index.parent),'status','--porcelain','--','index.html'],capture_output=True,text=True,timeout=4,check=True)
        result['working_tree_changed']=bool(p.stdout.strip())
    except (OSError,subprocess.SubprocessError):result['working_tree_changed']=None
    return result

class LegacyRadarAdapter:
    platform='X'
    def collect(self,engine,path,platform='X',today=None):
        if platform!='X':raise ValueError('LEGACY_RADAR_X_ONLY')
        index=Path(path)
        if index.is_symlink() or index.name!='index.html' or not index.is_file():raise ValueError('LOCAL_REFERENCE_FILE_REQUIRED')
        index=index.resolve(strict=True)
        if index.stat().st_size>MAX_BYTES:raise ValueError('LOCAL_REFERENCE_TOO_LARGE')
        raw=index.read_bytes()
        if b'\x00' in raw:raise ValueError('LOCAL_REFERENCE_INVALID')
        html=raw.decode('utf-8')
        parser=XSectionParser();parser.feed(html);section=parser.text()
        if not section or parser.start_line is None:raise ValueError('X_SECTION_NOT_FOUND')
        match=re.search(r'(?:Last updated|最近更新)</span>\s*<b>(\d{4}-\d{2}-\d{2})</b>',html)
        if not match:raise ValueError('PUBLISHED_DATE_NOT_FOUND')
        published=date.fromisoformat(match[1]);today=today or date.today();age=(today-published).days
        if age<0:status='INVALID_FUTURE_DATE'
        elif age>=STALE_DAYS:status='STALE'
        elif age>=REVIEW_DAYS:status='REVIEW_DUE'
        else:status='CURRENT_REFERENCE_ONLY'
        git=_git_meta(index)
        if git['working_tree_changed'] is True:status='SOURCE_MODIFIED_REVIEW_REQUIRED'
        source=Source('local-algo-radar-x','X','OBSERVATION','local://sayelf-algo-radar/index.html',
                      'Algo Radar · X 排序参考',provenance='RESEARCH',classification='Internal',
                      ttl_hours=STALE_DAYS*24,importance='LOW')
        engine.register(source)
        snap=engine.capture(source.id,raw,'text/html',acquisition='LOCAL_REFERENCE_FILE',
                            origin_attestation='Read-only local file; full HTML saved by SHA-256')
        section_hash=engine.store.blob(section.encode('utf-8'))
        prior=engine.state()['legacy_references'].get('sayelf-algo-radar-x')
        version=prior['version']+1 if prior and (prior['snapshot_hash']!=snap['hash'] or prior['text_hash']!=section_hash) else prior['version'] if prior else 1
        record={'id':'sayelf-algo-radar-x','platform':'X','kind':'LEGACY_RESEARCH_REFERENCE',
                'status':status,'action_eligible':False,'authority':'RESEARCH_ONLY','claims_individually_verified':False,'extractor_version':'2',
                'source':{'name':'sayelf-algo-radar','section':'#x','locator':f'index.html:{parser.start_line}-{parser.end_line}#x',
                          'published_at':published.isoformat(),'age_days':age,**git},
                'snapshot_hash':snap['hash'],'text_hash':section_hash,'snapshot_version':snap['version'],'version':version,
                'captured_at':snap['time'],'excerpt':section,
                'boundary':'速查页标注官方来源不等于每条 X 排序权重均有逐项官方定位；仅保留为待核验参考，不产生 Action Intelligence。'}
        if prior is None or prior['snapshot_hash']!=snap['hash'] or prior['text_hash']!=section_hash or prior['status']!=status or prior['source']!=record['source']:
            engine.store.append('RADAR_REFERENCE',record,engine.clock())
        # Capture and version the secondary-source update. It has no eligible
        # downstream actions, so completing this explicit import closes its
        # previous source-change review event.
        engine.resolve_incidents('SOURCE_CHANGED',source.id)
        return record
