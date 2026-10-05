"""Deterministic, evidence-bounded user brief generation."""

from datetime import datetime

ACTION_LABELS = {
    'MUST': '必须遵守',
    'SHOULD': '建议执行',
    'TEST': '待验证实验',
    'AVOID': '避免',
}
ACTION_LABELS_EN = {
    'MUST': 'Must', 'SHOULD': 'Should', 'TEST': 'Test', 'AVOID': 'Avoid',
}
SECTION_ORDER = ('POLICY', 'API', 'ALGORITHM', 'PRODUCT')
SECTION_LABELS = {
    'POLICY': '平台规则',
    'API': 'API 规则',
    'ALGORITHM': '推荐算法',
    'PRODUCT': '产品变化',
}
SECTION_LABELS_EN = {
    'POLICY': 'Platform Policies', 'API': 'API',
    'ALGORITHM': 'Recommendation Algorithm', 'PRODUCT': 'Product Updates',
}

PLATFORM_NAMES_EN = {
    'Instagram': 'Instagram', '小红书': 'Xiaohongshu', '视频号': 'WeChat Channels',
    '抖音': 'Douyin', '公众号': 'WeChat Official Accounts', '哔哩哔哩': 'Bilibili',
}

ACTION_TEXT_EN = {
    'statement': {
        '避免用网页脚本代替官方 API 操作 X': 'Do not automate X through website scripts instead of the official API.',
        '遵守接口速率限制；429 后等待窗口恢复': 'Respect API rate limits and wait for the window to reset after a 429 response.',
        '分析推荐变化时分别核对排序与可见性': 'When analyzing recommendations, verify ranking and visibility separately.',
        '将“互动计数比例等于排序收益”视为待检验假设': 'Treat “engagement-count ratios equal ranking gains” as a hypothesis to test.',
        '下游调用前单独核对计费与限流': 'Check pricing and rate limits separately before downstream API calls.',
    },
    'boundary': {
        '此条限制针对非 API 自动化，不能推出所有自动化都被禁止。': 'This restriction concerns non-API automation; it does not mean all automation is prohibited.',
        '文档描述当前接口限流行为，不保证额度长期固定；费率与限流分开。': 'The documentation describes current rate limits, which may change. Pricing and rate limits are separate.',
        '官方公开源码说明不能证明每个用户实时生产结果，也不能给出涨粉保证。': 'Public source code does not establish each user’s live production results or guarantee audience growth.',
        '源码描述预测概率或连续值加权，不能将原始互动次数乘以权重当成真实收益。': 'The source describes weights on predicted probabilities or continuous values; multiplying raw engagement counts by those weights does not yield actual ranking gains.',
        '产品介绍不替代实际账单或最新价格表，不提供费用额度保证。': 'A product overview does not replace an actual bill or current price list, and does not guarantee costs.',
    },
    'measure': {
        '非 API 账号操作路径数量=0': 'Number of non-API account-operation paths = 0',
        '超限绕过次数=0；记录429与恢复时间': 'Rate-limit bypasses = 0; record 429 responses and reset times',
        '记录排序与可见性证据是否分别可定位': 'Record whether ranking and visibility evidence can each be located',
        '用已有合法汇总数据比较预测假设；记录支持与反面证据，不因单次结果升级': 'Compare the hypothesis using existing lawful aggregate data; record supporting and counterevidence, and do not promote it based on one result',
        '预算依据的最新核验时间与费用偏差': 'Last verification time for budget assumptions and cost variance',
    },
}

ICEBERG_TEXT_EN = {
    'PHENOMENON': 'What is observable is the wording in this public document; this does not claim observed account-distribution results.',
    'MECHANISM': 'The rule or public mechanism bounds this recommendation; production behavior still requires independent verification.',
    'IMPACT': {
        '下游工具不得选择网页脚本执行账号动作。': 'Downstream tools must not use website scripts to perform account actions.',
        '下游调用方需要限流与重试边界。': 'Downstream callers need rate-limit and retry boundaries.',
        '影响解释推荐机制的下游分析，不能绕过政策。': 'This affects downstream recommendation analysis and does not override policy.',
        '对下游算法解释形成实验边界，不生产或发布内容。': 'This sets an experiment boundary for downstream algorithm interpretation; it does not create or publish content.',
        '需要下游预算检查；本情报工具不调用账号API。': 'Downstream use needs a budget check; this intelligence tool does not call account APIs.',
    },
}

