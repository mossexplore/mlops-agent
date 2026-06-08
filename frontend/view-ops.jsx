/* Ops dashboard view — wired to /agent/v1/ops/dashboard */
const { useState: useStateO, useEffect: useEffectO } = React;

function OpsView() {
  const c = useAccent();
  const [days, setDays] = useStateO(7);
  const [data, setData] = useStateO(null);
  const [loading, setLoading] = useStateO(true);
  const [error, setError] = useStateO('');

  function load(range) {
    setLoading(true);
    setError('');
    API.opsDashboard(H.rangeDates(range))
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffectO(() => { load(days); }, [days]);

  if (loading && !data) return <div className="view-pad"><Empty icon="chart">正在加载运营数据…</Empty></div>;
  if (error) return <div className="view-pad"><Empty icon="alert">{error}</Empty></div>;
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

  const rangeLabel = data.range ? `${data.range.startDate} → ${data.range.endDate}` : '';

  return (
    <div className="view-pad fade-in">
      <div className="view-wrap">
        <div className="ops-filterbar">
          <div className="ofb-left">
            <Icon name="filter" size={15} style={{ color: 'var(--text-mute)' }} />
            <span className="mono" style={{ fontSize: 12, color: 'var(--text-dim)' }}>{rangeLabel}</span>
          </div>
          <div className="ofb-right">
            <div className="seg">
              <button className={days === 1 ? 'on' : ''} onClick={() => setDays(1)}>近 24h</button>
              <button className={days === 7 ? 'on' : ''} onClick={() => setDays(7)}>近 7 天</button>
              <button className={days === 30 ? 'on' : ''} onClick={() => setDays(30)}>近 30 天</button>
            </div>
            <Btn variant="ghost" size="sm" icon="refresh" onClick={() => load(days)}>刷新</Btn>
          </div>
        </div>

        <div className="metric-grid">
          {metrics.map((m) => <Metric key={m.label} {...m} />)}
        </div>

        <div className="ops-grid-2">
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
                <LineChart data={daily} series={[{ key: 'ask' }, { key: 'like' }, { key: 'unlike', area: false }]} height={250} />
              ) : <Empty icon="chart">当前范围暂无使用数据</Empty>}
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

        <div className="ops-grid-2">
          <Card>
            <CardHead kicker="User Ranking" title="高频使用用户" />
            <div className="card-pad">
              {topUsers.length ? (
                <div className="rowlist">
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
                <div className="rowlist">
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
  );
}

window.OpsView = OpsView;
