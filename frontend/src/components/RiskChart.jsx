import React, { useMemo } from 'react';
import { fmt, fmtVideoTime } from '../lib/format';

const W = 1000;
const H = 220;
const X0 = 60;
const X1 = 980;
const Y0 = 200; // score 0
const Y1 = 30; // score 1
const MAX_POINTS = 900;

const yOf = (s) => Y0 - s * (Y0 - Y1);

/** Risk score over video time with the Medium/High threshold lines (design: Live Monitoring chart). */
export default function RiskChart({ history, medium, high, wallStart = null }) {
  const { line, area, current, peak, ticks } = useMemo(() => {
    if (!history?.length) return {};
    const step = Math.max(1, Math.ceil(history.length / MAX_POINTS));
    const pts = history.filter((_, i) => i % step === 0 || i === history.length - 1);
    const t0 = history[0].t;
    const t1 = Math.max(history[history.length - 1].t, t0 + 1);
    const xOf = (t) => X0 + ((t - t0) / (t1 - t0)) * (X1 - X0);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'} ${xOf(p.t).toFixed(1)},${yOf(p.s).toFixed(1)}`).join(' ');
    const area = `${line} L ${xOf(pts[pts.length - 1].t).toFixed(1)},${Y0} L ${xOf(pts[0].t).toFixed(1)},${Y0} Z`;
    const last = history[history.length - 1];
    const top = history.reduce((a, b) => (b.s > a.s ? b : a), history[0]);
    const ticks = Array.from({ length: 5 }, (_, i) => {
      const t = t0 + ((t1 - t0) * i) / 4;
      let label = fmtVideoTime(t);
      if (wallStart) label = new Date(new Date(wallStart).getTime() + t * 1000).toTimeString().slice(0, 8);
      return { x: xOf(t), label };
    });
    return {
      line,
      area,
      current: { x: xOf(last.t), y: yOf(last.s), s: last.s },
      peak: { x: xOf(top.t), y: yOf(top.s), s: top.s },
      ticks
    };
  }, [history, wallStart]);

  return (
    <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox={`0 0 ${W} ${H}`}>
      {[0.25, 0.5, 0.75].map((v) => (
        <line key={v} stroke="#343535" strokeOpacity="0.3" strokeWidth="1" x1={X0} x2={X1} y1={yOf(v)} y2={yOf(v)} />
      ))}
      <line stroke="#ffb95f" strokeDasharray="4,4" strokeOpacity="0.8" strokeWidth="1" x1={X0} x2={X1} y1={yOf(medium)} y2={yOf(medium)} />
      <text fill="#ffb95f" fontFamily="JetBrains Mono" fontSize="10" fontWeight="500" x={X0 + 4} y={yOf(medium) - 5}>
        Medium ({fmt(medium)})
      </text>
      <line stroke="#ffb4ab" strokeDasharray="4,4" strokeOpacity="0.8" strokeWidth="1" x1={X0} x2={X1} y1={yOf(high)} y2={yOf(high)} />
      <text fill="#ffb4ab" fontFamily="JetBrains Mono" fontSize="10" fontWeight="500" x={X0 + 4} y={yOf(high) - 5}>
        High ({fmt(high)})
      </text>
      <line stroke="#343535" strokeWidth="1" x1={X0} x2={X1} y1={Y0} y2={Y0} />

      <defs>
        <linearGradient id="riskGradient" x1="0%" x2="0%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="#ff7a73" stopOpacity="0.25" />
          <stop offset="60%" stopColor="#ffb95f" stopOpacity="0.10" />
          <stop offset="100%" stopColor="#4edea3" stopOpacity="0.0" />
        </linearGradient>
      </defs>

      {line ? (
        <>
          <path d={area} fill="url(#riskGradient)" />
          <path d={line} fill="none" stroke="#4edea3" strokeLinejoin="round" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          {peak.s > 0 && (
            <g transform={`translate(${Math.min(Math.max(peak.x - 35, X0), X1 - 70)}, ${Math.max(peak.y - 30, 2)})`}>
              <rect fill="#1e2020" height="20" rx="2" stroke="#ff7a73" strokeWidth="1" width="70" />
              <text fill="#ffb4ab" fontFamily="JetBrains Mono" fontSize="10" fontWeight="600" textAnchor="middle" x="35" y="14">
                {fmt(peak.s)} PEAK
              </text>
            </g>
          )}
          <circle cx={current.x} cy={current.y} fill="#4edea3" r="4" stroke="#0d0e0f" strokeWidth="1.5" />
          {ticks.map((t, i) => (
            <text key={i} fill={i === 4 ? '#e3e2e2' : '#86948a'} fontFamily="JetBrains Mono" fontSize="10" textAnchor="middle" x={t.x} y="216">
              {t.label}
            </text>
          ))}
        </>
      ) : (
        <text fill="#86948a" fontFamily="JetBrains Mono" fontSize="11" textAnchor="middle" x={(X0 + X1) / 2} y={115}>
          No data yet: press Run to start monitoring
        </text>
      )}

      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <text key={v} fill="#86948a" fontFamily="JetBrains Mono" fontSize="10" textAnchor="end" x="45" y={yOf(v) + 3}>
          {fmt(v)}
        </text>
      ))}
    </svg>
  );
}
