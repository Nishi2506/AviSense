import React, { useEffect, useMemo, useState } from 'react';
import { useApp } from '../context/AppContext';
import LevelBadge from '../components/LevelBadge';
import { FACTORS, FACTOR_LABELS, episodeId, fileName, fmt, fmtClock, fmtDuration, fmtVideoTime, levelStyle } from '../lib/format';
import './AlertHistory.css';

const PAGE = 10;

function summary(a) {
  const driver = (FACTOR_LABELS[a.top_factor] || a.top_factor || 'unknown').toLowerCase();
  const where =
    a.min_dist === 0 ? 'At least one bird entered the runway zone.' : a.min_dist != null ? `Nearest bird came within ${fmt(a.min_dist)} of the frame diagonal of the runway zone.` : '';
  return `${a.peak_level} episode on ${fileName(a.source)} from ${fmtVideoTime(a.start_s)} to ${fmtVideoTime(a.end_s)} of the video (${fmtDuration(
    a.duration_s
  )}), peaking at ${fmt(a.peak_score)}. Main factor over the episode: ${driver}; up to ${a.max_count} bird(s) tracked at once. ${where}`;
}

export default function AlertHistory() {
  const { alerts, refreshAlerts, selectedEpisodeId, setSelectedEpisodeId } = useApp();
  const [riskFilter, setRiskFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('recent');
  const [page, setPage] = useState(0);

  useEffect(() => {
    refreshAlerts();
  }, [refreshAlerts]);

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return alerts.alerts
      .filter((a) => riskFilter === 'ALL' || a.peak_level?.toUpperCase() === riskFilter)
      .filter(
        (a) =>
          !q ||
          episodeId(a.id).toLowerCase().includes(q) ||
          (FACTOR_LABELS[a.top_factor] || '').toLowerCase().includes(q) ||
          String(a.source || '').toLowerCase().includes(q) ||
          String(a.camera || '').toLowerCase().includes(q)
      )
      .sort((a, b) => (sortBy === 'peak' ? b.peak_score - a.peak_score : sortBy === 'duration' ? b.duration_s - a.duration_s : b.id - a.id));
  }, [alerts, riskFilter, searchQuery, sortBy]);

  useEffect(() => setPage(0), [riskFilter, searchQuery, sortBy]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const shown = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const active = alerts.alerts.find((a) => a.id === selectedEpisodeId) || shown[0] || null;
  const hasContrib = active && FACTORS.some((f) => active[`c_${f}`] != null);
  const contribTotal = hasContrib ? FACTORS.reduce((s, f) => s + (active[`c_${f}`] || 0), 0) : 0;
  const topPeak = hasContrib ? FACTORS.reduce((best, f) => ((active[`c_${f}`] || 0) > (active[`c_${best}`] || 0) ? f : best), FACTORS[0]) : null;

  const filterBtn = (key, label, color) => (
    <button
      key={key}
      onClick={() => setRiskFilter(key)}
      className={`px-3 py-1 rounded-DEFAULT font-label-sm text-label-sm font-medium transition-colors cursor-pointer ${
        riskFilter === key ? `${color} bg-[#161818] border border-[#242828]` : `text-[#9ca3af] hover:bg-[#161818]`
      }`}
      type="button"
    >
      {label}
    </button>
  );

  return (
    <div className="flex flex-col w-full gap-space-lg pb-space-xl alert-history-container">
      <div className="flex flex-col gap-space-md border-b border-[#242828] pb-space-md">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm">
          <div>
            <h2 className="font-headline-lg text-headline-lg text-[#ffffff] tracking-tight font-semibold">Alert History</h2>
            <p className="font-body-sm text-body-sm text-[#9ca3af] mt-0.5">
              Alert episodes: consecutive frames at Medium or above, logged to outputs/alerts.db
            </p>
          </div>
          <button
            onClick={refreshAlerts}
            type="button"
            className="flex items-center gap-2 font-label-sm text-label-sm text-[#9ca3af] hover:text-white px-3 py-1.5 bg-[#111313] border border-[#242828] rounded-DEFAULT cursor-pointer"
          >
            <span className="w-2 h-2 rounded-full bg-[#10b981]"></span>
            <span>{alerts.total} EPISODES</span>
            <span className="text-[#242828]">|</span>
            <span className="material-symbols-outlined text-[14px]">refresh</span>
          </button>
        </div>

        <div className="bg-[#111313] border border-[#242828] p-2 rounded-DEFAULT flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1 bg-[#000000] p-1 rounded-DEFAULT border border-[#242828]">
            {filterBtn('ALL', 'All', 'text-[#ffffff]')}
            {filterBtn('HIGH', 'High Risk', 'text-[#ef4444]')}
            {filterBtn('MEDIUM', 'Medium Risk', 'text-[#f59e0b]')}
            {filterBtn('LOW', 'Low', 'text-[#10b981]')}
          </div>
          <div className="flex items-center gap-2 flex-1 min-w-[280px] justify-end">
            <div className="relative flex-1 max-w-xs">
              <span className="material-symbols-outlined absolute left-2.5 top-2 text-[16px] text-[#9ca3af]">search</span>
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-8 pl-8 pr-2 bg-[#000000] border border-[#242828] text-[#ffffff] font-body-sm text-body-sm rounded-DEFAULT focus:outline-none focus:border-[#10b981] placeholder-[#9ca3af]/50 transition-colors"
                placeholder="Search episode, source or factor..."
                type="text"
              />
            </div>
            <div className="relative">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="h-8 pl-2.5 pr-8 bg-[#000000] border border-[#242828] rounded-DEFAULT font-label-sm text-label-sm text-[#ffffff] appearance-none cursor-pointer focus:outline-none focus:border-[#10b981]"
              >
                <option value="recent">Sort by Most Recent</option>
                <option value="peak">Sort by Peak Score (High to Low)</option>
                <option value="duration">Sort by Duration</option>
              </select>
              <span className="material-symbols-outlined absolute right-2 top-2 text-[14px] text-[#9ca3af] pointer-events-none">expand_more</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
        <div className="lg:col-span-7 flex flex-col bg-[#111313] rounded-DEFAULT overflow-hidden border border-[#242828]">
          <div className="px-4 py-3 bg-[#161818] border-b border-[#242828] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] text-[#10b981]">table_rows</span>
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-[#ffffff] font-semibold">Alert Episodes</span>
            </div>
            <span className="font-label-sm text-label-sm text-[#9ca3af]">Times are video time (m:ss)</span>
          </div>

          <div className="overflow-x-auto w-full">
            <table className="w-full text-left border-collapse font-body-sm">
              <thead>
                <tr className="bg-[#000000] text-[#9ca3af] font-label-sm text-label-sm uppercase border-b border-[#242828]">
                  <th className="py-2.5 pl-4 pr-2 font-medium tracking-wider">Episode ID</th>
                  <th className="py-2.5 px-2 font-medium tracking-wider">Source</th>
                  <th className="py-2.5 px-2 font-medium tracking-wider">Start</th>
                  <th className="py-2.5 px-2 font-medium tracking-wider">Duration</th>
                  <th className="py-2.5 px-2 font-medium tracking-wider">Risk Level</th>
                  <th className="py-2.5 px-2 font-medium tracking-wider text-right">Peak</th>
                  <th className="py-2.5 pl-2 pr-4 font-medium tracking-wider">Main Factor</th>
                </tr>
              </thead>
              <tbody className="font-label-sm text-label-sm divide-y divide-[#242828]/50">
                {shown.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="py-8 text-center text-[#9ca3af]">
                      {alerts.total ? 'No episodes match the filter.' : 'No alert episodes logged yet. Run a video to create some.'}
                    </td>
                  </tr>
                ) : (
                  shown.map((a) => {
                    const s = levelStyle(a.peak_level);
                    const isSelected = active && a.id === active.id;
                    return (
                      <tr
                        key={a.id}
                        onClick={() => setSelectedEpisodeId(a.id)}
                        className={`cursor-pointer transition-colors ${isSelected ? `bg-[#161818] border-l-2 ${s.border} text-[#ffffff]` : 'hover:bg-[#161818] text-[#9ca3af]'}`}
                      >
                        <td className="py-2.5 pl-4 pr-2 font-semibold text-[#ffffff] font-mono">
                          {episodeId(a.id)}
                          {a.status === 'active' && <span className="ml-1 text-[10px] text-[#ef4444]">● LIVE</span>}
                        </td>
                        <td className="py-2.5 px-2 truncate max-w-[160px]" title={a.source}>
                          {fileName(a.source)}
                        </td>
                        <td className="py-2.5 px-2 text-[#9ca3af] font-mono">{fmtVideoTime(a.start_s)}</td>
                        <td className="py-2.5 px-2 text-[#ffffff]">{fmtDuration(a.duration_s)}</td>
                        <td className="py-2.5 px-2">
                          <LevelBadge level={a.peak_level} />
                        </td>
                        <td className={`py-2.5 px-2 text-right font-mono font-semibold ${s.text}`}>{fmt(a.peak_score)}</td>
                        <td className="py-2.5 pl-2 pr-4 truncate max-w-[130px]">{FACTOR_LABELS[a.top_factor] || a.top_factor}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-2.5 bg-[#161818] border-t border-[#242828] flex items-center justify-between font-label-sm text-label-sm text-[#9ca3af]">
            <span>
              Showing {shown.length} of {filtered.length} · Total {alerts.total} recorded
              {alerts.total > alerts.alerts.length ? ` (latest ${alerts.alerts.length} loaded)` : ''}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-2.5 py-1 rounded-DEFAULT bg-[#000000] border border-[#242828] text-[#ffffff] hover:bg-[#242828] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                type="button"
              >
                Previous
              </button>
              <span className="px-2 font-mono text-[#ffffff]">
                {page + 1} / {pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                disabled={page >= pages - 1}
                className="px-2.5 py-1 rounded-DEFAULT bg-[#000000] border border-[#242828] text-[#ffffff] hover:bg-[#242828] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {active && (
          <div className="lg:col-span-5 flex flex-col bg-[#111313] rounded-DEFAULT border border-[#242828] overflow-hidden">
            <div className="px-4 py-3 bg-[#161818] border-b border-[#242828] flex items-center justify-between">
              <div>
                <span className="font-label-sm text-label-sm text-[#9ca3af] uppercase tracking-wider block">Episode Details</span>
                <span className="font-headline-sm text-[16px] font-semibold text-[#ffffff] font-mono">{episodeId(active.id)}</span>
              </div>
              <LevelBadge level={active.peak_level}>
                {active.peak_level?.toUpperCase()} {fmt(active.peak_score)}
              </LevelBadge>
            </div>

            <div className="p-space-md flex flex-col gap-space-md">
              <div className="flex flex-col gap-2 bg-[#000000] p-3 rounded-DEFAULT border border-[#242828]">
                <span className="font-label-sm text-label-sm text-[#9ca3af] uppercase tracking-wider">Summary</span>
                <div className="grid grid-cols-2 gap-y-2 gap-x-4 font-label-sm text-label-sm pt-1">
                  <div className="flex flex-col">
                    <span className="text-[#9ca3af]">Start (video)</span>
                    <span className="text-[#ffffff] font-mono font-medium">
                      {fmtVideoTime(active.start_s)} · frame {active.start_frame}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[#9ca3af]">End (video)</span>
                    <span className="text-[#ffffff] font-mono font-medium">
                      {fmtVideoTime(active.end_s)} · frame {active.end_frame}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[#9ca3af]">Duration</span>
                    <span className="text-[#ffffff] font-medium">{fmtDuration(active.duration_s)}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[#9ca3af]">Wall-clock start</span>
                    <span className="text-[#ffffff] font-mono font-medium">
                      {active.started_at ? `${active.started_at.slice(0, 10)} ${fmtClock(active.started_at)}` : 'Unknown'}
                    </span>
                  </div>
                </div>
                <div className="border-t border-[#242828] pt-2 mt-1 grid grid-cols-2 gap-x-4">
                  <div className="flex flex-col">
                    <span className="font-label-sm text-label-sm text-[#9ca3af]">Main factor (whole episode)</span>
                    <span className="text-[#ffffff] font-medium text-[13px] mt-0.5">{FACTOR_LABELS[active.top_factor] || active.top_factor}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="font-label-sm text-label-sm text-[#9ca3af]">Source</span>
                    <span className="text-[#ffffff] font-medium text-[13px] mt-0.5 truncate" title={active.source}>
                      {fileName(active.source)} {active.camera ? `· ${active.camera}` : ''}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2 bg-[#000000] p-3 rounded-DEFAULT border border-[#242828]">
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm text-[#9ca3af] uppercase tracking-wider">Birds Involved</span>
                  <span className="font-label-sm text-label-sm text-[#ffffff] font-mono font-medium">up to {active.max_count} at once</span>
                </div>
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div className="p-2 bg-[#161818] border border-[#242828] rounded-DEFAULT">
                    <span className="text-[#9ca3af] font-label-sm text-[11px] block">Nearest to runway zone</span>
                    <span className="text-[#ffffff] font-mono font-medium text-[12px] mt-0.5 block">
                      {active.min_dist === 0 ? 'Inside zone' : active.min_dist != null ? `${fmt(active.min_dist)} diag` : 'Not recorded'}
                    </span>
                  </div>
                  <div className="p-2 bg-[#161818] border border-[#242828] rounded-DEFAULT">
                    <span className="text-[#9ca3af] font-label-sm text-[11px] block">Maximum speed</span>
                    <span className="text-[#ffffff] font-mono font-medium text-[12px] mt-0.5 block">
                      {active.max_speed != null ? `${fmt(active.max_speed)} diag/s` : 'Not recorded'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2 bg-[#000000] p-3 rounded-DEFAULT border border-[#242828]">
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm text-[#9ca3af] uppercase tracking-wider">Factor Contributions at Peak</span>
                  {hasContrib && <span className="font-label-sm text-[11px] text-[#ef4444] font-medium">Largest: {FACTOR_LABELS[topPeak]}</span>}
                </div>
                {hasContrib ? (
                  <div className="flex flex-col gap-2.5 font-label-sm text-[12px] pt-1">
                    {FACTORS.map((f) => {
                      const c = active[`c_${f}`] || 0;
                      const share = contribTotal > 0 ? c / contribTotal : 0;
                      const primary = f === topPeak && c > 0;
                      return (
                        <div key={f} className="flex flex-col gap-1">
                          <div className="flex justify-between items-center">
                            <span className={primary ? 'text-[#ffffff] font-medium' : 'text-[#9ca3af]'}>{FACTOR_LABELS[f]}</span>
                            <span className={`font-mono ${primary ? 'text-[#ef4444] font-semibold' : 'text-[#ffffff] font-medium'}`}>
                              {fmt(c)} <span className="text-[#9ca3af] font-normal">({Math.round(share * 100)}%)</span>
                            </span>
                          </div>
                          <div className="w-full h-1.5 bg-[#161818] rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${primary ? 'bg-[#ef4444]' : 'bg-[#f59e0b]'}`} style={{ width: `${share * 100}%` }}></div>
                          </div>
                        </div>
                      );
                    })}
                    <span className="text-[#9ca3af] text-[11px]">Weighted contributions sum to the raw score at the peak frame; % = share of it.</span>
                  </div>
                ) : (
                  <p className="font-body-sm text-[12px] text-[#9ca3af]">Not recorded for this episode (logged before contributions were stored).</p>
                )}
              </div>

              <div className="flex flex-col gap-1.5 bg-[#161818] p-3 rounded-DEFAULT border border-[#242828]">
                <div className="flex items-center gap-1.5 text-[#9ca3af] font-label-sm text-[11px] uppercase tracking-wider">
                  <span className="material-symbols-outlined text-[14px] text-[#10b981]">description</span>
                  <span>Episode Summary</span>
                </div>
                <p className="font-body-sm text-[12px] text-[#ffffff] leading-relaxed">{summary(active)}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
