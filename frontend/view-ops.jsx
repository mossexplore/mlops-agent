/* Ops dashboard view — wired to /agent/v1/ops/dashboard.
   Filter is a calendar date-range picker; data refreshes only when 查询 is clicked
   (the picker selection is "pending" until committed). */
const { useState: useStateO, useEffect: useEffectO, useRef: useRefO } = React;

const WD = ['一', '二', '三', '四', '五', '六', '日'];
function fmtD(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }

function MonthGrid({ month, range, today, onPick }) {
  const y = month.getFullYear(), m = month.getMonth();
  const startDow = (new Date(y, m, 1).getDay() + 6) % 7; // Monday-first
  const dim = new Date(y, m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= dim; d++) cells.push(new Date(y, m, d));
  const { start, end } = range;
  return (
    <div className="dp-month">
      <div className="dp-dow">{WD.map((w) => <span key={w}>{w}</span>)}</div>
      <div className="dp-grid">
        {cells.map((d, i) => {
          if (!d) return <span key={i} className="dp-cell empty" />;
          const t = startOfDay(d).getTime();
          const isStart = start && t === startOfDay(start).getTime();
          const isEnd = end && t === startOfDay(end).getTime();
          const inR = start && end && t > startOfDay(start).getTime() && t < startOfDay(end).getTime();
          const future = t > startOfDay(today).getTime();
          const cls = ['dp-cell', isStart ? 'edge start' : '', isEnd ? 'edge end' : '', inR ? 'in' : '', future ? 'future' : ''].join(' ').replace(/\s+/g, ' ').trim();
          return <button key={i} className={cls} disabled={future} onClick={() => onPick(d)}>{d.getDate()}</button>;
        })}
      </div>
    </div>
  );
}

