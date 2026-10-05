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
from .briefs import localize_action_text

UI_EN={
    'choose_platform':'Choose a platform','configured':'Official sources configured','instagram':'Instagram (Ins)',
    'official_change':'Check {platform} official updates and create a brief','platform_current':'Current platform',
    'health':'Platform health','needs_attention':'Needs attention','verified_scoped':'Verified (scoped)',
    'policy':'Policy','api':'API','scoped_valid':'Valid for reviewed scope','await_review':'Awaiting review / dependent actions paused',
    'monitor_note':'Official sources are configured for all listed platforms. A snapshot is not policy verification; conclusions are reviewed per platform.',
    'attention':'Items needing attention','recent_changes':'Recent changes','no_attention':'No items need attention right now',
    'no_changes':'No source-text changes captured yet','sources_progress':'Official sources and check status',
    'source_open':'Open official source','snapshot_open':'Latest snapshot','locator_open':'Located text',
    'snapshot_reviewed':'Captured; review pending','source_failed':'Unavailable; check the official entry manually',
    'source_verified':'Reviewed for a scoped topic','source_waiting':'Captured; awaiting review','source_unchecked':'Not checked yet',
    'history':'History versions','next_check':'Next check','configured_empty':'Official sources are configured. Check to create a baseline.',
    'version':'Version','view_diff':'View source diff','radar_title':'Algo Radar · X reference',
    'radar_changed':'Reference updated; verify each item','radar_due':'Quarterly reference review is due','radar_stale':'Reference is past its review interval',
    'radar_modified':'Local reference has uncommitted changes; review required','radar_date':'Reference date is invalid; review required',
    'radar_wait':'No local reference imported. Import it only as versioned research context; it cannot directly create Actions.',
    'radar_details':'View X reference and local evidence','radar_read':'Read local X reference','radar_config':'Set SAYELF_ALGO_RADAR_PATH to enable the local reference action.',
    'brief_title':'{platform} policy and algorithm brief','brief_stats':'This check read {checked} sources · {changes} text changes · {updates} source-version updates · {unavailable} unavailable',
    'brief_note':'Conclusions require current reviewed evidence. Pending changes and access failures are shown separately. Review and edit this brief before sharing.',
    'brief_label':'Copyable {platform} evidence brief','copy':'Copy brief','citations':'Official evidence and change history',
    'no_citations':'No reviewed official evidence to show','original':'Official source','local_snapshot':'Local evidence snapshot',
    'change_record':'Local change record','source_entry':'Official entry','pending_locator':'Located text (review pending)',
    'reviewed_at':'reviewed','unavailable':'unavailable','urgent':'Urgent','important':'Important','review':'Review','notice':'Notice',
    'impact':' · affects {actions} actions / {consumers} recipients','observation':'Measure','expiry':'Review by',
    'why':'Why / official evidence','today':'Today’s Actions','no_actions':'No verified actions yet. Check official sources and review the evidence first.',
    'source_method_web':'Text snapshot from official web-rendering view','source_method_doc':'Original official-document snapshot',
    'invalid_platform':'Please choose a platform from the catalog.','invalid_language':'Unsupported language choice.',
    'brand_title':'SAYELF · Platform Intelligence v0.9.1','page_title':'SAYELF Platform Intelligence',
    'page_subtitle':'Platform policies · algorithms · APIs · product updates','language':'Language',
}

PLATFORM_NAMES_EN={'小红书':'Xiaohongshu','视频号':'WeChat Channels','抖音':'Douyin','公众号':'WeChat Official Accounts','哔哩哔哩':'Bilibili'}
LABELS_EN={'ACTIVE':'Active','STALE':'Expired','REVIEW_REQUIRED':'Review required','QUARANTINED':'Quarantined','BLOCKED':'Paused','RETIRED':'Retired',
           'MUST':'Must','SHOULD':'Should','TEST':'Test','AVOID':'Avoid','SOURCE_CHANGED':'Official source changed','SOURCE_UNAVAILABLE':'Official source unavailable',
           'TTL_EXPIRED':'Action evidence expired','UNREVIEWED_SOURCE':'Source awaiting review','CONFLICT':'Conflicting evidence','COUNTER_EVIDENCE':'Counterevidence found','EVIDENCE_TAMPERED':'Evidence integrity issue'}
