from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, quote
from html import escape
import secrets
import socket
import os
from .engine import Engine
from .adapters import XAdapter,get_adapter
from .contracts import ICEBERG, PLATFORMS

def platform_nav(selected):
    return '<nav aria-label="选择平台">'+''.join(
        f'<a href="/?platform={quote(p)}" '+('aria-current="page" ' if p==selected else '')+
        f'style="display:inline-block;padding:10px;margin:4px;border:1px solid #bdccc1;border-radius:10px">{escape("Instagram（Ins）" if p=="Instagram" else p)} · 官方来源已配置</a>'
        for p in PLATFORMS)+'</nav>'


LABELS={'ACTIVE':'有效','STALE':'已过期','REVIEW_REQUIRED':'待复核','QUARANTINED':'已隔离','BLOCKED':'已暂停','RETIRED':'已淘汰',
        'MUST':'必须遵守','SHOULD':'建议执行','TEST':'待验证实验','AVOID':'避免',
        'SOURCE_CHANGED':'官方来源发生变化','SOURCE_UNAVAILABLE':'官方来源暂时不可用','TTL_EXPIRED':'行动依据已过期',
        'UNREVIEWED_SOURCE':'来源尚待审核','CONFLICT':'证据发生冲突','COUNTER_EVIDENCE':'出现反面证据','EVIDENCE_TAMPERED':'证据完整性异常'}
LAYER={'FACT':'官方事实','PHENOMENON':'可观察现象','RELATION':'关系','MECHANISM':'可能机制','BOUNDARY':'推论边界','IMPACT':'影响','ACTION':'行动','MEASURE':'观察指标'}
EPISTEMIC={'FACT':'事实','INFERENCE':'推断','OBSERVATION':'观察','HYPOTHESIS':'待验证假设','ACTION':'行动建议'}

class LocalHTTPServer(HTTPServer):
    allow_reuse_address=False
    def server_bind(self):
        if os.name=='nt': self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

