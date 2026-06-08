/* Knowledge base view — wired to /agent/v1/knowledge/* */
const { useState: useStateK, useEffect: useEffectK } = React;

const KB_BLANK = { title: '', filename: '', content: '', category: '未分类', owner: '', tags: '', visibility: 'internal', status: 'draft' };

function KnowledgeView({ toast }) {
  const [items, setItems] = useStateK([]);
  const [activeFile, setActiveFile] = useStateK(null);
  const [statusFilter, setStatusFilter] = useStateK('');
  const [tab, setTab] = useStateK('search');
  const [form, setForm] = useStateK(KB_BLANK);
  const [meta, setMeta] = useStateK({ updatedAt: '' });
  const [query, setQuery] = useStateK('');
  const [results, setResults] = useStateK([]);
  const [revisions, setRevisions] = useStateK([]);
  const [gaps, setGaps] = useStateK([]);
  const [saving, setSaving] = useStateK(false);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  function loadList(select) {
    return API.knowledgeList().then((list) => {
      setItems(list || []);
      if (select && (list || []).length) selectFile((list[0]).filename);
      return list;
    }).catch((e) => toast(e.message));
  }

  useEffectK(() => { loadList(true); }, []);

  function selectFile(filename) {
    setActiveFile(filename);
    API.knowledgeDetail(filename).then((d) => {
      setForm({
        title: d.title || '', filename: d.filename || filename, content: d.content || '',
        category: d.category || '未分类', owner: d.owner || '', tags: H.joinList(d.tags),
        visibility: d.visibility || 'internal', status: d.status || 'published',
      });
      setMeta({ updatedAt: d.updatedAt || '' });
    }).catch((e) => toast(e.message));
  }

  function newDoc() {
    setActiveFile(null);
    setForm(KB_BLANK);
    setMeta({ updatedAt: '' });
    toast('已切换到新建知识');
  }

  async function save() {
    if (!form.title.trim()) { toast('请填写标题'); return; }
    setSaving(true);
    try {
      const data = await API.knowledgeSave({
        title: form.title.trim(),
        filename: form.filename.trim() || null,
        category: form.category.trim() || '未分类',
        tags: H.splitList(form.tags),
        status: form.status,
        visibility: form.visibility,
        owner: form.owner.trim() || null,
        content: form.content,
      });
      const fn = data?.filename || form.filename;
      await loadList(false);
      if (fn) selectFile(fn);
      toast('知识已保存并重建索引');
    } catch (e) {
      toast(e.message || '保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(status) {
    const fn = activeFile || form.filename.trim();
    if (!fn) { toast('请先保存知识'); return; }
    try {
      const d = await API.knowledgeStatus(fn, status);
      setField('status', d.status || status);
      await loadList(false);
      toast(`状态已切换为「${STATUS_LABEL[status] || status}」`);
    } catch (e) {
      toast(e.message || '状态更新失败');
    }
  }

  function runSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    API.knowledgeSearch(query.trim(), 5).then((r) => setResults(r || [])).catch((err) => toast(err.message));
  }

  useEffectK(() => {
    if (tab === 'revisions' && activeFile) {
      API.knowledgeRevisions(activeFile).then((r) => setRevisions(r || [])).catch(() => setRevisions([]));
    }
    if (tab === 'gaps') {
      API.knowledgeGaps().then((g) => setGaps(g || [])).catch(() => setGaps([]));
    }
  }, [tab, activeFile]);

  const filtered = items.filter((i) => !statusFilter || i.status === statusFilter);
  const lifecycle = [
    { k: 'draft', label: '转草稿' }, { k: 'review', label: '提交审核' },
    { k: 'published', label: '发布' }, { k: 'archived', label: '归档' },
  ];

  return (
    <div className="kb-layout">
      <aside className="kb-aside">
        <div className="aside-block-head" style={{ marginBottom: 12 }}>
          <Icon name="book" size={14} /> 知识文件
          <span className="mono count">{items.length}</span>
        </div>
        <select className="field" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ marginBottom: 12 }}>
          <option value="">全部状态</option>
          <option value="published">已发布</option>
          <option value="review">待审核</option>
          <option value="draft">草稿</option>
          <option value="archived">已归档</option>
        </select>
        <div className="kb-list">
          {filtered.length === 0 && <Empty icon="book">暂无知识文件</Empty>}
          {filtered.map((k) => (
            <button key={k.filename} className={`kb-item ${activeFile === k.filename ? 'active' : ''}`} onClick={() => selectFile(k.filename)}>
              <div className="kb-item-top">
                <Icon name="file" size={14} style={{ color: 'var(--text-mute)', flex: 'none' }} />
                <strong>{k.title}</strong>
              </div>
              <code className="mono kb-fn">{k.filename}</code>
              <div className="kb-item-foot">
                <Lifecycle status={k.status} />
                {typeof k.hits === 'number' && <span className="mono muted" style={{ fontSize: 10 }}>{k.hits} 命中</span>}
              </div>
            </button>
          ))}
        </div>
      </aside>

      <div className="kb-main">
        <div className="kb-grid">
          <Card className="kb-editor">
            <div className="kb-toolbar">
              <div>
                <Kicker>{activeFile ? '编辑已有知识' : '新增知识'}</Kicker>
                <h3 style={{ margin: '3px 0 0', fontSize: 15 }}>知识内容与治理元数据</h3>
                <div className="mono muted" style={{ fontSize: 11, marginTop: 3 }}>{form.filename || '未命名'}{meta.updatedAt ? ` · 更新于 ${meta.updatedAt}` : ''}</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <Btn icon="plus" size="sm" onClick={newDoc}>新建</Btn>
                <Btn variant="primary" size="sm" icon="check" disabled={saving} onClick={save}>{saving ? '保存中' : '保存'}</Btn>
              </div>
            </div>
            <div className="kb-editor-body">
              <div className="kb-fields-2">
                <label className="lbl"><span>标题</span><input className="field" value={form.title} onChange={(e) => setField('title', e.target.value)} /></label>
                <label className="lbl"><span>文件名</span><input className="field mono" value={form.filename} onChange={(e) => setField('filename', e.target.value)} placeholder="自动根据标题生成" /></label>
              </div>
              <label className="lbl" style={{ flex: 1 }}>
                <span>Markdown 内容</span>
                <textarea className="field mono kb-md" value={form.content} onChange={(e) => setField('content', e.target.value)} />
              </label>
            </div>
          </Card>

          <div className="kb-side-col">
            <Card>
              <CardHead kicker="属性与工作流" title="发布前治理信息" />
              <div className="card-pad" style={{ display: 'grid', gap: 16 }}>
                <div className="workflow-bar">
                  <div>
                    <div className="kicker" style={{ marginBottom: 4 }}>当前状态</div>
                    <Lifecycle status={form.status} />
                  </div>
                  <div className="lifecycle-actions">
                    {lifecycle.map((l) => (
                      <button key={l.k} className={`lc-btn ${form.status === l.k ? 'on' : ''}`} onClick={() => changeStatus(l.k)}>{l.label}</button>
                    ))}
                  </div>
                </div>
                <div className="gov-grid">
                  <label className="lbl"><span>分类</span><input className="field" value={form.category} onChange={(e) => setField('category', e.target.value)} /></label>
                  <label className="lbl"><span>负责人</span><input className="field" value={form.owner} onChange={(e) => setField('owner', e.target.value)} /></label>
                  <label className="lbl"><span>标签</span><input className="field" value={form.tags} onChange={(e) => setField('tags', e.target.value)} placeholder="逗号分隔" /></label>
                  <label className="lbl"><span>可见性</span>
                    <select className="field" value={form.visibility} onChange={(e) => setField('visibility', e.target.value)}>
                      <option value="internal">内部</option><option value="private">私有</option><option value="public">公开</option>
                    </select>
                  </label>
                </div>
              </div>
            </Card>

            <Card style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <div className="kb-tabs">
                {[{ k: 'search', l: '检索' }, { k: 'revisions', l: '版本' }, { k: 'gaps', l: '缺口' }].map((t) => (
                  <button key={t.k} className={tab === t.k ? 'on' : ''} onClick={() => setTab(t.k)}>{t.l}</button>
                ))}
              </div>
              <div className="card-pad kb-tab-body">
                {tab === 'search' && (
                  <div style={{ display: 'grid', gap: 12 }}>
                    <form className="kb-search" onSubmit={runSearch}>
                      <div className="search-wrap" style={{ flex: 1, margin: 0 }}>
                        <Icon name="search" size={14} />
                        <input className="field" placeholder="输入问题，例如：登录失败怎么处理" value={query} onChange={(e) => setQuery(e.target.value)} />
                      </div>
                      <Btn variant="primary" type="submit">检索</Btn>
                    </form>
                    {results.length === 0 ? <Empty icon="search">输入问题以检索已发布知识片段</Empty> : (
                      <div style={{ display: 'grid', gap: 9 }}>
                        {results.map((r, i) => (
                          <div key={i} className="kb-result">
                            <div className="kb-result-top">
                              <code className="mono">{(r.source || '').split('/').pop()}</code>
                              <span className="badge info mono">{Number(r.score || 0).toFixed(2)}</span>
                            </div>
                            <div className="kb-result-title">{r.heading || '未命名章节'}</div>
                            <p className="kb-result-snip">{r.content}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {tab === 'revisions' && (
                  !activeFile ? <Empty icon="file">选择左侧知识后查看版本历史</Empty> :
                  revisions.length === 0 ? <Empty icon="file">暂无版本记录</Empty> : (
                    <div className="kb-timeline">
                      {revisions.map((r, i) => (
                        <div key={i} className="tl-item">
                          <span className="tl-dot" />
                          <div className="tl-body">
                            <div className="tl-top"><Lifecycle status={r.status} /><span className="mono muted" style={{ fontSize: 11 }}>{r.timestamp}</span></div>
                            <div className="tl-note">{r.action || '保存'}{r.category ? ` · ${r.category}` : ''}</div>
                            <code className="mono muted" style={{ fontSize: 10.5 }}>{(r.content || '').slice(0, 80)}</code>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                )}
                {tab === 'gaps' && (
                  gaps.length === 0 ? <Empty icon="info">近期点踩问题没有暴露明显知识缺口</Empty> : (
                    <div style={{ display: 'grid', gap: 9 }}>
                      {gaps.map((g, i) => {
                        const types = g.reason?.feedbackInfoTypes || [];
                        return (
                          <div key={i} className="kb-gap">
                            <div style={{ flex: 1 }}>
                              <div className="kb-gap-q">{g.query || '未记录问题'}</div>
                              <span className="mono muted" style={{ fontSize: 11 }}>最近 {g.timestamp}{typeof g.bestScore === 'number' ? ` · score ${g.bestScore}` : ''}</span>
                            </div>
                            {types.length > 0 && <Badge kind="warn">{H.reasonLabel(types[0])}</Badge>}
                          </div>
                        );
                      })}
                    </div>
                  )
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

window.KnowledgeView = KnowledgeView;