LAYER_EN={'FACT':'Official fact','PHENOMENON':'Observable phenomenon','RELATION':'Relationship','MECHANISM':'Possible mechanism','BOUNDARY':'Inference boundary','IMPACT':'Impact','ACTION':'Action','MEASURE':'Measure'}
EPISTEMIC_EN={'FACT':'Fact','INFERENCE':'Inference','OBSERVATION':'Observation','HYPOTHESIS':'Hypothesis to test','ACTION':'Recommended action'}
SEVERITY_EN={'LOW':'Notice','MEDIUM':'Review','HIGH':'Important','CRITICAL':'Urgent'}

def ui(key,lang='zh',**kwargs):
    if lang=='en': return UI_EN[key].format(**kwargs)
    return {
        'choose_platform':'选择平台','configured':'官方来源已配置','instagram':'Instagram（Ins）',
        'official_change':'检查 {platform} 官方变化并生成简报','platform_current':'当前平台','health':'平台健康',
        'needs_attention':'需要处理','verified_scoped':'已核验（限定范围）','policy':'政策','api':'API',
        'scoped_valid':'限定主题有效','await_review':'待核验 / 暂停依赖动作','monitor_note':'所有平台已配置官方来源监测。获取快照不代表规则已核验；各平台结论独立审核。',
        'attention':'需处理事项','recent_changes':'近期变化','no_attention':'目前没有待处理事项','no_changes':'尚无已捕获的原文变化',
        'sources_progress':'关注的官方来源与检查进度','source_open':'打开官方来源','snapshot_open':'最近快照','locator_open':'定位文本',
        'snapshot_reviewed':'已获取，待审核','source_failed':'暂不可读取 / 需人工核对官方入口','source_verified':'限定主题已核验','source_waiting':'已获取，待审核','source_unchecked':'待检查',
        'history':'历史版本','next_check':'下次检查','configured_empty':'官方来源已配置，点击检查建立基线。','version':'版本','view_diff':'查看原文差异',
        'radar_title':'Algo Radar · X 参考','radar_changed':'参考页已更新，仍需逐条核验','radar_due':'参考页已到季度复核期','radar_stale':'参考页超过复核周期',
        'radar_modified':'本地参考文件有未提交变更，待复核','radar_date':'参考页日期异常，待复核',
        'radar_wait':'尚未导入本地旧参考页。导入后仅作带版本的研究线索，不会直接生成 Action。','radar_details':'查看 X 参考摘要与本地依据','radar_read':'读取本地 X 参考','radar_config':'设置 SAYELF_ALGO_RADAR_PATH 后可读取本地参考。',
        'brief_title':'{platform} 规则与算法简报','brief_stats':'本轮已检查 {checked} 个来源 · {changes} 项正文变化 · {updates} 个来源版本更新 · {unavailable} 个来源暂不可用',
        'brief_note':'规则结论仅来自有效审核证据；来源状态包含待审核快照和访问失败。未审核变化不推导规则。简报可复制后人工复核和编辑。',
        'brief_label':'可复制的 {platform} 平台证据简报','copy':'复制简报','citations':'查看官方依据与变化记录','no_citations':'当前没有可展示的有效官方依据',
        'original':'官方原文','local_snapshot':'本地证据快照','change_record':'本地变化记录','source_entry':'官方入口','pending_locator':'定位文本（待审核）',
        'reviewed_at':'核验','unavailable':'不可用','urgent':'紧急','important':'重要','review':'需复核','notice':'提示',
        'impact':' · 影响 {actions} 条行动 / {consumers} 个接收方','observation':'观察','expiry':'复核期限','why':'为什么 / 官方依据',
        'today':'今日 Action','no_actions':'尚无已核验行动。先检查官方来源，再完成证据审核。','source_method_web':'官方网页阅读通道的文本快照',
        'source_method_doc':'官方文档原始快照','invalid_platform':'请选择目录中的平台。','invalid_language':'语言选项无效。',
        'brand_title':'SAYELF · 平台情报 v0.9.1','page_title':'SAYELF 海内外自媒体平台情报','page_subtitle':'平台规则 · 算法 · API · 产品变化','language':'语言',
    }[key].format(**kwargs)

