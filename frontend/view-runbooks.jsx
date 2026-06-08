/* Runbook orchestration view — wired to /agent/v1/runbook/* */
const { useState: useStateR, useEffect: useEffectR } = React;

const RB_BLANK = {
  runbookId: null, title: '', service: 'Wise', scenario: '模型任务', severity: 'P2',
  status: 'draft', version: 'v1', owner: '', tags: '', trigger: '', summary: '',
  verification: '', escalation: '', riskControls: '', relatedKnowledge: '', steps: [blankStep(1)],
};

function blankStep(order) {
  return { order, title: '新的诊断步骤', actionType: 'check', instruction: '', evidenceRequired: '', toolName: '', expectedResult: '', riskLevel: 'low' };
}

function RunbooksView({ toast }) {
  const [list, setList] = useStateR([]);
  const [activeId, setActiveId] = useStateR(null);
  const [statusFilter, setStatusFilter] = useStateR('');
  const [search, setSearch] = useStateR('');
  const [rb, setRb] = useStateR(RB_BLANK);
  const [saving, setSaving] = useStateR(false);

  const setField = (k, v) => setRb((r) => ({ ...r, [k]: v }));

  function loadList(filters, selectFirst) {
    return API.runbookList(filters || {}).then((data) => {
      setList(data || []);
      if (selectFirst && (data || []).length) selectRunbook(data[0].runbookId);
      return data;
    }).catch((e) => toast(e.message));
  }

  useEffectR(() => { loadList({}, true); }, []);

  function selectRunbook(id) {
    setActiveId(id);
    API.runbookDetail(id).then((d) => {
      setRb({
        runbookId: d.runbookId, title: d.title || '', service: d.service || 'Wise',
        scenario: d.scenario || '模型任务', severity: d.severity || 'P2', status: d.status || 'draft',
        version: d.version || 'v1', owner: d.owner || '', tags: H.joinList(d.tags),
        trigger: d.trigger || '', summary: d.summary || '', verification: d.verification || '',
        escalation: d.escalation || '', riskControls: H.joinList(d.riskControls),
        relatedKnowledge: H.joinList(d.relatedKnowledge),
        steps: (d.steps && d.steps.length ? d.steps : [blankStep(1)]).map((s, i) => ({ ...blankStep(i + 1), ...s, order: i + 1 })),
      });
    }).catch((e) => toast(e.message));
  }

  function newRunbook() {
    setActiveId(null);
    setRb({ ...RB_BLANK, steps: [blankStep(1)] });
    toast('已切换到新增 Runbook');
  }

  function updateStep(idx, key, value) {
    setRb((r) => ({ ...r, steps: r.steps.map((s, i) => (i === idx ? { ...s, [key]: value } : s)) }));
  }
  function addStep() {
    setRb((r) => ({ ...r, steps: [...r.steps, blankStep(r.steps.length + 1)] }));
  }
  function removeStep(idx) {
    setRb((r) => {
      const steps = r.steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, order: i + 1 }));
      return { ...r, steps: steps.length ? steps : [blankStep(1)] };
    });
  }

  async function save() {
    if (!rb.title.trim()) { toast('请填写标题'); return; }
    setSaving(true);
    try {
      const saved = await API.runbookSave({
        runbookId: rb.runbookId,
        title: rb.title.trim(), service: rb.service, scenario: rb.scenario.trim() || '模型任务',
        severity: rb.severity, status: rb.status, owner: rb.owner.trim() || null,
        version: rb.version.trim() || 'v1', trigger: rb.trigger.trim() || null,
        summary: rb.summary.trim() || null, verification: rb.verification.trim() || null,
        escalation: rb.escalation.trim() || null, riskControls: H.splitList(rb.riskControls),
        tags: H.splitList(rb.tags), relatedKnowledge: H.splitList(rb.relatedKnowledge),
        steps: rb.steps.map((s, i) => ({ ...s, order: i + 1 })),
      });
      await loadList({}, false);
      if (saved?.runbookId) selectRunbook(saved.runbookId);
      toast('Runbook 已保存');
    } catch (e) {
      toast(e.message || '保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(status) {
    if (!rb.runbookId) { toast('请先保存 Runbook'); return; }
    try {
      await API.runbookStatus(rb.runbookId, status);
      setField('status', status);
      await loadList({}, false);
      toast(`状态已切换为「${STATUS_LABEL[status] || status}」`);
    } catch (e) {
      toast(e.message || '状态更新失败');
    }
  }

  const filtered = list.filter((r) =>
    (!statusFilter || r.status === statusFilter) &&
    (!search || `${r.title}${(r.tags || []).join(' ')}`.toLowerCase().includes(search.toLowerCase())));

  const lifecycle = [
    { k: 'draft', label: '转草稿' }, { k: 'review', label: '提交审核' },
    { k: 'published', label: '发布' }, { k: 'archived', label: '归档' },
  ];
  const relatedKnowledge = H.splitList(rb.relatedKnowledge);
  const riskControls = H.splitList(rb.riskControls);

  return (
    <div className="rb-layout">
      <aside className="rb-aside">
        <div className="aside-block-head" style={{ marginBottom: 12 }}>
          <Icon name="runbook" size={14} /> Runbook 流程
          <span className="mono count">{list.length}</span>
        </div>
        <div className="search-wrap" style={{ marginBottom: 9 }}>
          <Icon name="search" size={14} />
          <input className="field" placeholder="搜索标题或标签" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className="field" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ marginBottom: 12 }}>
          <option value="">全部状态</option>
          <option value="published">已发布</option>
          <option value="review">待审核</option>
          <option value="draft">草稿</option>
          <option value="archived">已归档</option>
        </select>
        <div className="rb-list">
          {filtered.length === 0 && <Empty icon="runbook">暂无 Runbook</Empty>}
          {filtered.map((r) => (
            <button key={r.runbookId} className={`rb-item ${activeId === r.runbookId ? 'active' : ''}`} onClick={() => selectRunbook(r.runbookId)}>
              <div className="rb-item-top">
                <Sev level={r.severity} />
                <strong>{r.title}</strong>
              </div>
              <div className="rb-item-foot">
                <Lifecycle status={r.status} />
                <span className="badge neutral" style={{ fontSize: 10 }}>{r.service}</span>
                <span className="mono muted" style={{ fontSize: 10, marginLeft: 'auto' }}>{r.stepCount || 0} 步 · {r.version}</span>
              </div>
            </button>
          ))}
        </div>
      </aside>

      <div className="rb-main">
        <div className="rb-grid">
          <Card className="rb-editor">
            <div className="kb-toolbar">
              <div>
                <Kicker>{rb.runbookId ? '编辑 Runbook' : '新增 Runbook'}</Kicker>
                <h3 style={{ margin: '3px 0 0', fontSize: 15 }}>{rb.title || '诊断流程元数据'}</h3>
                <div className="mono muted" style={{ fontSize: 11, marginTop: 3 }}>{rb.runbookId || '尚未保存'}{rb.owner ? ` · ${rb.owner}` : ''}</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <Btn icon="plus" size="sm" onClick={newRunbook}>新建</Btn>
                <Btn variant="primary" size="sm" icon="check" disabled={saving} onClick={save}>{saving ? '保存中' : '保存'}</Btn>
              </div>
            </div>

            <div className="rb-editor-body">
              <div className="rb-fields">
                <label className="lbl"><span>标题</span><input className="field" value={rb.title} onChange={(e) => setField('title', e.target.value)} /></label>
                <label className="lbl"><span>服务</span><select className="field" value={rb.service} onChange={(e) => setField('service', e.target.value)}><option>Wise</option><option>MTP</option><option>MEP</option></select></label>
                <label className="lbl"><span>场景</span><input className="field" value={rb.scenario} onChange={(e) => setField('scenario', e.target.value)} /></label>
                <label className="lbl"><span>严重级别</span><select className="field" value={rb.severity} onChange={(e) => setField('severity', e.target.value)}><option>P0</option><option>P1</option><option>P2</option><option>P3</option><option>P4</option></select></label>
                <label className="lbl"><span>版本</span><input className="field mono" value={rb.version} onChange={(e) => setField('version', e.target.value)} /></label>
                <label className="lbl"><span>负责人</span><input className="field" value={rb.owner} onChange={(e) => setField('owner', e.target.value)} /></label>
                <label className="lbl span-2"><span>触发条件</span><textarea className="field" rows="2" value={rb.trigger} onChange={(e) => setField('trigger', e.target.value)} /></label>
                <label className="lbl span-2"><span>流程摘要</span><textarea className="field" rows="2" value={rb.summary} onChange={(e) => setField('summary', e.target.value)} /></label>
                <label className="lbl"><span>验证方式</span><textarea className="field" rows="2" value={rb.verification} onChange={(e) => setField('verification', e.target.value)} /></label>
                <label className="lbl"><span>升级路径</span><textarea className="field" rows="2" value={rb.escalation} onChange={(e) => setField('escalation', e.target.value)} /></label>
                <label className="lbl span-2"><span>风险护栏（逗号分隔）</span><input className="field" value={rb.riskControls} onChange={(e) => setField('riskControls', e.target.value)} /></label>
                <label className="lbl span-2"><span>关联知识（逗号分隔）</span><input className="field mono" value={rb.relatedKnowledge} onChange={(e) => setField('relatedKnowledge', e.target.value)} /></label>
              </div>

              <div className="rb-step-editor">
                <div className="rb-step-head">
                  <div><Kicker>Executable Flow</Kicker><h4>诊断步骤</h4></div>
                  <Btn icon="plus" size="sm" onClick={addStep}>新增步骤</Btn>
                </div>
                <div className="rb-steps">
                  {rb.steps.map((s, idx) => (
                    <div key={idx} className="rb-step">
                      <span className="step-no">{idx + 1}</span>
                      <div className="rb-step-body" style={{ display: 'grid', gap: 8 }}>
                        <div className="rb-step-title" style={{ gap: 8 }}>
                          <input className="field" style={{ flex: 1 }} value={s.title} onChange={(e) => updateStep(idx, 'title', e.target.value)} />
                          <button className="btn ghost sm icon" title="删除步骤" onClick={() => removeStep(idx)}><Icon name="trash" size={14} /></button>
                        </div>
                        <div className="rb-step-grid">
                          <select className="field" value={s.actionType} onChange={(e) => updateStep(idx, 'actionType', e.target.value)}>
                            {Object.entries(H.ACTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                          </select>
                          <select className="field" value={s.riskLevel} onChange={(e) => updateStep(idx, 'riskLevel', e.target.value)}>
                            <option value="low">低风险</option><option value="medium">中风险</option><option value="high">高风险</option>
                          </select>
                          <input className="field mono" placeholder="工具，如 metrics.gpu_memory" value={s.toolName} onChange={(e) => updateStep(idx, 'toolName', e.target.value)} />
                        </div>
                        <textarea className="field" rows="2" placeholder="操作说明" value={s.instruction} onChange={(e) => updateStep(idx, 'instruction', e.target.value)} />
                        <div className="rb-step-grid">
                          <input className="field" placeholder="所需证据" value={s.evidenceRequired} onChange={(e) => updateStep(idx, 'evidenceRequired', e.target.value)} />
                          <input className="field" placeholder="预期结果" value={s.expectedResult} onChange={(e) => updateStep(idx, 'expectedResult', e.target.value)} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <div className="rb-side-col">
            <Card>
              <CardHead kicker="Current Flow" title="执行视图" />
              <div className="card-pad rb-preview">
                <div className="rb-prev-meta">
                  <div><span className="kicker">服务 / 场景</span><div className="rb-prev-val">{rb.service} · {rb.scenario || '未设置场景'}</div></div>
                  <Sev level={rb.severity} />
                </div>
                {rb.trigger && (
                  <div className="rb-prev-trigger">
                    <Icon name="bolt" size={13} /><span>{rb.trigger}</span>
                  </div>
                )}
                <ol className="rb-exec">
                  {rb.steps.map((s, i) => (
                    <li key={i} className={`rb-exec-step ${s.riskLevel === 'high' ? 'high' : ''}`}>
                      <span className="rb-exec-no">{i + 1}</span>
                      <div>
                        <div className="rb-exec-title">{s.title} <Risk level={s.riskLevel} /></div>
                        {s.riskLevel === 'high' && <div className="rb-guard"><Icon name="shield" size={12} /> 高风险动作需人工确认后执行</div>}
                      </div>
                    </li>
                  ))}
                </ol>
                {relatedKnowledge.length > 0 && (
                  <div className="rb-related">
                    <span className="kicker">关联知识</span>
                    {relatedKnowledge.map((k) => <code key={k} className="mono rb-rel-chip">{k}</code>)}
                  </div>
                )}
              </div>
            </Card>

            <Card>
              <CardHead kicker="Lifecycle" title="状态流转" />
              <div className="card-pad">
                <div style={{ marginBottom: 12 }}><Lifecycle status={rb.status} /></div>
                <div className="lifecycle-actions wide">
                  {lifecycle.map((l) => (
                    <button key={l.k} className={`lc-btn ${rb.status === l.k ? 'on' : ''}`} onClick={() => changeStatus(l.k)}>{l.label}</button>
                  ))}
                </div>
                {riskControls.length > 0 && (
                  <div className="rb-guard-box">
                    <Icon name="shield" size={14} />
                    <div><b>风险护栏</b>{riskControls.join(' · ')}</div>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

window.RunbooksView = RunbooksView;