BRIEF_EN = {
    'unknown': 'Unknown', 'not_checked': 'Not checked yet',
    'header': '[{platform} Platform Policy and Algorithm Evidence Brief]',
    'checked_at': 'Checked at: {time}',
    'scope': 'Scope: {platform} only. Includes only current reviewed conclusions with locatable public official sources.',
    'boundary': 'Boundary: unreviewed changes are not interpreted as policy or algorithm conclusions. This brief does not cover every platform policy or promise distribution results. Evidence is reviewed independently for each platform.',
    'run_summary': 'This check read {checked} sources; {changes} content changes; {updates} source-version updates; {unavailable} unavailable sources.',
    'no_run': 'This check has no available run record.',
    'findings': '[Findings in this check]',
    'change': '- {title}: {status} (version {version}, {date}); meaning has not been reviewed and is not treated as a current rule or recommendation.',
    'official_source': '  Official source: {url}',
    'unavailable_with_changes': '- No content changes were found in readable sources; unavailable sources have no conclusion.',
    'changes_with_actions': '- No content changes were found in the sources read this check; items below are still-valid reviewed conclusions, not new changes.',
    'no_run_with_actions': '- No results are available for this check; items below are still-valid reviewed conclusions.',
    'no_changes': '- No content changes were found in the sources read this check.',
    'unavailable': '- Temporarily inaccessible: {sources}. Their content is not assumed unchanged.',
    'applicable_boundary': '  Applicable boundary: {text}',
    'evidence': '  Official evidence: {title} ({url}; {locator}; reviewed {date}; snapshot v{version} / {hash})',
    'no_actions': 'There are no current reviewed conclusions cleared for citation.',
    'source_list': '[Official sources followed]',
    'snapshot': '  Latest snapshot: {time} / v{version} / {hash}; capture does not mean review approval.',
    'footer': 'This deterministic brief summarizes official-source status and reviewed conclusions. Review and edit it before sharing.',
    'source_unavailable': 'Temporarily inaccessible; official entry retained, with no conclusion for this check',
    'source_reviewed': 'Reviewed evidence supports a scoped conclusion',
    'source_pending': 'Snapshot captured; semantic review pending',
    'source_unchecked': 'Official source not checked yet',
    'content_pending': 'Content change awaiting review',
    'version_pending': 'Source file version changed; extracted text is unchanged, but related conclusions need review',
}


def localize_action_text(field, text, lang='zh'):
    """Translate reviewed product-authored X action text; leave source quotations intact."""
    if field == 'iceberg' and isinstance(text, tuple):
        layer, value = text
        if lang != 'en':
            return value
        if layer in ('ACTION', 'BOUNDARY', 'MEASURE'):
            return localize_action_text({'ACTION': 'statement'}.get(layer, layer.lower()), value, lang)
        if layer == 'PHENOMENON':
            return ICEBERG_TEXT_EN['PHENOMENON']
        if layer == 'MECHANISM':
            return ICEBERG_TEXT_EN['MECHANISM']
        if layer == 'IMPACT':
            return ICEBERG_TEXT_EN['IMPACT'].get(value, value)
        if layer == 'RELATION':
            statement = next((ACTION_TEXT_EN['statement'][k] for k in ACTION_TEXT_EN['statement'] if k in value), None)
            if statement:
                return f'This source supports “{statement}”; that relationship does not establish causality.'
        return value
    if lang != 'en':
        return text
    return ACTION_TEXT_EN.get(field, {}).get(text, text)


def _short_date(value,lang='zh'):
    if not value:
        return 'Unknown' if lang=='en' else '未知'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        return str(value)[:10]


def _current_official_evidence(action, state,platform='X'):
    evidence = []
    for item in action.get('evidence', []):
        source = state['sources'].get(item.get('source_id'))
        history = state['snapshots'].get(item.get('source_id'), [])
        latest = history[-1] if history else None
        if (not source or not latest or source.get('platform') != platform
                or source.get('classification') != 'Public'
                or source.get('provenance') != 'OFFICIAL'
                or item.get('hash') != latest.get('hash')
                or item.get('snapshot_version') != latest.get('version')
                or item.get('url') != source.get('url')
                or not item.get('locator') or not item.get('reviewed_at')):
            continue
        if source.get('kind') not in SECTION_LABELS:
            continue
        evidence.append({
            'kind': source['kind'],
            'title': source['title'],
            'url': item['url'],
            'locator': item['locator'],
            'reviewed_at': item['reviewed_at'],
            'captured_at': item.get('captured_at'),
            'snapshot_version': item['snapshot_version'],
            'hash': item['hash'],
            'snapshot_hash': item['hash'],
        })
    return evidence


