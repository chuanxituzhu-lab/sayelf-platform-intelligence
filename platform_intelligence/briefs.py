"""Deterministic, evidence-bounded user brief generation."""

from datetime import datetime

ACTION_LABELS = {
    'MUST': '必须遵守',
    'SHOULD': '建议执行',
    'TEST': '待验证实验',
    'AVOID': '避免',
}
SECTION_ORDER = ('POLICY', 'API', 'ALGORITHM', 'PRODUCT')
SECTION_LABELS = {
    'POLICY': '平台规则',
    'API': 'API 规则',
    'ALGORITHM': '推荐算法',
    'PRODUCT': '产品变化',
}


def _short_date(value):
    if not value:
        return '未知'
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


def build_brief(engine,platform='X'):
    """Compile this platform's current verified conclusions and source status only."""
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
        title = source.get('title', result.get('source_id', '未知来源'))
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
                'kind': source.get('kind', '未知'),
                'version': snapshot.get('version'),
                'time': snapshot.get('time'),
                'url': source.get('url', ''),
                'diff_hash': snapshot.get('diff_hash'),
                'status': '正文变化待审核',
            })
        elif snapshot.get('previous_hash') and snapshot.get('previous_hash') != snapshot.get('hash'):
            changes.append({
                'title': title,
                'kind': source.get('kind', '未知'),
                'version': snapshot.get('version'),
                'time': snapshot.get('time'),
                'url': source.get('url', ''),
                'diff_hash': snapshot.get('diff_hash'),
                'status': '原文件版本变化，提取正文未见变化；关联结论仍待复核',
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
            'section': SECTION_LABELS[kind],
            'action_class': action.get('action_class', ''),
            'action_label': ACTION_LABELS.get(action.get('action_class'), '待复核'),
            'statement': action.get('statement', ''),
            'boundary': boundary,
            'evidence': evidence,
        })
    actions.sort(key=lambda item: (SECTION_ORDER.index(item['kind']), item['statement']))

    run_time = run.get('time') if run else None
    lines = [
        f'【{platform} 平台规则与算法证据简报】',
        f"检查时间：{run_time or '尚未检查'}",
        f'范围：仅 {platform}；只汇总当前有效、经审核并有官方公开来源定位的结论。',
        '边界：未审核变化不解释为规则或算法结论；本简报不代表平台全部政策，也不承诺分发结果。各平台证据独立核验。',
    ]
    if results:
        lines.append(f'本轮检查：成功读取 {len(checked)} 个来源；正文变化 {sum(c["status"] == "正文变化待审核" for c in changes)} 项；来源版本变化 {len(changes)} 项；不可用 {len(unavailable)} 个来源。')
    else:
        lines.append('本轮检查：暂无可用的检查记录。')

    lines.append('')
    lines.append('【本轮发现】')
    if changes:
        for change in changes:
            lines.append(f"- {change['title']}：{change['status']}（版本 {change['version']}，{_short_date(change['time'])}）；语义尚未审核，不作为现行规则或行动建议。")
            lines.append(f"  官方来源：{change['url']}")
    elif unavailable:
        lines.append('- 可读取来源中未发现正文变化；不可用来源尚无结论。')
    elif results:
        lines.append('- 本轮读取到的来源未发现正文变化；下方内容是仍有效的已核验结论，不代表新变化。')
    else:
        lines.append('- 尚无本轮检查结果；下方内容是仍有效的已核验结论。')
    if unavailable:
        lines.append('- 暂时不可读取：' + '、'.join(unavailable) + '。相关内容不据此推断为未变化。')

    for kind in SECTION_ORDER:
        section_actions = [item for item in actions if item['kind'] == kind]
        if not section_actions:
            continue
        lines.extend(['', f'【{SECTION_LABELS[kind]}】'])
        for action in section_actions:
            lines.append(f"- 【{action['action_label']}】{action['statement']}")
            if action['boundary']:
                lines.append(f"  适用边界：{action['boundary']}")
            for proof in action['evidence']:
                lines.append(f"  官方依据：{proof['title']}（{proof['url']}；{proof['locator']}；核验 {_short_date(proof['reviewed_at'])}；快照 v{proof['snapshot_version']} / {proof['hash'][:12]}）")

    if not actions:
        lines.extend(['', '当前没有可公开引用的有效审核结论。'])
    lines.extend(['','【官方来源关注清单】'])
    sources=[]
    for sid,source in state['sources'].items():
        if source['platform']!=platform or source['provenance']!='OFFICIAL':continue
        history=state['snapshots'].get(sid,[]);latest=history[-1] if history else None
        failed=any(i['source_id']==sid and i['kind']=='SOURCE_UNAVAILABLE' and i['status']=='OPEN' for i in state['incidents'].values())
        reviewed=any(a.get('platform')==platform and a.get('status')=='ACTIVE' and
                     any(p['hash']==latest['hash'] and p['source_id']==sid for p in a.get('evidence',[]))
                     for a in state['actions'].values()) if latest else False
        status='暂不可读取，关注官方入口；尚无本轮结论' if failed else '已有经定位核验结论（限定主题）' if reviewed else '已有快照，规则语义待审核' if latest else '待检查官方原文'
        sources.append({'id':sid,'title':source['title'],'url':source['url'],'status':status,'snapshot':latest})
        lines.append(f'- {source["title"]}：{status}；官方入口 {source["url"]}')
        if latest:lines.append(f'  最近快照：{latest["time"]} / v{latest["version"]} / {latest["hash"][:12]}；获取不等于审核通过。')
    lines.extend(['', '本简报确定性整理官方来源状态与已审核结论；可复制后人工复核、编辑和发布。'])
    return {
        'platform': platform,
        'sources':sources,
        'run_time': run_time,
        'checked_count': len(checked),
        'change_count': sum(item['status'] == '正文变化待审核' for item in changes),
        'source_update_count': len(changes),
        'unavailable_count': len(unavailable),
        'actions': actions,
        'changes': changes,
        'unavailable': unavailable,
        'text': '\n'.join(lines),
    }
