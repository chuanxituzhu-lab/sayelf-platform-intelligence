"""Read-only official source adapters. Redirects checked before following."""
from html.parser import HTMLParser
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit,parse_qsl
from .contracts import Source, PLATFORMS

ALLOWED = {'help.x.com', 'docs.x.com', 'raw.githubusercontent.com'}

def official_url(url, platform=None):
    try:
        p = urlsplit(url)
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443): return False
    except ValueError: return False
    x=p.hostname in {'help.x.com','docs.x.com'} or (p.hostname=='raw.githubusercontent.com' and p.path.startswith('/xai-org/x-algorithm/'))
    if platform=='X': return x
    from .catalog import CATALOG,REDIRECTS
    # Only curated document paths, plus descendants, can carry official authority.
    # Shared hosting (Google/Meta/Tencent) must match this platform's own endpoints.
    for selected,rows in CATALOG.items():
        if platform is not None and selected!=platform:continue
        for url in [row[3] for row in rows]+list(REDIRECTS.get(selected,())):
            expected=urlsplit(url); prefix=expected.path.rstrip('/') or '/'
            path_ok=p.path==expected.path or (prefix!='/' and p.path.startswith(prefix+'/'))
            if p.hostname==expected.hostname and path_ok and (not expected.query or sorted(parse_qsl(p.query))==sorted(parse_qsl(expected.query))):return True
    return x if platform is None else False

class SafeRedirect(HTTPRedirectHandler):
    def __init__(self,platform='X'):super().__init__();self.platform=platform
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not official_url(newurl,self.platform):
            raise ValueError('REDIRECT_BLOCKED')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        if tag in ('h1','h2','h3','h4','p','li','br','div','section'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip = max(0, self.skip-1)
        if tag in ('h1','h2','h3','h4','p','li','div','section'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

class AcquisitionRejected(ValueError):
    """A known access challenge is not a policy document or a document change."""

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_title=False; self.parts=[]
    def handle_starttag(self, tag, attrs):
        if tag=='title': self.in_title=True
    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
    def handle_data(self, data):
        if self.in_title: self.parts.append(data)

def check_acquisition(raw, media):
    # Deliberately narrow signatures: policy text may legitimately discuss CAPTCHA.
    # This is a rejection guard, not proof that every other page is a valid document.
    if 'html' not in media.lower(): return
    parser=TitleParser(); parser.feed(raw.decode('utf-8',errors='replace'))
    title=' '.join(''.join(parser.parts).casefold().split()).strip('. !…')
    blocked={'just a moment','access denied','attention required! | cloudflare',
             'verify you are human','please enable javascript','checking your browser',
             'robot check','访问受限','访问被拒绝','安全验证'}
    if title in blocked: raise AcquisitionRejected('ACCESS_CHALLENGE_NOT_DOCUMENT')

def extract(raw, media):
    text = raw.decode('utf-8', errors='replace')
    if 'html' in media:
        parser = TextParser(); parser.feed(text); text = ''.join(parser.parts)
    return '\n'.join(' '.join(line.split()) for line in text.splitlines() if line.strip())

class XAdapter:
    platform = 'X'
    def sources(self):
        return [
            Source('x-automation','X','POLICY','https://help.x.com/en/rules-and-policies/x-automation','自动化规则'),
            Source('x-api-rate','X','API','https://docs.x.com/x-api/fundamentals/rate-limits','API 速率限制'),
            Source('x-algorithm','X','ALGORITHM','https://raw.githubusercontent.com/xai-org/x-algorithm/main/README.md','公开推荐算法源码说明',ttl_hours=720),
            Source('x-product','X','PRODUCT','https://docs.x.com/x-api/introduction','API 产品能力',ttl_hours=720),
        ]
    def fetch(self, source):
        if source.platform != 'X' or source.classification != 'Public' or not official_url(source.url):
            raise ValueError('FETCH_SCOPE_BLOCKED')
        req = Request(source.url, headers={'User-Agent':'SayelfPlatformIntelligence/0.9.0 (public-document-monitor)', 'Accept':'text/html,text/plain'})
        with build_opener(SafeRedirect).open(req, timeout=12) as response:
            raw = response.read(8*1024*1024+1)
            if len(raw) > 8*1024*1024: raise ValueError('SOURCE_TOO_LARGE')
            return raw, response.headers.get('Content-Type','text/plain')

class CapabilityBenchmark:
    def compare(self, intelligence):
        # A capability match is only a lead. Never propagate another platform's fact.
        return [{'platform':p, 'capability':intelligence['capability'], 'status':'NO_DIRECT_EQUIVALENT',
                 'confidence':0, 'evidence':[], 'requires_independent_verification':True}
                for p in PLATFORMS if p != intelligence.get('platform','X')]

class PlatformAdapter:
    def __init__(self,platform):
        if platform not in PLATFORMS or platform=='X':raise ValueError('PLATFORM_ADAPTER_INVALID')
        self.platform=platform
    def sources(self):
        from .catalog import sources_for
        return sources_for(self.platform)
    def fetch(self,source):
        if source.platform!=self.platform or source.classification!='Public' or not official_url(source.url,self.platform):
            raise ValueError('FETCH_SCOPE_BLOCKED')
        req=Request(source.url,headers={'User-Agent':'SayelfPlatformIntelligence/0.9.0 (public-document-monitor)','Accept':'text/html,text/plain'})
        with build_opener(SafeRedirect(self.platform)).open(req,timeout=12) as response:
            raw=response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError('SOURCE_TOO_LARGE')
            media=response.headers.get('Content-Type','text/plain')
        check_acquisition(raw,media)
        text=extract(raw,media)
        from .catalog import markers_for
        markers=markers_for(source)
        if len(text)<200 or not any(m.casefold() in text.casefold() for m in markers):
            raise AcquisitionRejected('OFFICIAL_BODY_NOT_AVAILABLE')
        if len(text)<1500 and any(s in text.casefold() for s in ('扫码登录','请登录','log in to continue','enable javascript')):
            raise AcquisitionRejected('LOGIN_OR_SCRIPT_SHELL_NOT_DOCUMENT')
        return raw,media

def get_adapter(platform):return XAdapter() if platform=='X' else PlatformAdapter(platform)

def adapter_registry():
    return {p: {'enabled':True,'adapter':'XAdapter' if p == 'X' else 'PlatformAdapter','scope':'PUBLIC_OFFICIAL_SOURCE_MONITOR'} for p in PLATFORMS}
