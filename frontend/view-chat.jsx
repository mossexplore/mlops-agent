/* Chat / diagnostic console view — wired to the FastAPI SSE backend. */
const { useState: useStateC, useRef: useRefC, useEffect: useEffectC } = React;

function Markdown({ text }) {
  return <div className="md" dangerouslySetInnerHTML={{ __html: H.renderMarkdown(text || '') }} />;
}

function TracePanel({ traceId }) {
  const [open, setOpen] = useStateC(false);
  const [trace, setTrace] = useStateC(null);
  const [err, setErr] = useStateC('');

  useEffectC(() => {
    if (!open || trace || !traceId) return;
    API.traceDetail(traceId).then(setTrace).catch((e) => setErr(e.message));
  }, [open, traceId]);

  const spans = trace?.spans || [];
  const sources = trace?.sources || trace?.knowledgeSources || [];

  return (
    <div className="trace card" style={{ marginTop: 14 }}>
      <button className="trace-toggle" onClick={() => setOpen(!open)}>
        <Icon name="spark" size={14} style={{ color: 'var(--accent-bright)' }} />
        <span className="kicker" style={{ color: 'var(--accent-bright)' }}>Agent Trace</span>
        <code className="mono" style={{ fontSize: 11, color: 'var(--text-mute)' }}>{traceId.slice(0, 12)}</code>
        {trace && typeof trace.totalMs === 'number' && <span className="badge ok" style={{ marginLeft: 4 }}>{trace.totalMs} ms</span>}
        <Icon name="chevronDown" size={15} style={{ marginLeft: 'auto', transform: open ? 'rotate(180deg)' : 'none', transition: '0.2s', color: 'var(--text-mute)' }} />
      </button>
      {open && (
        <div style={{ marginTop: 12, display: 'grid', gap: 6 }}>
          {err && <div className="empty">{err}</div>}
          {!err && !trace && <div className="empty">读取 trace…</div>}
          {spans.map((s, i) => (
            <div key={i} className="span-row">
              <span className="span-dot" data-kind={s.kind} />
              <code className="mono" style={{ fontSize: 12, color: 'var(--text-dim)' }}>{s.name}</code>
              <span className="badge neutral mono" style={{ fontSize: 10 }}>{s.kind}</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-mute)' }}>{s.durationMs ?? s.ms ?? 0} ms</span>
            </div>
          ))}
          {sources.length > 0 && (
            <div className="src-row" style={{ marginTop: 8 }}>
              <span className="kicker">引用来源</span>
              {sources.map((s, i) => (
                <span key={i} className="src-chip"><Icon name="file" size={12} /> {s.title || (s.source || '').split('/').pop()} {typeof s.score === 'number' && <em className="mono">{s.score.toFixed(2)}</em>}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DiagnosticStatePanel({ state }) {
  if (!state) return null;
  const facts = state.facts || state.confirmedFacts || [];
  const needed = state.openQuestions || state.nextNeeded || [];
  return (
    <div className="diag-state">
      <div className="ds-row">
        <span className="kicker">多轮诊断状态</span>
        <Risk level={state.riskLevel || 'low'} />
      </div>
      <div className="ds-grid">
        <div>
          <div className="ds-label">当前步骤</div>
          <div className="ds-val">{state.currentStep || '—'}</div>
        </div>
        <div>
          <div className="ds-label">已确认事实</div>
          {facts.length ? <ul>{facts.map((f, i) => <li key={i}>{f}</li>)}</ul> : <div className="ds-val muted">暂无</div>}
        </div>
        <div>
          <div className="ds-label">下一步需补充</div>
          {needed.length ? <ul>{needed.map((f, i) => <li key={i} className="need">{f}</li>)}</ul> : <div className="ds-val muted">暂无</div>}
        </div>
      </div>
    </div>
  );
}

function AssistantMessage({ m, runbookMode, onFeedback }) {
  return (
    <div className="msg assistant">
      <div className="msg-meta">
        <div className="av bot"><Icon name="spark" size={15} /></div>
        <span className="mono">Agent</span>
        {runbookMode && <span className="badge info" style={{ fontSize: 10 }}>Runbook 模式</span>}
      </div>
      <div className="diag fade-in">
        <Markdown text={m.text} />
        <DiagnosticStatePanel state={m.diagnosticState} />
        {m.traceId && <TracePanel traceId={m.traceId} />}
        <div className="fb-row">
          <button className={`fb-btn ${m.feedback === 'like' ? 'on like' : ''}`} onClick={() => onFeedback(m, 'like')} title="点赞">
            <Icon name="thumb" size={15} />
          </button>
          <button className={`fb-btn down ${m.feedback === 'unlike' ? 'on unlike' : ''}`} onClick={() => onFeedback(m, 'unlike')} title="点踩">
            <Icon name="thumb" size={15} />
          </button>
          <span className="fb-sep" />
          <button className="fb-btn" title="复制" onClick={() => navigator.clipboard?.writeText(m.text || '')}><Icon name="copy" size={15} /></button>
        </div>
      </div>
    </div>
  );
}

function StreamingState() {
  return (
    <div className="streaming card">
      <div className="stream-head">
        <span className="pulse" />
        <span className="kicker" style={{ color: 'var(--accent-bright)' }}>正在诊断…</span>
      </div>
      <div style={{ display: 'grid', gap: 7, marginTop: 12 }}>
        <div className="span-row pending"><span className="span-spin" /><span className="mono" style={{ fontSize: 12, color: 'var(--text-mute)' }}>problem_identification · knowledge_retrieval · response_generation</span></div>
      </div>
    </div>
  );
}

function ChatView({ ctx, setCtx, runbookMode, setRunbookMode, deepThink, setDeepThink, toast, newChatNonce }) {
  const [convs, setConvs] = useStateC([]);
  const [conversationId, setConversationId] = useStateC(() => crypto.randomUUID());
  const [activeConv, setActiveConv] = useStateC(null);
  const [search, setSearch] = useStateC('');
  const [messages, setMessages] = useStateC([]);
  const [input, setInput] = useStateC('');
  const [streaming, setStreaming] = useStateC(false);
  const [pending, setPending] = useStateC(false);
  const scrollRef = useRefC(null);
  const abortRef = useRefC(null);

  function loadConversations(userId) {
    API.conversationList(userId || ctx.userId)
      .then((list) => setConvs(list || []))
      .catch(() => setConvs([]));
  }

  useEffectC(() => { loadConversations(ctx.userId); }, [ctx.userId]);

  // "新会话" from the topbar
  useEffectC(() => {
    if (newChatNonce === 0) return;
    newConversation();
  }, [newChatNonce]);

  useEffectC(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streaming, pending]);

  useEffectC(() => () => abortRef.current?.abort(), []);

  const filtered = convs.filter((c) => !search || `${c.title || ''}${c.preview || ''}`.toLowerCase().includes(search.toLowerCase()));

  function newConversation() {
    abortRef.current?.abort();
    setConversationId(crypto.randomUUID());
    setActiveConv(null);
    setMessages([]);
    setStreaming(false);
    setPending(false);
  }

  async function loadConversation(convId) {
    abortRef.current?.abort();
    setConversationId(convId);
    setActiveConv(convId);
    setStreaming(false);
    setPending(false);
    try {
      const data = await API.chatList(ctx.userId, convId);
      setMessages((data || []).map((item, i) => item.type === 'user'
        ? { id: `u${i}-${item.messageId || i}`, role: 'user', text: item.content, time: item.timestamp }
        : {
          id: `a${i}-${item.messageId || i}`, role: 'assistant', text: item.content,
          messageId: item.messageId, queryMessageId: item.queryMessageId, traceId: item.traceId,
          time: item.timestamp, feedback: item.feedbackInfo?.feedback || null, diagnosticState: null,
        }));
    } catch (e) {
      toast(e.message || '会话加载失败');
    }
  }

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || streaming) return;
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: 'user', text: q, time: H.nowTime() }]);
    setInput('');
    setStreaming(true);
    setPending(true);

    const controller = new AbortController();
    abortRef.current = controller;
    const tempId = `stream-${Date.now()}`;
    const body = {
      query: q,
      needDeepThinking: deepThink ? 1 : 0,
      groundingMode: runbookMode ? 'runbook' : 'knowledge',
      prompt: 'mlops-agent',
      context: { userId: ctx.userId, conversationId, service: ctx.service, scene: ctx.scene || '模型任务', title: ctx.title || q.slice(0, 20) },
    };

    try {
      await API.chatStream(body, (payload, fullText) => {
        setPending(false);
        setMessages((prev) => {
          const msg = {
            id: tempId, role: 'assistant', text: fullText, time: H.nowTime(),
            messageId: payload.messageId, queryMessageId: payload.queryMessageId,
            traceId: payload.traceId, diagnosticState: payload.diagnosticState, feedback: null, streaming: true,
          };
          if (!prev.some((x) => x.id === tempId)) return [...prev, msg];
          return prev.map((x) => (x.id === tempId ? { ...x, ...msg } : x));
        });
      }, controller.signal);
      setMessages((prev) => prev.map((x) => (x.id === tempId ? { ...x, streaming: false } : x)));
      setActiveConv(conversationId);
      loadConversations(ctx.userId);
    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: 'assistant', text: `请求失败：${e.message || '请稍后重试'}` }]);
      }
    } finally {
      setStreaming(false);
      setPending(false);
      if (abortRef.current === controller) abortRef.current = null;
    }
  }

  async function onFeedback(m, val) {
    if (!m.messageId) { toast('该消息暂不可反馈'); return; }
    const next = m.feedback === val ? null : val;
    try {
      await API.feedback(
        { userId: ctx.userId, conversationId, messageId: m.messageId, queryMessageId: m.queryMessageId },
        val,
        val === 'unlike' ? { feedbackInfo: '', feedbackInfoTypes: [] } : null,
      );
      setMessages((prev) => prev.map((x) => (x.id === m.id ? { ...x, feedback: next } : x)));
      toast(val === 'like' ? '已记录点赞反馈' : '已提交点踩反馈');
    } catch (e) {
      toast(e.message || '反馈提交失败');
    }
  }

  return (
    <div className="chat-layout">
      <aside className="chat-aside">
        <button className="btn primary new-chat" onClick={newConversation}>
          <Icon name="plus" size={16} /> 新建诊断会话
        </button>

        <div className="aside-block">
          <div className="aside-block-head"><Icon name="sliders" size={14} /> 上下文</div>
          <div className="ctx-grid">
            <label className="lbl"><span>用户</span><input className="field" value={ctx.userId} onChange={(e) => setCtx({ ...ctx, userId: e.target.value })} /></label>
            <label className="lbl"><span>来源</span>
              <select className="field" value={ctx.service} onChange={(e) => setCtx({ ...ctx, service: e.target.value })}>
                <option>Wise</option><option>MTP</option><option>MEP</option>
              </select>
            </label>
            <label className="lbl"><span>场景</span><input className="field" value={ctx.scene} onChange={(e) => setCtx({ ...ctx, scene: e.target.value })} /></label>
          </div>
          <div className="ctx-toggles">
            <Toggle checked={deepThink} onChange={setDeepThink} label="深度思考" />
            <Toggle checked={runbookMode} onChange={setRunbookMode} label="Runbook 回答" />
          </div>
        </div>

        <div className="aside-block history-block">
          <div className="aside-block-head">
            <Icon name="history" size={14} /> 历史会话
            <span className="mono count">{convs.length}</span>
          </div>
          <div className="search-wrap">
            <Icon name="search" size={14} />
            <input className="field" placeholder="搜索会话" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="conv-list">
            {filtered.length === 0 && <Empty icon="history">暂无历史会话</Empty>}
            {filtered.map((c) => (
              <button key={c.conversationId} className={`conv ${activeConv === c.conversationId ? 'active' : ''}`} onClick={() => loadConversation(c.conversationId)}>
                <div className="conv-top">
                  <strong>{c.title || '未命名会话'}</strong>
                  <span className="mono conv-time">{c.timestamp || ''}</span>
                </div>
                {c.preview && <span className="conv-prev">{c.preview}</span>}
                <div className="conv-foot">
                  {c.scene && <span className="badge neutral" style={{ fontSize: 10 }}>{c.scene}</span>}
                  {typeof c.count === 'number' && <span className="mono conv-count">{c.count} 轮</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      </aside>

      <section className="chat-main">
        <div className="messages" ref={scrollRef}>
          <div className="messages-inner">
            {messages.length === 0 && !streaming && (
              <div className="chat-empty fade-in">
                <div className="ce-mark"><Icon name="terminal" size={30} /></div>
                <h2>WiseMLOps Agent</h2>
                <p>可解释的智能诊断伙伴，为模型任务、资源异常与平台日志提供可执行的排查建议。</p>
                <div className="quick-grid">
                  {H.QUICK_PROMPTS.map((p) => (
                    <button key={p.k} className="quick" onClick={() => send(p.q)}>
                      <span className="quick-k">{p.k}</span>
                      <span className="quick-q">{p.q}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => m.role === 'user' ? (
              <div key={m.id} className="msg user">
                <div className="bubble">{m.text}</div>
                <div className="msg-meta"><span className="mono">{m.time}</span><div className="av user">{(ctx.userId || '--').slice(-2)}</div></div>
              </div>
            ) : (
              <AssistantMessage key={m.id} m={m} runbookMode={runbookMode} onFeedback={onFeedback} />
            ))}
            {pending && (
              <div className="msg assistant">
                <div className="msg-meta"><div className="av bot"><Icon name="spark" size={15} /></div><span className="mono">Agent</span></div>
                <StreamingState />
              </div>
            )}
          </div>
        </div>

        <div className="composer">
          <div className="composer-box">
            <textarea className="composer-input" rows="1" placeholder="描述报错码、现象或日志，按 Enter 发送…"
              value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <button className="send-btn" onClick={() => streaming ? abortRef.current?.abort() : send()} disabled={!streaming && !input.trim()}>
              {streaming ? <span className="send-spin" /> : <Icon name="send" size={18} />}
            </button>
          </div>
          <p className="composer-note">AI 可能产生不准确的信息，关键操作请人工核实。高风险动作需确认后执行。</p>
        </div>
      </section>
    </div>
  );
}

window.ChatView = ChatView;