def render(e,token,brief=None,platform="X"):
    envelope=e.envelope(platform); state=e.state()
    state['sources']={sid:s for sid,s in state['sources'].items() if s['platform']==platform}
    state['snapshots']={sid:snaps for sid,snaps in state['snapshots'].items() if sid in state['sources']}
    state['actions']={aid:a for aid,a in state['actions'].items() if a['platform']==platform}
    incidents=[i for i in state['incidents'].values() if i['platform']==platform and i['status']=='OPEN']
    health='需要处理' if incidents or envelope['policy_gate']=='BLOCKED' or envelope['api_gate']=='BLOCKED' else '已核验（限定范围）'
    cards=[]
    for a in state['actions'].values():
        facts=[]
        for iid in a['derived_from']:
            intel=state['intelligence'][iid]
            for ev in intel['evidence']:
                method='官方网页阅读通道的文本快照' if ev.get('acquisition')=='OFFICIAL_WEB_RENDERER_TEXT_CAPTURE' else '官方文档原始快照'
                facts.append(f'<a target="_blank" rel="noopener" href="{escape(ev["url"],quote=True)}">来源原文</a> · <a href="/evidence/{ev["hash"]}">本地快照</a> · <a href="/evidence/{ev["text_hash"]}">定位文本</a><p>{escape(ev["locator"])} · 核验 {escape(ev["reviewed_at"][:10])} · {method}</p>')
        why=''.join(f'<p><b>{LAYER[k]}</b> · {EPISTEMIC[a["iceberg"][k]["label"]]}<br>{escape(a["iceberg"][k]["text"])}</p>' for k in ICEBERG)
        cards.append(f'<article><span class="tag">{LABELS[a["action_class"]]}</span> <span>{LABELS[a["status"]]}</span><h3>{escape(a["statement"])}</h3><p>观察：{escape(a["measure"])}</p><p>复核期限：{escape(a["expires_at"][:10])}</p><details><summary>为什么 / 官方依据</summary>{why}{"".join(facts)}</details></article>')
    attention=''.join(f'<li>{escape(state["sources"].get(i["source_id"],{}).get("title","平台状态"))}：{escape(LABELS.get(i["kind"],i["kind"]))} · {escape({"LOW":"提示","MEDIUM":"需复核","HIGH":"重要","CRITICAL":"紧急"}.get(i["severity"],i["severity"]))} · 影响 {len(i["blast_radius"]["actions"])} 条行动 / {len(i["blast_radius"]["consumers"])} 个接收方</li>' for i in incidents) or '<li>目前没有待处理事项</li>'
    source_rows=[]
    for sid,source in state['sources'].items():
        snaps=state['snapshots'].get(sid,[]);latest=snaps[-1] if snaps else None
        failed=any(i['source_id']==sid and i['kind']=='SOURCE_UNAVAILABLE' for i in incidents)
        reviewed=any(a['status']=='ACTIVE' and any(ev['hash']==latest['hash'] and ev['source_id']==sid for ev in a.get('evidence',[])) for a in state['actions'].values()) if latest else False
        status='暂不可读取 / 需人工核对官方入口' if failed else '限定主题已核验' if reviewed else '已获取，待审核' if latest else '待检查'
        links=f'<a target="_blank" rel="noopener" href="{escape(source["url"],quote=True)}">打开官方来源</a>'
        if latest:links+=f' · <a href="/evidence/{latest["hash"]}">最近快照</a> · <a href="/evidence/{latest["text_hash"]}">定位文本</a>'
        source_rows.append(f'<li><b>{escape(source["title"])}</b> · {status}<br>{links}<br>历史版本 {len({x["hash"] for x in snaps})} · 下次检查 {escape(e.next_check(sid)[:16])}</li>')
    sources=''.join(source_rows) or '<li>官方来源已配置，点击检查建立基线。</li>'

    changes=[]
    for sid, snapshots in state['snapshots'].items():
        for snap in snapshots:
            if snap['changed']:
                changes.append(f'<li>{escape(state["sources"][sid]["title"])} · 版本 {snap["version"]} · <a href="/evidence/{snap["diff_hash"]}">查看原文差异</a></li>')
    radar=state['legacy_references'].get('sayelf-algo-radar-x')
    if radar:
        radar_labels={'CURRENT_REFERENCE_ONLY':'参考页已更新，仍需逐条核验','REVIEW_DUE':'参考页已到季度复核期',
                      'STALE':'参考页超过复核周期','SOURCE_MODIFIED_REVIEW_REQUIRED':'本地参考文件有未提交变更，待复核',
                      'INVALID_FUTURE_DATE':'参考页日期异常，待复核'}
        radar_html=f'<section><h2>Algo Radar · X 参考</h2><p>{escape(radar_labels.get(radar["status"],"待复核"))} · 页面日期 {escape(radar["source"]["published_at"])} · 已过 {radar["source"]["age_days"]} 天</p><p>{escape(radar["boundary"])}</p><details><summary>查看 X 参考摘要与本地依据</summary><p>本地版本 {escape(radar["source"]["revision"][:12])} · {escape(radar["source"]["locator"])}</p><pre style="white-space:pre-wrap;line-height:1.65">{escape(radar["excerpt"])}</pre><a href="/evidence/{radar["snapshot_hash"]}">查看原文件快照</a></details></section>'
    else:
        radar_html='<section><h2>Algo Radar · X 参考</h2><p>尚未导入本地旧参考页。导入后仅作带版本的研究线索，不会直接生成 Action。</p><form method="post" action="/radar-check"><input type="hidden" name="token" value="'+token+'"><button>读取本地 X 参考</button></form></section>'
    if platform!='X':radar_html=''
    brief_html=''
    if brief:
        citations=[]
        for action in brief['actions']:
            for proof in action['evidence']:
                citations.append(f'<li>{escape(action["section"])} · <a target="_blank" rel="noopener" href="{escape(proof["url"],quote=True)}">官方原文</a> · <a href="/evidence/{proof["snapshot_hash"]}">本地证据快照</a> · {escape(proof["locator"])} · 核验 {escape(proof["reviewed_at"][:10])}</li>')
        for change in brief['changes']:
            if change.get('diff_hash'):
                citations.append(f'<li>{escape(change["title"])} · <a target="_blank" rel="noopener" href="{escape(change["url"],quote=True)}">官方原文</a> · <a href="/evidence/{change["diff_hash"]}">本地变化记录</a> · {escape(change["status"])}</li>')
        for source in brief.get('sources',[]):
            snap=source.get('snapshot')
            proof=f' · <a href="/evidence/{snap["hash"]}">原文快照</a> · <a href="/evidence/{snap["text_hash"]}">定位文本（待审核）</a>' if snap else ''
            citations.append(f'<li>{escape(source["title"])} · <a target="_blank" rel="noopener" href="{escape(source["url"],quote=True)}">官方入口</a>{proof} · {escape(source["status"])}</li>')
        brief_html=f'''<section id="generated-brief"><h2>{escape(platform)} 规则与算法简报</h2>
        <p>本轮已检查 {brief['checked_count']} 个来源 · {brief['change_count']} 项正文变化 · {brief['source_update_count']} 个来源版本更新 · {brief['unavailable_count']} 个来源暂不可用</p>
        <p>规则结论仅来自有效审核证据；来源状态包含待审核快照和访问失败。未审核变化不推导规则。简报可复制后人工复核和编辑。</p>
        <textarea id="brief-content" aria-label="可复制的 {escape(platform)} 平台证据简报" readonly rows="24">{escape(brief['text'])}</textarea>
        <p><button type="button" data-copy-id="brief-content">复制简报</button> <span data-copy-status aria-live="polite"></span></p>
        <details><summary>查看官方依据与变化记录</summary><ul>{''.join(citations) or '<li>当前没有可展示的有效官方依据</li>'}</ul></details></section>'''
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SAYELF 海内外自媒体平台情报</title>
    <style>body{{margin:0;background:#f2f5f2;color:#19392f;font:16px system-ui}}main{{max-width:1050px;margin:auto;padding:40px 24px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:center}}h1{{font-size:34px}}.muted{{color:#63766e}}section,article{{background:white;border:1px solid #d9e3dc;border-radius:16px;padding:24px;margin:18px 0}}button{{border:0;border-radius:10px;background:#206849;color:white;padding:13px 20px;cursor:pointer}}.tag{{display:inline-block;background:#e0efe5;padding:5px 10px;border-radius:8px}}summary{{cursor:pointer;color:#206849}}a{{color:#206849}}li{{margin:12px 0}}details p{{line-height:1.6}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}textarea{{box-sizing:border-box;width:100%;min-height:420px;padding:14px;border:1px solid #bdccc1;border-radius:10px;background:#fbfdfb;color:#19392f;font:14px/1.6 ui-monospace,monospace;resize:vertical}}@media(max-width:700px){{.grid{{display:block}}header{{display:block}}}} </style><script src="/static/brief.js" defer></script>
    <main><header><div><p class="muted">SAYELF · 平台情报 v0.9.0</p><h1>海内外自媒体平台情报</h1><p>平台规则 · 算法 · API · 产品变化</p></div><form method="post" action="/check"><input type="hidden" name="token" value="{token}"><input type="hidden" name="platform" value="{escape(platform,quote=True)}"><button>检查 {escape(platform)} 官方变化并生成简报</button></form></header>
    {platform_nav(platform)}<h2>{escape(platform)} · 当前平台</h2>
    <section><h2>平台健康 · {health}</h2><p>政策：{'限定主题有效' if envelope['policy_gate']=='VALID_SCOPED' else '待核验 / 暂停依赖动作'}　API：{'限定主题有效' if envelope['api_gate']=='VALID_SCOPED' else '待核验 / 暂停依赖动作'}</p><p class="muted">所有平台已配置官方来源监测。获取快照不代表规则已核验；各平台结论独立审核。</p></section>
    <div class="grid"><section><h2>需处理事项</h2><ul>{attention}</ul></section><section><h2>近期变化</h2><ul>{''.join(changes) or '<li>尚无已捕获的原文变化</li>'}</ul><details open><summary>关注的官方来源与检查进度</summary><ul>{sources}</ul></details></section></div>
    {radar_html}{brief_html}<h2>今日 Action</h2>{''.join(cards) or '<section>尚无已核验行动。先检查官方来源，再完成证据审核。</section>'}</main></html>'''

def handler(data,port,token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def valid_host(self): return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
        def send(self,code,raw,media='text/html; charset=utf-8'):
            self.send_response(code); self.send_header('Content-Type',media); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; connect-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if not self.valid_host(): self.send(403,b'Forbidden'); return
            parsed=urlsplit(self.path); path=parsed.path
            if path=='/static/brief.js':
                raw=(Path(__file__).with_name('static')/'brief.js').read_bytes()
                self.send(200,raw,'text/javascript; charset=utf-8'); return
            e=Engine(data)
            try:
                if path=='/':
                    platform=parse_qs(parsed.query).get('platform',['X'])
                    if len(platform)!=1 or platform[0] not in PLATFORMS:
                        self.send(400,'请选择目录中的平台'.encode()); return
                    brief=None
                    if parse_qs(parsed.query).get('brief')==['1']:
                        from .briefs import build_brief
                        brief=build_brief(e,platform[0])
                    self.send(200,render(e,token,brief,platform[0]).encode())
                elif path.startswith('/evidence/'):
                    h=path.split('/')[-1]; raw=e.store.read(h)
                    # Always escaped text; raw HTML never executes. Binary originals download.
                    if b'\x00' in raw or raw.startswith(b'%PDF'):
                        self.send(200,raw,'application/octet-stream')
                    else: self.send(200,('<meta charset="utf-8"><pre>'+escape(raw.decode('utf-8',errors='replace'))+'</pre>').encode())
                else: self.send(404,b'Not found')
            except (ValueError,OSError): self.send(409,b'Evidence unavailable or integrity check failed')
            finally: e.store.close()
        def do_POST(self):
            if not self.valid_host() or self.path not in ('/check','/radar-check') or self.headers.get('Origin') not in (None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                self.send(403,b'Forbidden'); return
            try: length=int(self.headers.get('Content-Length','0'))
            except ValueError: self.send(400,b'Invalid length'); return
            if length<0 or length>512: self.send(413,b'Too large'); return
            if self.path=='/radar-check' and length==0:length=0
            form=parse_qs(self.rfile.read(length).decode())
            if form.get('token')!=[token]: self.send(403,b'Forbidden'); return
            selected=form.get('platform',['X'])
            if len(selected)!=1 or selected[0] not in PLATFORMS:
                self.send(400,b'Invalid platform');return
            platform=selected[0]
            e=Engine(data)
            try:
                if self.path=='/check':e.monitor(XAdapter() if platform=='X' else get_adapter(platform),force=True)
                else:
                    from .legacy_radar import LegacyRadarAdapter
                    from .cli import radar_path
                    LegacyRadarAdapter().collect(e,radar_path())
                self.send_response(303); self.send_header('Location',('/?brief=1' if platform=='X' else '/?platform='+quote(platform)+'&brief=1') if self.path=='/check' else '/'); self.end_headers()
            except (OSError,ValueError):self.send(503,b'Local reference unavailable or needs review')
            finally: e.store.close()
    return Handler

def serve(data,port,open_browser=False):
    token=secrets.token_urlsafe(32)
    print(f'http://127.0.0.1:{port}',flush=True)
    server=LocalHTTPServer(('127.0.0.1',port),handler(data,port,token))
    if open_browser:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{port}')
    server.serve_forever()
