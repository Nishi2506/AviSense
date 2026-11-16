import React from 'react';
import { FACTORS, FACTOR_LABELS, fmt } from '../lib/format';

/**
 * Each factor's weighted contribution to the risk score, drawn against that factor's weight
 * (its maximum possible contribution). The largest contribution is marked as the primary driver.
 */
export default function FactorBars({ contributions, weights, compact = false }) {
  const values = FACTORS.map((f) => contributions?.[f] ?? 0);
  const top = Math.max(...values);
  const maxWeight = Math.max(...FACTORS.map((f) => weights?.[f] ?? 0), 0.01);

  return (
    <div className={`flex flex-col ${compact ? 'gap-2.5' : 'gap-space-md'}`}>
      {FACTORS.map((f, i) => {
        const c = values[i];
        const w = weights?.[f] ?? 0;
        const primary = c > 0 && c === top;
        const color = primary ? 'bg-error' : c > 0 ? 'bg-secondary' : 'bg-primary';
        const text = primary ? 'text-error' : c > 0 ? 'text-secondary' : 'text-on-surface-variant';
        return (
          <div key={f} className="flex flex-col gap-1.5">
            <div className="flex justify-between items-baseline">
              <div className="flex items-center gap-1.5">
                <span className={`${compact ? 'font-label-sm text-[12px]' : 'font-body-md text-body-md'} text-on-surface font-medium`}>
                  {compact ? '' : `${i + 1}. `}
                  {FACTOR_LABELS[f]}
                </span>
                {primary && (
                  <span className="font-label-sm text-label-sm text-error px-1.5 py-0.5 rounded-DEFAULT bg-error-container/20">
                    Primary Driver
                  </span>
                )}
              </div>
              <span className={`font-label-md text-label-md font-semibold ${text}`}>
                {fmt(c)} <span className="text-on-surface-variant font-normal">/ {fmt(w)}</span>
              </span>
            </div>
            <div className="relative w-full h-2 rounded-full bg-surface-container-highest overflow-hidden">
              <div className="absolute inset-y-0 left-0 bg-surface-bright/60 rounded-full" style={{ width: `${(w / maxWeight) * 100}%` }} />
              <div className={`absolute inset-y-0 left-0 ${color} rounded-full transition-all duration-200`} style={{ width: `${(c / maxWeight) * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