function DateRangePicker({ range, onChange, today }) {
  const [open, setOpen] = useStateO(false);
  const [view, setView] = useStateO(new Date(range.end.getFullYear(), range.end.getMonth(), 1));
  const [pick, setPick] = useStateO(null); // pending start while choosing
  const ref = useRefO(null);
  useEffectO(() => {
    function onDoc(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    if (open) document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  function handlePick(d) {
    if (!pick) { setPick(d); onChange({ start: d, end: d }); return; }
    let start = pick, end = d;
    if (end < start) [start, end] = [end, start];
    onChange({ start, end });
    setPick(null);
    setOpen(false);
  }
  const prevMonth = () => setView(new Date(view.getFullYear(), view.getMonth() - 1, 1));
  const nextMonth = () => setView(new Date(view.getFullYear(), view.getMonth() + 1, 1));
  const dayCount = Math.round((startOfDay(range.end) - startOfDay(range.start)) / 86400000) + 1;

  return (
    <div className="date-picker" ref={ref}>
      <button className={`dp-trigger ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
        <Icon name="calendar" size={15} style={{ color: 'var(--text-mute)' }} />
        <span className="mono">{fmtD(range.start)}</span>
        <span className="dp-arrow">→</span>
        <span className="mono">{fmtD(range.end)}</span>
        <Icon name="chevronDown" size={14} style={{ color: 'var(--text-mute)', transform: open ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
      </button>
      {open && (
        <div className="dp-pop">
          <div className="dp-head">
            <button className="dp-nav" onClick={prevMonth}><Icon name="chevronLeft" size={16} /></button>
            <span className="dp-title">{view.getFullYear()} 年 {view.getMonth() + 1} 月</span>
            <button className="dp-nav" onClick={nextMonth} disabled={view.getFullYear() === today.getFullYear() && view.getMonth() >= today.getMonth()}><Icon name="chevron" size={16} /></button>
          </div>
          <MonthGrid month={view} range={range} today={today} onPick={handlePick} />
          <div className="dp-foot">
            <span className="mono dim">{pick ? '请选择结束日期' : `已选 ${dayCount} 天`}</span>
            <div className="dp-quick">
              <button onClick={() => { onChange({ start: addDays(today, -6), end: today }); setView(new Date(today.getFullYear(), today.getMonth(), 1)); setPick(null); }}>近 7 天</button>
              <button onClick={() => { onChange({ start: addDays(today, -29), end: today }); setView(new Date(today.getFullYear(), today.getMonth(), 1)); setPick(null); }}>近 30 天</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function OpsView() {
  const c = useAccent();
  const TODAY = startOfDay(new Date());
  const DEFAULT = { start: addDays(TODAY, -6), end: TODAY };
  const [range, setRange] = useStateO(DEFAULT);          // picker selection (pending)
  const [committed, setCommitted] = useStateO(DEFAULT);  // applied query range
  const [data, setData] = useStateO(null);
  const [loading, setLoading] = useStateO(true);         // first load
  const [refreshing, setRefreshing] = useStateO(false);  // subsequent queries
  const [error, setError] = useStateO('');

  useEffectO(() => {
    let cancelled = false;
    setError('');
    setData((d) => { if (d) setRefreshing(true); else setLoading(true); return d; });
    API.opsDashboard({ startDate: fmtD(committed.start), endDate: fmtD(committed.end) })
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) { setLoading(false); setRefreshing(false); } });
    return () => { cancelled = true; };
  }, [committed]);

  function runQuery() { setCommitted(range); }

  if (loading && !data) return <div className="view-pad"><Empty icon="chart">正在加载运营数据…</Empty></div>;
  if (error && !data) return <div className="view-pad"><Empty icon="alert">{error}</Empty></div>;
  if (!data) return null;

  const s = data.summary || {};
  const daily = (data.daily || []).map((r) => ({ d: (r.date || '').slice(5), ask: r.questionCount || 0, like: r.likeCount || 0, unlike: r.unlikeCount || 0 }));
  const like = s.likeCount || 0;
  const unlike = s.unlikeCount || 0;
  const totalFb = like + unlike;
  const none = Math.max(0, (s.questionCount || 0) - totalFb);
  const satisfaction = totalFb ? Math.round((like / totalFb) * 100) : 0;
  const fbSegments = [
    { label: '点赞', value: like, color: c.teal },
    { label: '点踩', value: unlike, color: c.rose },
    { label: '无反馈', value: none, color: 'var(--line-strong)' },
  ];
  const reasonColors = [c.rose, c.amber, c.violet, c.teal, c.accent];
  const reasons = (data.reasonTop || []).map((r, i) => ({ label: H.reasonLabel(r.reason), value: r.count || 0, color: reasonColors[i % reasonColors.length] }));
  const topUsers = (data.topUsers || []).map((u) => ({ user: u.userId, asks: u.questionCount || 0, sessions: u.conversationCount || 0 }));
  const maxAsks = topUsers.length ? topUsers[0].asks || 1 : 1;
  const recentUnlikes = data.recentUnlikes || [];

  const metrics = [
    { label: '活跃用户', value: String(s.activeUsers ?? 0), icon: 'users', foot: '范围内去重提问用户' },
    { label: '提问总数', value: String(s.questionCount ?? 0), icon: 'chat', foot: '用户发起的问题数' },
    { label: '会话数', value: String(s.conversationCount ?? 0), icon: 'layers', foot: '产生提问的会话数' },
    { label: '满意率', value: String(satisfaction), unit: '%', icon: 'thumb', foot: '点赞 / 总反馈' },
    { label: '点赞数', value: String(like), icon: 'thumb', foot: '正向反馈次数' },
    { label: '反馈率', value: H.pct(s.feedbackRate), unit: '%', icon: 'flag', foot: '反馈数 / 回复数' },
  ];

  return (
    <div className="view-pad fade-in view-fit">
      <div className="view-wrap">
        <div className="ops-filterbar">
          <div className="ofb-left">
            <DateRangePicker range={range} onChange={setRange} today={TODAY} />
            <Btn variant="primary" size="sm" icon="search" onClick={runQuery} disabled={refreshing}>查询</Btn>
          </div>
        </div>

        <div className={`ops-body ${refreshing ? 'refreshing' : ''}`}>
          <div className="metric-grid">
            {metrics.map((m) => <Metric key={m.label} {...m} />)}
          </div>

          <div className="ops-grid-2 grid-align">
            <Card className="span-2">
              <CardHead kicker="Usage Trend" title="每日使用趋势">
                <div className="legend">
                  <span><i style={{ background: c.accent }} />提问</span>
                  <span><i style={{ background: c.teal }} />点赞</span>
                  <span><i style={{ background: c.rose }} />点踩</span>
                </div>
              </CardHead>
              <div className="card-pad">
                {daily.length ? (
                  <LineChart data={daily} series={[{ key: 'ask' }, { key: 'like' }, { key: 'unlike', area: false }]} height={220} />
                ) : <Empty icon="chart">该时间范围暂无数据</Empty>}
              </div>
            </Card>

            <Card>
              <CardHead kicker="Feedback Quality" title="点赞 / 点踩概览" />
              <div className="card-pad" style={{ display: 'grid', gap: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
                  <Donut segments={totalFb ? fbSegments : [{ label: '无反馈', value: 1, color: 'var(--line-strong)' }]} centerLabel={`${satisfaction}%`} centerSub="满意率" />
                  <div style={{ display: 'grid', gap: 11, flex: 1 }}>
                    {fbSegments.map((seg) => (
                      <div key={seg.label} className="legend-row">
                        <i style={{ background: seg.color }} />
                        <span className="dim">{seg.label}</span>
                        <b className="mono">{seg.value}</b>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="kicker" style={{ marginBottom: 11 }}>点踩原因排行</div>
                  {reasons.length ? <HBars items={reasons} valueFmt={(v) => v} /> : <Empty icon="flag">暂无点踩原因</Empty>}
                </div>
              </div>
            </Card>
          </div>

          <div className="ops-grid-2 grid-flex">
            <Card>
              <CardHead kicker="User Ranking" title="高频使用用户" />
              <div className="card-pad">
                {topUsers.length ? (
                  <div className="rowlist list-scroll">
                    {topUsers.map((u, i) => (
                      <div key={u.user} className="row">
                        <span className={`rank ${i === 0 ? 'top' : ''}`}>{i + 1}</span>
                        <code className="mono" style={{ fontSize: 13, flex: 1 }}>{u.user}</code>
                        <div style={{ width: 120 }}>
                          <div style={{ height: 6, borderRadius: 999, background: 'var(--surface-inset)', overflow: 'hidden' }}>
                            <div style={{ width: `${(u.asks / maxAsks) * 100}%`, height: '100%', background: 'var(--accent)', borderRadius: 999 }} />
                          </div>
                        </div>
                        <span className="mono dim" style={{ fontSize: 12, width: 56, textAlign: 'right' }}>{u.asks} 问</span>
                        <span className="mono muted" style={{ fontSize: 11, width: 56, textAlign: 'right' }}>{u.sessions} 会话</span>
                      </div>
                    ))}
                  </div>
                ) : <Empty icon="users">当前范围暂无用户数据</Empty>}
              </div>
            </Card>

            <Card>
              <CardHead kicker="Recent Risks" title="最近点踩记录">
                {recentUnlikes.length > 0 && <Badge kind="bad">{recentUnlikes.length} 条待处理</Badge>}
              </CardHead>
              <div className="card-pad">
                {recentUnlikes.length ? (
                  <div className="rowlist list-scroll">
                    {recentUnlikes.map((r, i) => {
                      const types = r.reason?.feedbackInfoTypes || [];
                      const reasonText = types.map(H.reasonLabel).join(' / ') || '点踩';
                      return (
                        <div key={i} className="unlike-row">
                          <div className="ur-main">
                            <div className="ur-q">{r.query || '未记录问题'}</div>
                            <div className="ur-meta">
                              <code className="mono">{r.userId}</code>
                              {r.scene && <span className="badge neutral" style={{ fontSize: 10 }}>{r.scene}</span>}
                              <span className="mono muted">{r.timestamp}</span>
                            </div>
                          </div>
                          <Badge kind="bad">{reasonText}</Badge>
                        </div>
                      );
                    })}
                  </div>
                ) : <Empty icon="flag">当前范围暂无点踩记录</Empty>}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

window.OpsView = OpsView;
