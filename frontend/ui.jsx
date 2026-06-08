/* Shared UI primitives + bespoke SVG charts */
const { useState, useRef, useEffect } = React;

/* ---------- atoms ---------- */
function Kicker({ children, style }) {
  return <div className="kicker" style={style}>{children}</div>;
}

function Badge({ children, kind = '', mono, className = '' }) {
  return <span className={`badge ${kind} ${mono ? 'badge-mono' : ''} ${className}`}>{children}</span>;
}

const STATUS_LABEL = { draft: '草稿', review: '待审核', published: '已发布', archived: '已归档' };
function Lifecycle({ status }) {
  return <span className={`lc ${status}`}><i className="dot" />{STATUS_LABEL[status] || status}</span>;
}

const RISK_LABEL = { low: '低风险', medium: '中风险', high: '高风险' };
function Risk({ level }) {
  return <span className={`risk ${level}`}>{RISK_LABEL[level] || level}</span>;
}

function Sev({ level }) {
  return <span className={`sev ${level}`}>{level}</span>;
}

function Btn({ children, variant = '', size = '', icon, onClick, type = 'button', disabled, className = '', title }) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title}
      className={`btn ${variant} ${size} ${className}`}>
      {icon && <Icon name={icon} size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  );
}

function Card({ children, className = '', style }) {
  return <div className={`card ${className}`} style={style}>{children}</div>;
}
function CardHead({ kicker, title, children }) {
  return (
    <div className="card-head">
      <div className="ch-titles">
        {kicker && <Kicker>{kicker}</Kicker>}
        <h3>{title}</h3>
      </div>
      {children && <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>{children}</div>}
    </div>
  );
}

function Toggle({ checked, onChange, label }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" />
      {label && <span className="tg-label">{label}</span>}
    </label>
  );
}

function Segmented({ options, value, onChange }) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.value} className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

function Delta({ value, up }) {
  return (
    <span className={`delta ${up ? 'up' : 'down'}`}>
      <Icon name={up ? 'arrowUp' : 'arrowDown'} size={12} />
      {Math.abs(value)}%
    </span>
  );
}

function Metric({ label, value, unit, icon, delta, up, foot }) {
  return (
    <div className="metric fade-in">
      <div className="m-top">
        <span className="m-label">{label}</span>
        {icon && <span className="m-ico"><Icon name={icon} size={16} /></span>}
      </div>
      <div className="m-val">{value}{unit && <small>{unit}</small>}</div>
      <div className="m-foot">
        {typeof delta === 'number' && <Delta value={delta} up={up} />}
        <span>{foot}</span>
      </div>
    </div>
  );
}

function Empty({ icon = 'info', children }) {
  return <div className="empty"><Icon name={icon} size={26} />{children}</div>;
}

/* ---------- charts ---------- */
function useAccent() {
  // resolve css vars to concrete colors for canvas/SVG gradients
  const root = getComputedStyle(document.documentElement);
  return {
    accent: root.getPropertyValue('--accent').trim(),
    bright: root.getPropertyValue('--accent-bright').trim(),
    teal: root.getPropertyValue('--viz-teal').trim(),
    rose: root.getPropertyValue('--viz-rose').trim(),
    amber: root.getPropertyValue('--viz-amber').trim(),
    violet: root.getPropertyValue('--viz-violet').trim(),
    line: root.getPropertyValue('--line').trim(),
    text: root.getPropertyValue('--text-mute').trim(),
  };
}

