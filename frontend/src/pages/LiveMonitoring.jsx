import React from 'react';
import { useApp } from '../context/AppContext';
import VideoFeed from '../components/VideoFeed';
import FactorBars from '../components/FactorBars';
import RiskChart from '../components/RiskChart';
import { FACTOR_LABELS, fmt, fmtVideoTime, levelStyle } from '../lib/format';
import './LiveMonitoring.css';

function Card({ title, children, footerLabel, footer }) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/30 rounded-xl p-space-lg flex flex-col justify-between shadow-sm min-h-[148px]">
      <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">{title}</span>
      <div className="flex items-baseline gap-space-md py-space-xs">{children}</div>
      <div className="pt-space-sm border-t border-outline-variant/30 flex items-center justify-between">
        <span className="font-body-sm text-body-sm text-on-surface-variant">{footerLabel}</span>
        {footer}
      </div>
    </div>
  );
}

export default function LiveMonitoring() {
  const { snapshot, status, history, settings, config, startRun, canRun, medThreshold, highThreshold } = useApp();

  const levels = snapshot?.config?.levels || { medium: medThreshold, high: highThreshold };
  const weights = snapshot?.config?.weights || config?.risk?.weights;
  const risk = snapshot?.risk;
  const f = risk?.features || {};
  const style = levelStyle(risk?.level);
  const hasRun = status !== 'idle' && snapshot?.run_id > 0;
  const proximityRange = config?.risk?.normalise?.proximity_range ?? 0.3;
  const wallStart = snapshot?.params?.start_time;
  const nTracks = snapshot?.tracks?.length ?? 0;

  return (
    <div className="flex flex-col w-full live-monitoring-container">
      <div className="flex flex-col gap-space-lg w-full max-w-[1720px] mx-auto pb-space-xl">
        {/* 1. Key data row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md">
          <Card
            title="Overall Risk Assessment"
            footerLabel={snapshot?.alert ? 'Alert active' : 'Severity'}
            footer={
              <span className={`font-label-sm text-label-sm font-medium ${style.text}`}>
                {snapshot?.alert
                  ? `${snapshot.alert.peak_level} episode · ${FACTOR_LABELS[snapshot.alert.top_factor] || snapshot.alert.top_factor}`
                  : risk?.level === 'High'
                  ? `High (≥ ${fmt(levels.high)})`
                  : risk?.level === 'Medium'
                  ? `Medium (${fmt(levels.medium)} – ${fmt(levels.high)})`
                  : `Low (< ${fmt(levels.medium)})`}
              </span>
            }
          >
            <span className={`font-metric-display text-metric-display font-semibold tracking-tight ${risk ? style.text : 'text-on-surface-variant'}`}>
              {risk ? risk.level.toUpperCase() : '—'}
            </span>
            <span className="font-metric-display text-metric-display text-on-surface font-semibold tracking-tight">{risk ? fmt(risk.score) : ''}</span>
          </Card>

          <Card
            title="Tracked Birds"
            footerLabel="Largest flock / in zone"
            footer={
              <span className="font-label-sm text-label-sm text-primary flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                {risk ? `${f.flock_size} in flock · ${f.n_in_zone} in zone` : '—'}
              </span>
            }
          >
            <span className="font-metric-display text-metric-display text-on-surface font-semibold tracking-tight">{risk ? f.count : '—'}</span>
          </Card>

          <Card
            title="Speed & Runway Distance"
            footerLabel="Nearest bird to runway zone"
            footer={
              <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
                {f.min_dist_to_zone === 0 ? 'Inside zone' : f.min_dist_to_zone != null ? `${fmt(f.min_dist_to_zone)} diag` : 'No birds'}
              </span>
            }
          >
            <span className="font-metric-display text-metric-display text-on-surface font-semibold tracking-tight">
              {risk ? fmt(f.max_speed) : '—'}{' '}
              <span className="font-body-sm text-body-sm text-on-surface-variant font-normal" title="Frame diagonals per second">
                diag/s fastest
              </span>
            </span>
          </Card>
        </div>

        {/* 2. Video + factor contributions */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md items-stretch">
          <div className="lg:col-span-7 bg-surface-container-low border border-outline-variant/30 rounded-xl p-space-md flex flex-col justify-between shadow-sm">
            <div className="flex items-center justify-between pb-space-sm mb-space-sm gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2 h-2 rounded-full ${status === 'running' ? 'bg-error animate-pulse' : 'bg-outline'}`}></span>
                <span className="font-headline-sm text-headline-sm text-on-surface font-semibold tracking-tight truncate">
                  Camera Feed — {snapshot?.source?.name || 'not running'}
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider whitespace-nowrap">
                {snapshot?.source?.camera ? `Zones: ${snapshot.source.camera}` : ''}
              </span>
            </div>

            {hasRun && snapshot?.frame?.seq !== undefined ? (
              <VideoFeed snapshot={snapshot} proximityRange={proximityRange} className="rounded-lg" />
            ) : (
              <div className="relative w-full aspect-video rounded-lg bg-surface-container-lowest flex flex-col items-center justify-center gap-space-sm text-center p-space-lg">
                {status === 'loading' ? (
                  <>
                    <span className="material-symbols-outlined text-primary text-[36px] animate-spin">refresh</span>
                    <span className="font-label-md text-label-md text-on-surface">{snapshot?.step || 'Starting…'}</span>
                  </>
                ) : status === 'error' ? (
                  <>
                    <span className="material-symbols-outlined text-error text-[32px]">error</span>
                    <span className="font-body-md text-body-md text-on-surface max-w-md">{snapshot.error}</span>
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-on-surface-variant text-[32px]">videocam_off</span>
                    <span className="font-body-md text-body-md text-on-surface-variant">No run yet. Choose a video and zones in the sidebar.</span>
                    <button
                      type="button"
                      onClick={startRun}
                      disabled={!canRun}
                      className="h-9 px-space-lg bg-primary text-on-primary font-label-md text-label-md font-semibold rounded-DEFAULT hover:bg-primary-fixed-dim transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span className="material-symbols-outlined text-[16px]">play_arrow</span> Run
                    </button>
                  </>
                )}
              </div>
            )}

            <div className="flex items-center justify-between pt-space-sm mt-space-xs font-label-sm text-label-sm text-on-surface-variant gap-2">
              <span>
                {snapshot?.frame?.t !== undefined
                  ? `Frame ${snapshot.frame.idx}${snapshot.source?.frames ? ` / ${snapshot.source.frames}` : ''} · ${fmtVideoTime(snapshot.frame.t)}`
                  : 'Boxes: red inside zone, amber near it, green elsewhere'}
              </span>
              <span className="text-primary font-mono font-medium">
                {snapshot?.source?.width ? `${snapshot.source.width}×${snapshot.source.height} · ` : ''}
                {status === 'running' ? `${fmt(snapshot.proc_fps, 1)} FPS processed` : ''}
                {nTracks ? ` · ${nTracks} tracks` : ''}
              </span>
            </div>
          </div>

          <div className="lg:col-span-5 bg-surface-container-low border border-outline-variant/30 rounded-xl p-space-lg flex flex-col justify-between shadow-sm">
            <div>
              <div className="pb-space-sm mb-space-md">
                <h2 className="font-headline-sm text-headline-sm text-on-surface font-semibold tracking-tight">Factor Contributions</h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                  Weighted contribution to the current score; pale track = the factor's weight (its maximum)
                </p>
              </div>
              <FactorBars contributions={risk?.contributions} weights={weights} />
            </div>
            <div className="pt-space-md mt-space-md flex items-center justify-between text-on-surface-variant font-label-sm text-label-sm border-t border-outline-variant/30">
              <span>Raw (this frame): {fmt(risk?.raw)}</span>
              <span>
                Score ({snapshot?.config?.smoothing_frames ?? config?.risk?.smoothing_frames}-frame mean): {fmt(risk?.score)}
              </span>
            </div>
          </div>
        </div>

        {/* 3. Risk over time */}
        <div className="w-full bg-surface-container-low border border-outline-variant/30 rounded-xl p-space-lg flex flex-col shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between pb-space-sm mb-space-md gap-space-sm">
            <div>
              <h2 className="font-headline-sm text-headline-sm text-on-surface font-semibold tracking-tight">Risk Score Over Time (This Run)</h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                {wallStart ? 'Wall-clock time in the video' : 'Video time (m:ss)'} · every processed frame
              </p>
            </div>
            <div className="flex items-center gap-space-md font-label-sm text-label-sm">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-primary shrink-0"></span>
                <span className="text-on-surface-variant">Low (&lt; {fmt(levels.medium)})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-secondary shrink-0"></span>
                <span className="text-on-surface-variant">
                  Medium ({fmt(levels.medium)} - {fmt(levels.high)})
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-error shrink-0"></span>
                <span className="text-on-surface">High (≥ {fmt(levels.high)})</span>
              </div>
            </div>
          </div>
          <div className="w-full h-56 relative">
            <RiskChart history={history} medium={levels.medium} high={levels.high} wallStart={wallStart} />
          </div>
          <div className="flex items-center justify-between pt-space-sm mt-space-sm font-label-sm text-label-sm text-on-surface-variant border-t border-outline-variant/30">
            <span>
              {history.length ? `${history.length} frames · ${history.filter((p) => p.l !== 'Low').length} at Medium or above` : 'Waiting for data'}
            </span>
            <span>
              Alert episodes this run: {snapshot?.alerts_closed ?? 0}
              {snapshot?.alert ? ' + 1 active' : ''}
            </span>
          </div>
        </div>
        {settings && !snapshot?.config && (
          <p className="font-label-sm text-label-sm text-on-surface-variant">Thresholds and weights from Settings apply when you press Run.</p>
        )}
      </div>
    </div>
  );
}
