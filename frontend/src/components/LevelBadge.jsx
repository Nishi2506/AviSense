import React from 'react';
import { levelStyle } from '../lib/format';

export default function LevelBadge({ level, children }) {
  const s = levelStyle(level);
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-DEFAULT font-medium text-[11px] font-label-sm ${s.chip}`}>
      <span className="material-symbols-outlined text-[13px]">{s.icon}</span>
      {children ?? level}
    </span>
  );
}