def build_brief(engine,platform='X',lang='zh'):
    """Compile this platform's current verified conclusions and source status only."""
    lang = 'en' if lang == 'en' else 'zh'
    english = lang == 'en'
    text = lambda key, **kwargs: BRIEF_EN[key].format(**kwargs) if english else None
    platform_label = PLATFORM_NAMES_EN.get(platform, platform) if english else platform
    section_labels = SECTION_LABELS_EN if english else SECTION_LABELS
    action_labels = ACTION_LABELS_EN if english else ACTION_LABELS
    envelope = engine.envelope(platform)
    state = engine.state()
    run = next((r for r in reversed(state['runs']) if r.get('platform')==platform or
                (not r.get('platform') and any(state['sources'].get(x.get('source_id'),{}).get('platform')==platform for x in r.get('results',[])))),None)
    results = run.get('results', []) if run else []

    changes = []
    unavailable = []
    checked = []
    for result in results:
        source = state['sources'].get(result.get('source_id'), {})
        if source.get('platform')!=platform:continue
        title = source.get('title', result.get('source_id', 'Unknown source' if english else '未知来源'))
        if result.get('status') == 'UNAVAILABLE':
            unavailable.append(title)
            continue
        if result.get('status') != 'CAPTURED':
            continue
        checked.append(title)
        snapshot = next((item for item in reversed(state['snapshots'].get(result.get('source_id'), []))
                        if item.get('hash') == result.get('hash')), None)
        if not snapshot:
            continue
        if snapshot.get('changed'):
            changes.append({
                'title': title,
                'kind': source.get('kind', 'Unknown' if english else '未知'),
                'version': snapshot.get('version'),
                'time': snapshot.get('time'),
                'url': source.get('url', ''),
                'diff_hash': snapshot.get('diff_hash'),
                'status': BRIEF_EN['content_pending'] if english else '正文变化待审核',
            })
        elif snapshot.get('previous_hash') and snapshot.get('previous_hash') != snapshot.get('hash'):
            changes.append({
                'title': title,
                'kind': source.get('kind', 'Unknown' if english else '未知'),
                'version': snapshot.get('version'),
                'time': snapshot.get('time'),
                'url': source.get('url', ''),
                'diff_hash': snapshot.get('diff_hash'),
                'status': BRIEF_EN['version_pending'] if english else '原文件版本变化，提取正文未见变化；关联结论仍待复核',
            })

    actions = []
    for action in envelope.get('actions', []):
        if (action.get('platform') != platform or action.get('status') != 'ACTIVE'
                or action.get('confidence') != 'VERIFIED_OFFICIAL'):
            continue
        evidence = _current_official_evidence(action, state,platform)
        if not evidence:
            continue
        evidence_kinds = {item['kind'] for item in evidence}
        kind = next((item for item in SECTION_ORDER if item in evidence_kinds), None)
        if not kind:
            continue
        boundary = action.get('iceberg', {}).get('BOUNDARY', {}).get('text') or action.get('rationale', '')
        actions.append({
            'kind': kind,
            'section': section_labels[kind],
            'action_class': action.get('action_class', ''),
            'action_label': action_labels.get(action.get('action_class'), 'Review' if english else '待复核'),
            'statement': localize_action_text('statement', action.get('statement', ''), lang),
            'boundary': localize_action_text('boundary', boundary, lang),
            'evidence': evidence,
        })
    actions.sort(key=lambda item: (SECTION_ORDER.index(item['kind']), item['statement']))

    run_time = run.get('time') if run else None
    if english:
        lines = [
            text('header', platform=platform_label),
            text('checked_at', time=run_time or BRIEF_EN['not_checked']),
            text('scope', platform=platform_label),
            text('boundary'),
        ]
    else:
        lines = [
            f'【{platform} 平台规则与算法证据简报】',
            f"检查时间：{run_time or '尚未检查'}",
            f'范围：仅 {platform}；只汇总当前有效、经审核并有官方公开来源定位的结论。',
            '边界：未审核变化不解释为规则或算法结论；本简报不代表平台全部政策，也不承诺分发结果。各平台证据独立核验。',
        ]
    changed_count = sum(c['status'] in ('正文变化待审核', BRIEF_EN['content_pending']) for c in changes)
    if results:
        if english:
            lines.append(text('run_summary', checked=len(checked), changes=changed_count, updates=len(changes), unavailable=len(unavailable)))
        else:
            lines.append(f'本轮检查：成功读取 {len(checked)} 个来源；正文变化 {changed_count} 项；来源版本变化 {len(changes)} 项；不可用 {len(unavailable)} 个来源。')
    else:
        lines.append(text('no_run') if english else '本轮检查：暂无可用的检查记录。')

    lines.append('')
    lines.append(text('findings') if english else '【本轮发现】')
    if changes:
        for change in changes:
            if english:
                lines.append(text('change', title=change['title'], status=change['status'], version=change['version'], date=_short_date(change['time'],lang)))
                lines.append(text('official_source', url=change['url']))
            else:
                lines.append(f"- {change['title']}：{change['status']}（版本 {change['version']}，{_short_date(change['time'])}）；语义尚未审核，不作为现行规则或行动建议。")
                lines.append(f"  官方来源：{change['url']}")
    elif unavailable:
        lines.append(text('unavailable_with_changes') if english else '- 可读取来源中未发现正文变化；不可用来源尚无结论。')
    elif results:
        lines.append(text('changes_with_actions') if english else '- 本轮读取到的来源未发现正文变化；下方内容是仍有效的已核验结论，不代表新变化。')
    else:
        lines.append(text('no_run_with_actions') if english else '- 尚无本轮检查结果；下方内容是仍有效的已核验结论。')
    if unavailable:
        lines.append(text('unavailable', sources=', '.join(unavailable)) if english else '- 暂时不可读取：' + '、'.join(unavailable) + '。相关内容不据此推断为未变化。')

    for kind in SECTION_ORDER:
        section_actions = [item for item in actions if item['kind'] == kind]
        if not section_actions:
            continue
        lines.extend(['', f'[{section_labels[kind]}]' if english else f'【{SECTION_LABELS[kind]}】'])
        for action in section_actions:
            lines.append(f"- [{action['action_label']}] {action['statement']}" if english else f"- 【{action['action_label']}】{action['statement']}")
            if action['boundary']:
                lines.append(text('applicable_boundary', text=action['boundary']) if english else f"  适用边界：{action['boundary']}")
            for proof in action['evidence']:
                if english:
                    lines.append(text('evidence', title=proof['title'], url=proof['url'], locator=proof['locator'], date=_short_date(proof['reviewed_at'],lang), version=proof['snapshot_version'], hash=proof['hash'][:12]))
                else:
                    lines.append(f"  官方依据：{proof['title']}（{proof['url']}；{proof['locator']}；核验 {_short_date(proof['reviewed_at'])}；快照 v{proof['snapshot_version']} / {proof['hash'][:12]}）")

    if not actions:
        lines.extend(['', text('no_actions') if english else '当前没有可公开引用的有效审核结论。'])
    lines.extend(['', text('source_list') if english else '【官方来源关注清单】'])
    sources=[]
    for sid,source in state['sources'].items():
        if source['platform']!=platform or source['provenance']!='OFFICIAL':continue
        history=state['snapshots'].get(sid,[]);latest=history[-1] if history else None
        failed=any(i['source_id']==sid and i['kind']=='SOURCE_UNAVAILABLE' and i['status']=='OPEN' for i in state['incidents'].values())
        reviewed=any(a.get('platform')==platform and a.get('status')=='ACTIVE' and
                     any(p['hash']==latest['hash'] and p['source_id']==sid for p in a.get('evidence',[]))
                     for a in state['actions'].values()) if latest else False
        status=(BRIEF_EN['source_unavailable'] if failed else BRIEF_EN['source_reviewed'] if reviewed else BRIEF_EN['source_pending'] if latest else BRIEF_EN['source_unchecked']) if english else ('暂不可读取，关注官方入口；尚无本轮结论' if failed else '已有经定位核验结论（限定主题）' if reviewed else '已有快照，规则语义待审核' if latest else '待检查官方原文')
        sources.append({'id':sid,'title':source['title'],'url':source['url'],'status':status,'snapshot':latest})
        lines.append(f'- {source["title"]}: {status}; official source {source["url"]}' if english else f'- {source["title"]}：{status}；官方入口 {source["url"]}')
        if latest:
            lines.append(text('snapshot', time=latest['time'], version=latest['version'], hash=latest['hash'][:12]) if english else f'  最近快照：{latest["time"]} / v{latest["version"]} / {latest["hash"][:12]}；获取不等于审核通过。')
    lines.extend(['', text('footer') if english else '本简报确定性整理官方来源状态与已审核结论；可复制后人工复核、编辑和发布。'])
    return {
        'platform': platform,
        'sources':sources,
        'run_time': run_time,
        'checked_count': len(checked),
        'change_count': changed_count,
        'source_update_count': len(changes),
        'unavailable_count': len(unavailable),
        'actions': actions,
        'changes': changes,
        'unavailable': unavailable,
        'text': '\n'.join(lines),
    }
