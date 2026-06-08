/* App shell: sidebar rail + topbar + router. Wired to the FastAPI backend. */
const { useState: useStateA, useEffect: useEffectA, useCallback } = React;

const ACCENTS = [
  { hex: '#38bdf8', hue: 205 },
  { hex: '#6366f1', hue: 262 },
  { hex: '#a78bfa', hue: 292 },
  { hex: '#2dd4bf', hue: 178 },
  { hex: '#34d399', hue: 152 },
];
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#38bdf8",
  "mode": "dark",
  "density": "regular"
}/*EDITMODE-END*/;

const NAV = [
  { id: 'chat', path: '/', label: '诊断会话', icon: 'chat', kicker: 'Diagnostic Console', title: '诊断会话', tags: ['FastAPI', 'SSE', 'SQLite'] },
  { id: 'knowledge', path: '/knowledge', label: '知识库', icon: 'book', kicker: 'Local Markdown Knowledge', title: '本地知识库管理', tags: ['Lifecycle', 'Metadata', 'RAG'] },
  { id: 'runbooks', path: '/runbooks', label: 'Runbook', icon: 'runbook', kicker: 'Runbook · Tool Intent · Guardrail', title: '诊断 Runbook 编排', tags: ['Checklist', 'Evidence', 'Approval'] },
  { id: 'ops', path: '/ops', label: '运营看板', icon: 'chart', kicker: 'Operations Analytics', title: 'Agent 运营看板', tags: ['DAU', 'Feedback', 'Quality'] },
  { id: 'quality', path: '/quality', label: '质量闭环', icon: 'quality', kicker: 'Dataset · Eval · Experiment', title: '质量评估与反馈闭环', tags: ['Feedback', 'Eval Set', 'A/B'] },
];

function navFromPath(pathname) {
  const match = NAV.find((n) => n.path === pathname);
  return (match || NAV[0]).id;
}

function useToast() {
  const [state, setState] = useStateA({ msg: '', show: false });
  const ref = React.useRef(null);
  const toast = useCallback((msg) => {
    setState({ msg, show: true });
    clearTimeout(ref.current);
    ref.current = setTimeout(() => setState((s) => ({ ...s, show: false })), 2200);
  }, []);
  return [state, toast];
}

function Rail({ active, setActive, collapsed, setCollapsed, ctx, authEnabled, onLogout }) {
  return (
    <aside className="rail">
      <div className="brand">
        <div className="brand-mark">W</div>
        <div className="brand-text">
          <h1>Wise MLOps</h1>
          <p>diagnostic agent</p>
        </div>
      </div>

      <div className="rail-section-label">工作台</div>
      <nav className="nav">
        {NAV.map((n) => (
          <button key={n.id} className={`nav-item ${active === n.id ? 'active' : ''}`} onClick={() => setActive(n.id)} title={n.label}>
            <Icon name={n.icon} size={19} className="nv-ico" />
            <span>{n.label}</span>
          </button>
        ))}
      </nav>

      <div className="rail-spacer" />

      <div className="rail-foot">
        <div className="user-chip">
          <div className="user-av">{(ctx.userId || '--').slice(-2).toUpperCase()}</div>
          <div className="user-meta">
            <b>{ctx.userId}</b>
            <small>{ctx.role === 'admin' ? '管理员' : '用户'} · {ctx.service}</small>
          </div>
        </div>
        {authEnabled && (
          <button className="rail-collapse-btn" onClick={onLogout}>
            <Icon name="logout" size={15} />
            <span>退出登录</span>
          </button>
        )}
        <button className="rail-collapse-btn" onClick={() => setCollapsed(!collapsed)}>
          <Icon name="chevron" size={15} />
          <span>收起侧栏</span>
        </button>
      </div>
    </aside>
  );
}

function Topbar({ nav, children }) {
  return (
    <header className="topbar">
      <div className="tb-titles">
        <div className="tb-kicker">{nav.kicker}</div>
        <h2 className="tb-title">{nav.title}</h2>
      </div>
      <div className="tb-actions">
        {children}
        <div className="tag-row">
          {nav.tags.map((t) => <span key={t} className="stack-tag"><i />{t}</span>)}
        </div>
      </div>
    </header>
  );
}