/* multi-series line/area chart */
function LineChart({ data, series, height = 230 }) {
  const c = useAccent();
  const W = 720, H = height, padL = 36, padR = 14, padT = 16, padB = 28;
  const max = Math.max(...data.flatMap((d) => series.map((s) => d[s.key]))) * 1.12;
  const x = (i) => padL + (i / (data.length - 1)) * (W - padL - padR);
  const y = (v) => padT + (1 - v / max) * (H - padT - padB);
  const gid = useRef('lg' + Math.random().toString(36).slice(2));

  const colorMap = { ask: c.accent, like: c.teal, unlike: c.rose };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: 'block' }}>
      <defs>
        {series.map((s) => (
          <linearGradient key={s.key} id={`${gid.current}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colorMap[s.key] || c.accent} stopOpacity="0.28" />
            <stop offset="100%" stopColor={colorMap[s.key] || c.accent} stopOpacity="0" />
          </linearGradient>
        ))}
      </defs>
      {/* gridlines */}
      {[0, 0.25, 0.5, 0.75, 1].map((g, i) => (
        <line key={i} x1={padL} x2={W - padR} y1={padT + g * (H - padT - padB)} y2={padT + g * (H - padT - padB)}
          stroke={c.line} strokeWidth="1" />
      ))}
      {/* x labels */}
      {data.map((d, i) => (
        <text key={i} x={x(i)} y={H - 8} fill={c.text} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">{d.d}</text>
      ))}
      {series.map((s) => {
        const col = colorMap[s.key] || c.accent;
        const pts = data.map((d, i) => `${x(i)},${y(d[s.key])}`);
        const area = `M${x(0)},${y(0)} L${pts.join(' L')} L${x(data.length - 1)},${y(0)} Z`;
        const line = `M${pts.join(' L')}`;
        return (
          <g key={s.key}>
            {s.area !== false && <path d={area} fill={`url(#${gid.current}-${s.key})`} />}
            <path d={line} fill="none" stroke={col} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
            {data.map((d, i) => <circle key={i} cx={x(i)} cy={y(d[s.key])} r="2.6" fill="var(--bg-canvas)" stroke={col} strokeWidth="1.8" />)}
          </g>
        );
      })}
    </svg>
  );
}

/* donut */
function Donut({ segments, size = 150, thickness = 20, centerLabel, centerSub }) {
  const c = useAccent();
  const total = segments.reduce((a, s) => a + s.value, 0);
  const R = (size - thickness) / 2;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={cx} cy={cy} r={R} fill="none" stroke={c.line} strokeWidth={thickness} />
        {segments.map((s, i) => {
          const frac = s.value / total;
          const dash = `${frac * circ} ${circ}`;
          const el = <circle key={i} cx={cx} cy={cy} r={R} fill="none" stroke={s.color} strokeWidth={thickness}
            strokeDasharray={dash} strokeDashoffset={-acc * circ} strokeLinecap="butt" />;
          acc += frac;
          return el;
        })}
      </svg>
      {centerLabel && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center' }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 750, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>{centerLabel}</div>
            {centerSub && <div style={{ fontSize: 11, color: 'var(--text-mute)', marginTop: 2 }}>{centerSub}</div>}
          </div>
        </div>
      )}
    </div>
  );
}

/* horizontal bars */
function HBars({ items, max, color, valueFmt }) {
  const c = useAccent();
  const mx = max || Math.max(...items.map((i) => i.value));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
      {items.map((it, i) => (
        <div key={i}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5, fontSize: 12 }}>
            <span className="dim">{it.label}</span>
            <span className="mono" style={{ color: 'var(--text)', fontWeight: 600 }}>{valueFmt ? valueFmt(it.value) : it.value}</span>
          </div>
          <div style={{ height: 7, borderRadius: 999, background: 'var(--surface-inset)', overflow: 'hidden' }}>
            <div style={{ width: `${(it.value / mx) * 100}%`, height: '100%', borderRadius: 999, background: it.color || color || 'var(--accent)' }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* sparkline */
function Sparkline({ values, color = 'var(--accent)', w = 90, h = 28 }) {
  const max = Math.max(...values), min = Math.min(...values);
  const rng = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / rng) * (h - 4) - 2}`);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <path d={`M${pts.join(' L')}`} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Toast({ msg, show }) {
  return (
    <div className={`toast ${show ? 'show' : ''}`}>
      <Icon name="check" size={18} className="ti" />
      {msg}
    </div>
  );
}

Object.assign(window, {
  Kicker, Badge, Lifecycle, Risk, Sev, Btn, Card, CardHead, Toggle, Segmented,
  Delta, Metric, Empty, LineChart, Donut, HBars, Sparkline, Toast, useAccent, STATUS_LABEL,
});
