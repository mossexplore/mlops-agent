/* Quality feedback-loop view — wired to /agent/v1/quality/* */
const { useState: useStateQ, useEffect: useEffectQ } = React;

const QSTATUS = {
  pending: { l: '待标注', k: 'warn' },
  reviewing: { l: '标注中', k: 'info' },
  resolved: { l: '已处理', k: 'ok' },
  converted: { l: '已转用例', k: 'ok' },
  annotated: { l: '已标注', k: 'info' },
};
const QPENDING = new Set(['pending', 'reviewing']);

function QualityView({ toast }) {
  const [data, setData] = useStateQ(null);
  const [loading, setLoading] = useStateQ(true);
  const [error, setError] = useStateQ('');
  const [draft, setDraft] = useStateQ({}); // per-feedback annotation drafts
  const [caseForm, setCaseForm] = useStateQ({ title: '', query: '', required: '', forbidden: '' });
  const [runForm, setRunForm] = useStateQ({ name: 'baseline quality run', variant: 'baseline', promptVersion: '' });
  const [expForm, setExpForm] = useStateQ({ name: '', variants: '', split: '', metric: 'satisfactionRate' });

  function load() {
    setLoading(true);
    setError('');
    API.qualityDashboard().then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }
  useEffectQ(() => { load(); }, []);

  if (loading && !data) return <div className="view-pad"><Empty icon="quality">正在加载质量数据…</Empty></div>;
  if (error) return <div className="view-pad"><Empty icon="alert">{error}</Empty></div>;
  if (!data) return null;

  const m = data.metrics || {};
  const metricTiles = [
    { label: '知识命中率', value: H.pct(m.knowledgeHitRate, 1), unit: '%' },
    { label: '回答满意率', value: H.pct(m.satisfactionRate, 1), unit: '%' },
    { label: '点踩率', value: H.pct(m.unlikeRate, 1), unit: '%' },
    { label: '无答案率', value: H.pct(m.noAnswerRate, 1), unit: '%' },
    { label: '重复提问率', value: H.pct(m.repeatQuestionRate, 1), unit: '%' },
    { label: '平均耗时', value: String(m.avgLatencyMs || 0), unit: 'ms' },
  ];
  const queue = data.feedback || [];
  const cases = data.evalCases || [];
  const runs = data.evalRuns || [];
  const experiments = data.experiments || [];
  const pendingCount = queue.filter((x) => QPENDING.has(x.status)).length;

  function setDraftFor(id, patch) {
    setDraft((d) => ({ ...d, [id]: { ...d[id], ...patch } }));
  }

  async function annotate(f) {
    const d = draft[f.answerMessageId] || {};
    try {
      await API.qualityFeedbackAnnotate({
        answerMessageId: f.answerMessageId, userId: f.userId, conversationId: f.conversationId,
        qualityReason: d.reason || f.qualityReason, annotation: d.annotation ?? f.annotation ?? '',
        status: 'resolved', reviewer: 'admin',
      });
      toast('已标注反馈原因');
      load();
    } catch (e) { toast(e.message || '标注失败'); }
  }

  async function deriveCase(f) {
    try {
      await API.qualityEvalCaseFromFeedback({ answerMessageId: f.answerMessageId, userId: f.userId, conversationId: f.conversationId });
      toast('已沉淀为评测用例');
      load();
    } catch (e) { toast(e.message || '沉淀失败'); }
  }

  async function saveCase() {
    if (!caseForm.title.trim() || !caseForm.query.trim()) { toast('请填写用例标题与问题'); return; }
    try {
      await API.qualityEvalCaseSave({
        title: caseForm.title.trim(), query: caseForm.query.trim(),
        requiredSteps: H.splitList(caseForm.required), forbiddenContent: H.splitList(caseForm.forbidden),
        tags: [], status: 'active',
      });
      setCaseForm({ title: '', query: '', required: '', forbidden: '' });
      toast('评测用例已保存');
      load();
    } catch (e) { toast(e.message || '保存失败'); }
  }

  async function runEval() {
    try {
      const run = await API.qualityEvalRun({
        name: runForm.name.trim() || 'eval run', variant: runForm.variant.trim() || 'baseline',
        promptVersion: runForm.promptVersion.trim() || null,
      });
      toast(`评测完成：通过率 ${H.pct(run.passRate)}%`);
      load();
    } catch (e) { toast(e.message || '评测失败'); }
  }

  async function saveExperiment() {
    if (!expForm.name.trim()) { toast('请填写实验名称'); return; }
    const variants = H.splitList(expForm.variants);
    const ratios = H.splitList(expForm.split).map(Number);
    const trafficSplit = {};
    variants.forEach((v, i) => { trafficSplit[v] = ratios[i] || 0; });
    try {
      await API.qualityExperimentSave({
        name: expForm.name.trim(), variants, trafficSplit, primaryMetric: expForm.metric, status: 'draft',
      });
      setExpForm({ name: '', variants: '', split: '', metric: 'satisfactionRate' });
      toast('实验配置已保存');
      load();
    } catch (e) { toast(e.message || '保存失败'); }
  }

  return (
    <div className="view-pad fade-in view-fit">
      <div className="view-wrap">
        <div className="metric-grid q-metric-grid">
          {metricTiles.map((t) => (
            <div key={t.label} className="q-metric">
              <div className="qm-label">{t.label}</div>
              <div className="qm-val">{t.value}{t.unit && <small>{t.unit}</small>}</div>
            </div>
          ))}
        </div>

        <div className="ops-grid-2 grid-flex">
          <Card>
            <CardHead kicker="Annotation Queue" title="点踩反馈工作台">
              <Badge kind="warn">{pendingCount} 待处理</Badge>
            </CardHead>
            <div className="card-pad">
              {queue.length === 0 ? <Empty icon="thumb">暂无点踩反馈</Empty> : (
                <div className="q-queue list-scroll">
                  {queue.map((f) => {
                    const st = QSTATUS[f.status] || QSTATUS.pending;
                    const d = draft[f.answerMessageId] || {};
                    return (
                      <div key={f.answerMessageId} className="q-fb">
                        <div className="q-fb-top">
                          <code className="mono">{f.userId}</code>
                          <span className="mono muted" style={{ fontSize: 11 }}>{f.timestamp}</span>
                          <span style={{ marginLeft: 'auto' }} className={`badge ${st.k}`}>{st.l}</span>
                        </div>
                        <div className="q-fb-q">{f.query || '未记录问题'}</div>
                        {f.answer && <div className="q-fb-a">{f.answer}</div>}
                        <div className="q-fb-foot" style={{ flexWrap: 'wrap', gap: 8 }}>
                          <select className="field" style={{ width: 'auto', height: 30, fontSize: 12 }}
                            value={d.reason || f.qualityReason || 'knowledge_missing'}
                            onChange={(e) => setDraftFor(f.answerMessageId, { reason: e.target.value })}>
                            {Object.entries(H.REASON_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                          </select>
                          <input className="field" style={{ flex: 1, minWidth: 120, height: 30, fontSize: 12 }} placeholder="标注说明"
                            value={d.annotation ?? f.annotation ?? ''} onChange={(e) => setDraftFor(f.answerMessageId, { annotation: e.target.value })} />
                          <Btn size="sm" onClick={() => annotate(f)}>标注</Btn>
                          <Btn size="sm" variant="ghost" icon="beaker" onClick={() => deriveCase(f)}>沉淀用例</Btn>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHead kicker="Golden Dataset" title="评测集沉淀">
              <Btn variant="primary" size="sm" icon="plus" onClick={saveCase}>保存用例</Btn>
            </CardHead>
            <div className="card-pad">
              <div className="q-case-form">
                <input className="field" placeholder="用例标题，例如：OOM 资源不足诊断" value={caseForm.title} onChange={(e) => setCaseForm({ ...caseForm, title: e.target.value })} />
                <textarea className="field" rows="2" placeholder="输入问题" value={caseForm.query} onChange={(e) => setCaseForm({ ...caseForm, query: e.target.value })} />
                <div className="q-form-2">
                  <input className="field" placeholder="必须包含步骤，逗号分隔" value={caseForm.required} onChange={(e) => setCaseForm({ ...caseForm, required: e.target.value })} />
                  <input className="field" placeholder="禁止出现内容，逗号分隔" value={caseForm.forbidden} onChange={(e) => setCaseForm({ ...caseForm, forbidden: e.target.value })} />
                </div>
              </div>
              <div className="q-cases list-scroll">
                {cases.length === 0 ? <Empty icon="target">暂无评测用例</Empty> : cases.map((c, i) => (
                  <div key={c.caseId || c.id || i} className="q-case">
                    <div className="q-case-top">
                      <Icon name="target" size={14} style={{ color: 'var(--accent)' }} />
                      <strong>{c.title}</strong>
                      <Badge kind="ok" className="badge-mono" style={{ marginLeft: 'auto' }}>{c.status || 'active'}</Badge>
                    </div>
                    <code className="mono q-case-q">{c.query}</code>
                    <div className="q-case-reqs">
                      {(c.requiredSteps || []).map((r) => <span key={r} className="q-req ok"><Icon name="check" size={11} />{r}</span>)}
                      {(c.forbiddenContent || []).map((r) => <span key={r} className="q-req no"><Icon name="x" size={11} />{r}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>

        <div className="ops-grid-2 grid-flex">
          <Card>
            <CardHead kicker="Regression Eval" title="自动评测">
              <Btn variant="primary" size="sm" icon="play" onClick={runEval}>运行评测</Btn>
            </CardHead>
            <div className="card-pad">
              <div className="q-run-form">
                <input className="field" value={runForm.name} onChange={(e) => setRunForm({ ...runForm, name: e.target.value })} />
                <input className="field mono" value={runForm.variant} onChange={(e) => setRunForm({ ...runForm, variant: e.target.value })} />
                <input className="field mono" placeholder="prompt 版本" value={runForm.promptVersion} onChange={(e) => setRunForm({ ...runForm, promptVersion: e.target.value })} />
              </div>
              <div className="q-runs list-scroll">
                {runs.length === 0 ? <Empty icon="play">暂无评测运行记录</Empty> : runs.map((r, i) => {
                  const passRate = Math.round((r.passRate || 0) * 100);
                  return (
                    <div key={r.runId || i} className="q-run">
                      <div className="q-run-top">
                        <strong>{r.name}</strong>
                        <span className="badge info mono" style={{ marginLeft: 'auto' }}>{r.variant}</span>
                      </div>
                      <div className="q-run-stats">
                        <div className="q-stat"><span className="mono">{passRate}%</span><small>通过率</small></div>
                        <div className="q-stat"><span className="mono">{r.avgScore ?? '—'}</span><small>平均分</small></div>
                        <div className="q-stat"><span className="mono">{H.pct(r.knowledgeHitRate)}%</span><small>知识命中</small></div>
                      </div>
                      <div className="q-run-bar">
                        <div style={{ width: `${passRate}%`, background: passRate >= 85 ? 'var(--success)' : 'var(--warning)' }} />
                      </div>
                      <span className="mono muted" style={{ fontSize: 10.5 }}>{r.createdAt || ''}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>

          <Card>
            <CardHead kicker="Experiment Design" title="A/B 实验">
              <Btn variant="primary" size="sm" icon="plus" onClick={saveExperiment}>保存实验</Btn>
            </CardHead>
            <div className="card-pad">
              <div className="q-exp-form">
                <input className="field" placeholder="实验名称，例如：检索阈值对比" value={expForm.name} onChange={(e) => setExpForm({ ...expForm, name: e.target.value })} />
                <div className="q-form-2">
                  <input className="field mono" placeholder="variants：baseline,high-recall" value={expForm.variants} onChange={(e) => setExpForm({ ...expForm, variants: e.target.value })} />
                  <input className="field mono" placeholder="流量：50,50" value={expForm.split} onChange={(e) => setExpForm({ ...expForm, split: e.target.value })} />
                </div>
                <select className="field" value={expForm.metric} onChange={(e) => setExpForm({ ...expForm, metric: e.target.value })}>
                  <option value="satisfactionRate">满意率</option>
                  <option value="unlikeRate">点踩率</option>
                  <option value="knowledgeHitRate">知识命中率</option>
                  <option value="avgScore">评测平均分</option>
                </select>
              </div>
              <div className="q-exps list-scroll">
                {experiments.length === 0 ? <Empty icon="flask">暂无 A/B 实验配置</Empty> : experiments.map((e, i) => {
                  const variants = e.variants || [];
                  const split = e.trafficSplit ? Object.values(e.trafficSplit).join(' / ') : '';
                  return (
                    <div key={e.experimentId || i} className="q-exp">
                      <div className="q-exp-top">
                        <Icon name="flask" size={14} style={{ color: 'var(--viz-violet)' }} />
                        <strong>{e.name}</strong>
                        <span className={`badge ${e.status === 'running' ? 'ok' : 'neutral'}`} style={{ marginLeft: 'auto' }}>
                          {e.status === 'running' ? '运行中' : (e.status === 'paused' ? '已暂停' : '草稿')}
                        </span>
                      </div>
                      <div className="q-exp-variants">
                        {variants.map((v, j) => (
                          <span key={v} className="q-variant">
                            <i style={{ background: j === 0 ? 'var(--accent)' : 'var(--viz-teal)' }} />{v}
                          </span>
                        ))}
                        {split && <span className="mono muted" style={{ marginLeft: 'auto', fontSize: 11 }}>{split}</span>}
                      </div>
                      <div className="q-exp-metric mono">主指标 · {e.primaryMetric}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

window.QualityView = QualityView;