function App() {
  const [active, setActiveState] = useStateA(navFromPath(window.location.pathname));
  const [collapsed, setCollapsed] = useStateA(false);
  const [ctx, setCtx] = useStateA({ userId: 'l0123456', service: 'Wise', scene: '模型任务', title: 'MLOps 诊断', role: 'admin' });
  const [authEnabled, setAuthEnabled] = useStateA(false);
  const [runbookMode, setRunbookMode] = useStateA(false);
  const [deepThink, setDeepThink] = useStateA(false);
  const [toastState, toast] = useToast();
  const [newChatNonce, setNewChatNonce] = useStateA(0);

  const setActive = useCallback((id) => {
    setActiveState(id);
    const target = NAV.find((n) => n.id === id);
    if (target && window.location.pathname !== target.path) {
      window.history.pushState({ id }, '', target.path);
    }
  }, []);

  useEffectA(() => {
    const onPop = () => setActiveState(navFromPath(window.location.pathname));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // load identity from backend
  useEffectA(() => {
    API.me().then((payload) => {
      const data = payload && payload.result && payload.result.data;
      if (data) {
        setAuthEnabled(!!data.authEnabled);
        setCtx((c) => ({ ...c, userId: data.userId || c.userId, role: data.role || c.role }));
      }
    }).catch(() => {});
  }, []);

  const nav = NAV.find((n) => n.id === active);

  const [tw, setTweak] = useTweaks(TWEAK_DEFAULTS);
  useEffectA(() => {
    const acc = ACCENTS.find((a) => a.hex === tw.accent) || ACCENTS[0];
    document.documentElement.style.setProperty('--accent-h', acc.hue);
    document.documentElement.setAttribute('data-mode', tw.mode);
    document.documentElement.setAttribute('data-density', tw.density);
  }, [tw.accent, tw.mode, tw.density]);

  function logout() {
    API.logout().finally(() => { window.location.href = '/login'; });
  }

  let topbarExtra = null;
  if (active === 'chat') {
    topbarExtra = <Btn variant="ghost" size="sm" icon="plus" onClick={() => setNewChatNonce((n) => n + 1)}>新会话</Btn>;
  }

  return (
    <div className={`app ${collapsed ? 'rail-collapsed' : ''}`}>
      <Rail active={active} setActive={setActive} collapsed={collapsed} setCollapsed={setCollapsed}
        ctx={ctx} authEnabled={authEnabled} onLogout={logout} />
      <div className="main">
        <Topbar nav={nav}>{topbarExtra}</Topbar>
        <div className="view" key={active}>
          {active === 'chat' && (
            <ChatView ctx={ctx} setCtx={setCtx} runbookMode={runbookMode} setRunbookMode={setRunbookMode}
              deepThink={deepThink} setDeepThink={setDeepThink} toast={toast} newChatNonce={newChatNonce} />
          )}
          {active === 'knowledge' && <KnowledgeView toast={toast} />}
          {active === 'runbooks' && <RunbooksView toast={toast} />}
          {active === 'ops' && <OpsView />}
          {active === 'quality' && <QualityView toast={toast} />}
        </div>
      </div>
      <Toast msg={toastState.msg} show={toastState.show} />

      <TweaksPanel title="Tweaks">
        <TweakSection label="品牌调色" />
        <TweakColor label="强调色" value={tw.accent} options={ACCENTS.map((a) => a.hex)}
          onChange={(v) => setTweak('accent', v)} />
        <TweakSection label="外观" />
        <TweakRadio label="主题" value={tw.mode} options={[{ value: 'dark', label: '深色' }, { value: 'light', label: '浅色' }]}
          onChange={(v) => setTweak('mode', v)} />
        <TweakRadio label="信息密度" value={tw.density} options={[{ value: 'regular', label: '常规' }, { value: 'compact', label: '紧凑' }]}
          onChange={(v) => setTweak('density', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