def platform_name(platform,lang):
    return PLATFORM_NAMES_EN.get(platform,platform) if lang=='en' else platform

def platform_nav(selected,lang='zh'):
    return f'<nav aria-label="{ui("choose_platform",lang)}">'+''.join(
        f'<a href="/?platform={quote(p)}&amp;lang={lang}" '+('aria-current="page" ' if p==selected else '')+
        f'style="display:inline-block;padding:10px;margin:4px;border:1px solid #bdccc1;border-radius:10px">{escape(ui("instagram",lang) if p=="Instagram" else platform_name(p,lang))} · {ui("configured",lang)}</a>'
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

def render(e,token,brief=None,platform="X",lang='zh'):
    lang='en' if lang=='en' else 'zh'
    english=lang=='en'; platform_label=platform_name(platform,lang)
    labels=LABELS_EN if english else LABELS
    layers=LAYER_EN if english else LAYER
    epistemic=EPISTEMIC_EN if english else EPISTEMIC
    envelope=e.envelope(platform); state=e.state()
    state['sources']={sid:s for sid,s in state['sources'].items() if s['platform']==platform}
    state['snapshots']={sid:snaps for sid,snaps in state['snapshots'].items() if sid in state['sources']}
    state['actions']={aid:a for aid,a in state['actions'].items() if a['platform']==platform}
    incidents=[i for i in state['incidents'].values() if i['platform']==platform and i['status']=='OPEN']
    needs_attention=bool(incidents or envelope['policy_gate']=='BLOCKED' or envelope['api_gate']=='BLOCKED')
    health=ui('needs_attention' if needs_attention else 'verified_scoped',lang)
    cards=[]
    for action in state['actions'].values():
        facts=[]
        for iid in action['derived_from']:
            intel=state['intelligence'][iid]
            for ev in intel['evidence']:
                method=ui('source_method_web' if ev.get('acquisition')=='OFFICIAL_WEB_RENDERER_TEXT_CAPTURE' else 'source_method_doc',lang)
                source_label='Official source' if english else '来源原文'
                snap_label='Local snapshot' if english else '本地快照'
                locator_label='Located text' if english else '定位文本'
                verified_label='reviewed' if english else '核验'
                facts.append(f'<a target="_blank" rel="noopener" href="{escape(ev["url"],quote=True)}">{source_label}</a> · <a href="/evidence/{ev["hash"]}">{snap_label}</a> · <a href="/evidence/{ev["text_hash"]}">{locator_label}</a><p>{escape(ev["locator"])} · {verified_label} {escape(ev["reviewed_at"][:10])} · {method}</p>')
        why=''.join(f'<p><b>{layers[k]}</b> · {epistemic[action["iceberg"][k]["label"]]}<br>{escape(localize_action_text("iceberg",(k,action["iceberg"][k]["text"]),lang))}</p>' for k in ICEBERG)
        action_statement=localize_action_text('statement',action['statement'],lang)
        action_measure=localize_action_text('measure',action['measure'],lang)
        verified=labels.get(action['status'],action['status'])
        cards.append(f'<article><span class="tag">{labels[action["action_class"]]}</span> <span>{verified}</span><h3>{escape(action_statement)}</h3><p>{ui("observation",lang)}: {escape(action_measure)}</p><p>{ui("expiry",lang)}: {escape(action["expires_at"][:10])}</p><details><summary>{ui("why",lang)}</summary>{why}{"".join(facts)}</details></article>')
    severity=SEVERITY_EN if english else {'LOW':'提示','MEDIUM':'需复核','HIGH':'重要','CRITICAL':'紧急'}
    status_label=labels.get
    attention=''.join(f'<li>{escape(state["sources"].get(i["source_id"],{}).get("title","Platform status" if english else "平台状态"))}: {escape(status_label(i["kind"],i["kind"]))} · {escape(severity.get(i["severity"],i["severity"]))}{ui("impact",lang,actions=len(i["blast_radius"]["actions"]),consumers=len(i["blast_radius"]["consumers"]))}</li>' for i in incidents) or f'<li>{ui("no_attention",lang)}</li>'
    source_rows=[]
    for sid,source in state['sources'].items():
        snaps=state['snapshots'].get(sid,[]);latest=snaps[-1] if snaps else None
        failed=any(i['source_id']==sid and i['kind']=='SOURCE_UNAVAILABLE' for i in incidents)
        reviewed=any(a['status']=='ACTIVE' and any(ev['hash']==latest['hash'] and ev['source_id']==sid for ev in a.get('evidence',[])) for a in state['actions'].values()) if latest else False
        status=(ui('source_failed',lang) if failed else ui('source_verified',lang) if reviewed else ui('source_waiting',lang) if latest else ui('source_unchecked',lang))
        links=f'<a target="_blank" rel="noopener" href="{escape(source["url"],quote=True)}">{ui("source_open",lang)}</a>'
        if latest:links+=f' · <a href="/evidence/{latest["hash"]}">{ui("snapshot_open",lang)}</a> · <a href="/evidence/{latest["text_hash"]}">{ui("locator_open",lang)}</a>'
        source_rows.append(f'<li><b>{escape(source["title"])}</b> · {status}<br>{links}<br>{ui("history",lang)} {len({x["hash"] for x in snaps})} · {ui("next_check",lang)} {escape(e.next_check(sid)[:16])}</li>')
    sources=''.join(source_rows) or f'<li>{ui("configured_empty",lang)}</li>'

    changes=[]
    for sid,snapshots in state['snapshots'].items():
        for snap in snapshots:
            if snap['changed']:
                changes.append(f'<li>{escape(state["sources"][sid]["title"])} · {ui("version",lang)} {snap["version"]} · <a href="/evidence/{snap["diff_hash"]}">{ui("view_diff",lang)}</a></li>')
    radar=state['legacy_references'].get('sayelf-algo-radar-x')
    radar_html=''
    if platform=='X':
        radar_keys={'CURRENT_REFERENCE_ONLY':'radar_changed','REVIEW_DUE':'radar_due','STALE':'radar_stale',
                    'SOURCE_MODIFIED_REVIEW_REQUIRED':'radar_modified','INVALID_FUTURE_DATE':'radar_date'}
        if radar:
            radar_status=ui(radar_keys.get(radar['status'],'radar_wait'),lang)
            radar_html=f'<section><h2>{ui("radar_title",lang)}</h2><p>{escape(radar_status)} · {"Source date" if english else "页面日期"} {escape(radar["source"]["published_at"])} · {radar["source"]["age_days"]} {"days old" if english else "天"}</p><p>{escape(radar["boundary"])}</p><details><summary>{ui("radar_details",lang)}</summary><p>{"Local revision" if english else "本地版本"} {escape(radar["source"]["revision"][:12])} · {escape(radar["source"]["locator"])}</p><pre style="white-space:pre-wrap;line-height:1.65">{escape(radar["excerpt"])}</pre><a href="/evidence/{radar["snapshot_hash"]}">{"View original snapshot" if english else "查看原文件快照"}</a></details></section>'
        elif os.environ.get('SAYELF_ALGO_RADAR_PATH'):
            radar_html=f'<section><h2>{ui("radar_title",lang)}</h2><p>{ui("radar_wait",lang)}</p><form method="post" action="/radar-check"><input type="hidden" name="token" value="{token}"><input type="hidden" name="lang" value="{lang}"><button>{ui("radar_read",lang)}</button></form></section>'
        else:
            radar_html=f'<section><h2>{ui("radar_title",lang)}</h2><p>{ui("radar_wait",lang)}</p><p class="muted">{ui("radar_config",lang)}</p></section>'

    brief_html=''
    if brief:
        citations=[]
        for action in brief['actions']:
            for proof in action['evidence']:
                citations.append(f'<li>{escape(action["section"])} · <a target="_blank" rel="noopener" href="{escape(proof["url"],quote=True)}">{ui("original",lang)}</a> · <a href="/evidence/{proof["snapshot_hash"]}">{ui("local_snapshot",lang)}</a> · {escape(proof["locator"])} · {ui("reviewed_at",lang)} {escape(proof["reviewed_at"][:10])}</li>')
        for change in brief['changes']:
            if change.get('diff_hash'):
                citations.append(f'<li>{escape(change["title"])} · <a target="_blank" rel="noopener" href="{escape(change["url"],quote=True)}">{ui("original",lang)}</a> · <a href="/evidence/{change["diff_hash"]}">{ui("change_record",lang)}</a> · {escape(change["status"])}</li>')
        for source in brief.get('sources',[]):
            snap=source.get('snapshot')
            proof=f' · <a href="/evidence/{snap["hash"]}">{ui("snapshot_open",lang)}</a> · <a href="/evidence/{snap["text_hash"]}">{ui("pending_locator",lang)}</a>' if snap else ''
            citations.append(f'<li>{escape(source["title"])} · <a target="_blank" rel="noopener" href="{escape(source["url"],quote=True)}">{ui("source_entry",lang)}</a>{proof} · {escape(source["status"])}</li>')
        brief_html=f'''<section id="generated-brief"><h2>{ui("brief_title",lang,platform=platform_label)}</h2>
        <p>{ui("brief_stats",lang,checked=brief['checked_count'],changes=brief['change_count'],updates=brief['source_update_count'],unavailable=brief['unavailable_count'])}</p>
        <p>{ui("brief_note",lang)}</p>
        <textarea id="brief-content" aria-label="{ui("brief_label",lang,platform=platform_label)}" readonly rows="24">{escape(brief['text'])}</textarea>
        <p><button type="button" data-copy-id="brief-content">{ui("copy",lang)}</button> <span data-copy-status aria-live="polite"></span></p>
        <details><summary>{ui("citations",lang)}</summary><ul>{''.join(citations) or f'<li>{ui("no_citations",lang)}</li>'}</ul></details></section>'''

    brief_query='&amp;brief=1' if brief else ''
    toggle_links=f'<nav class="language" aria-label="{ui("language",lang)}"><a href="/?platform={quote(platform)}&amp;lang=zh{brief_query}" lang="zh-CN">中文</a><a href="/?platform={quote(platform)}&amp;lang=en{brief_query}" lang="en">English</a></nav>'
    platform_form=f'<form method="post" action="/check"><input type="hidden" name="token" value="{token}"><input type="hidden" name="platform" value="{escape(platform,quote=True)}"><input type="hidden" name="lang" value="{lang}"><button>{ui("official_change",lang,platform=platform_label)}</button></form>'
    gate='VALID_SCOPED'
    policy_status=ui('scoped_valid' if envelope['policy_gate']==gate else 'await_review',lang)
    api_status=ui('scoped_valid' if envelope['api_gate']==gate else 'await_review',lang)
    return f'''<!doctype html><html lang="{'en' if english else 'zh-CN'}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" type="image/png" href="/static/logo.png"><title>{ui("page_title",lang)}</title>
    <style>body{{margin:0;background:#f2f5f2;color:#19392f;font:16px system-ui}}main{{max-width:1050px;margin:auto;padding:34px 24px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:center}}.brand{{display:flex;align-items:center;gap:18px}}.brand-logo{{width:88px;height:88px;object-fit:cover;border-radius:50%;border:2px solid #314b35;flex:none}}.header-tools{{display:flex;align-items:center;gap:14px}}.language{{display:flex;gap:8px}}h1{{font-size:32px;margin:8px 0}}.muted{{color:#63766e}}section,article{{background:white;border:1px solid #d9e3dc;border-radius:16px;padding:24px;margin:18px 0}}button{{border:0;border-radius:10px;background:#206849;color:white;padding:13px 20px;cursor:pointer}}.tag{{display:inline-block;background:#e0efe5;padding:5px 10px;border-radius:8px}}summary{{cursor:pointer;color:#206849}}a{{color:#206849}}li{{margin:12px 0}}details p{{line-height:1.6}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}textarea{{box-sizing:border-box;width:100%;min-height:420px;padding:14px;border:1px solid #bdccc1;border-radius:10px;background:#fbfdfb;color:#19392f;font:14px/1.6 ui-monospace,monospace;resize:vertical}}@media(max-width:700px){{.grid{{display:block}}header{{display:block}}.header-tools{{margin-top:18px;justify-content:space-between}}.brand-logo{{width:68px;height:68px}}}}</style><script src="/static/brief.js" defer></script>
    <main><header><div class="brand"><img class="brand-logo" src="/static/logo.png" alt="SAYELF 山野精灵 logo"><div><p class="muted">{ui("brand_title",lang)}</p><h1>{ui("page_title",lang)}</h1><p>{ui("page_subtitle",lang)}</p></div></div><div class="header-tools">{toggle_links}{platform_form}</div></header>
    {platform_nav(platform,lang)}<h2>{escape(platform_label)} · {ui("platform_current",lang)}</h2>
    <section><h2>{ui("health",lang)} · {health}</h2><p>{ui("policy",lang)}: {policy_status}　{ui("api",lang)}: {api_status}</p><p class="muted">{ui("monitor_note",lang)}</p></section>
    <div class="grid"><section><h2>{ui("attention",lang)}</h2><ul>{attention}</ul></section><section><h2>{ui("recent_changes",lang)}</h2><ul>{''.join(changes) or f'<li>{ui("no_changes",lang)}</li>'}</ul><details open><summary>{ui("sources_progress",lang)}</summary><ul>{sources}</ul></details></section></div>
    {radar_html}{brief_html}<h2>{ui("today",lang)}</h2>{''.join(cards) or f'<section>{ui("no_actions",lang)}</section>'}</main></html>'''

def handler(data,port,token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def valid_host(self): return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
        def send(self,code,raw,media='text/html; charset=utf-8'):
            self.send_response(code); self.send_header('Content-Type',media); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; img-src 'self'; script-src 'self'; connect-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if not self.valid_host(): self.send(403,b'Forbidden'); return
            parsed=urlsplit(self.path); path=parsed.path
            if path in ('/static/brief.js','/static/logo.png'):
                asset=Path(__file__).with_name('static')/('brief.js' if path.endswith('.js') else 'logo.png')
                raw=asset.read_bytes()
                self.send(200,raw,'text/javascript; charset=utf-8' if path.endswith('.js') else 'image/png'); return
            e=Engine(data)
            try:
                if path=='/':
                    params=parse_qs(parsed.query)
                    platform=params.get('platform',['X'])
                    if len(platform)!=1 or platform[0] not in PLATFORMS:
                        self.send(400,ui('invalid_platform',params.get('lang',['zh'])[0]).encode()); return
                    lang=params.get('lang',['zh'])
                    if len(lang)!=1 or lang[0] not in ('zh','en'):
                        self.send(400,ui('invalid_language').encode()); return
                    brief=None
                    if params.get('brief')==['1']:
                        from .briefs import build_brief
                        brief=build_brief(e,platform[0],lang[0])
                    self.send(200,render(e,token,brief,platform[0],lang[0]).encode())
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
            lang=form.get('lang',['zh'])
            if len(lang)!=1 or lang[0] not in ('zh','en'):
                self.send(400,ui('invalid_language').encode()); return
            lang=lang[0]
            selected=form.get('platform',['X'])
            if len(selected)!=1 or selected[0] not in PLATFORMS:
                self.send(400,b'Invalid platform');return
            platform=selected[0]
            e=Engine(data)
            try:
                if self.path=='/check':e.monitor(XAdapter() if platform=='X' else get_adapter(platform),force=True)
                else:
                    from .legacy_radar import LegacyRadarAdapter
                    radar_path=os.environ.get('SAYELF_ALGO_RADAR_PATH')
                    if not radar_path: raise FileNotFoundError('SAYELF_ALGO_RADAR_PATH is not configured')
                    LegacyRadarAdapter().collect(e,Path(radar_path).expanduser())
                language_suffix='&lang=en' if lang=='en' else ''
                destination=(f'/?brief=1{language_suffix}' if platform=='X' else f'/?platform={quote(platform)}&brief=1{language_suffix}') if self.path=='/check' else f'/?platform=X{language_suffix}'
                self.send_response(303); self.send_header('Location',destination); self.end_headers()
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
