import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import VideoFeed from '../components/VideoFeed';
import LevelBadge from '../components/LevelBadge';
import { FACTOR_LABELS, episodeId, fileName, fmt, fmtClock, fmtDuration, fmtVideoTime, levelStyle } from '../lib/format';
import './StartPage.css';

export default function StartPage() {
  const navigate = useNavigate();
  const {
    config,
    configError,
    selectedVideo,
    isWebcam,
    zonesFile,
    settings,
    snapshot,
    status,
    systemState,
    canRun,
    startRun,
    stopToStandby,
    runError,
    alerts,
    medThreshold,
    highThreshold,
    setSelectedEpisodeId
  } = useApp();

  const recent = alerts.alerts.slice(0, 4);
  const highCount = alerts.alerts.filter((a) => a.peak_level === 'High').length;
  const active = status === 'running' || status === 'loading';
  const sourceLabel = active
    ? snapshot?.source?.name || fileName(snapshot?.params?.source)
    : isWebcam
    ? 'Webcam (device 0)'
    : selectedVideo?.name || 'No video selected';
  const shownZones = active ? snapshot?.params?.zones : zonesFile;
  const shownVideo = active ? snapshot?.source : selectedVideo;
  const risk = snapshot?.risk;
  const style = levelStyle(risk?.level);
  const proximityRange = config?.risk?.normalise?.proximity_range ?? 0.3;
  const weightsName = fileName(settings?.detectorWeights);

  const inspect = (id) => {
    setSelectedEpisodeId(id);
    navigate('/alerts');
  };

  return (
    <div className="flex flex-col w-full start-page-container">
      {/* Status ribbon */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-space-md pb-space-lg mb-space-lg border-b border-outline-variant/30">
        <div className="flex flex-col gap-space-xs min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">{active ? 'Running Source' : 'Selected Source'}</span>
            <span className="text-outline-variant">/</span>
            <span className="font-label-sm text-label-sm text-primary tracking-wide">{shownZones ? `ZONES ${shownZones}` : 'NO ZONES FILE'}</span>
          </div>
          <div className="flex items-baseline gap-space-md min-w-0">
            <h2 className="font-headline-lg text-headline-lg text-on-surface tracking-tight font-semibold truncate">{sourceLabel}</h2>
            {shownVideo?.width > 0 && (
              <span className="font-label-md text-label-md text-on-surface-variant font-medium whitespace-nowrap">
                {shownVideo.width}×{shownVideo.height} · {fmt(shownVideo.fps, 0)} fps
                {shownVideo.frames > 0 ? ` · ${fmtVideoTime(shownVideo.frames / (shownVideo.fps || 25))}` : ''}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-DEFAULT bg-surface-container-low border border-outline-variant/30 font-label-sm text-label-sm">
          <span className="text-outline">SYSTEM:</span>
          {configError ? (
            <span className="text-error font-medium">API SERVER NOT REACHABLE</span>
          ) : systemState === 'LIVE' ? (
            <span className="text-primary font-medium flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span> MONITORING
            </span>
          ) : systemState === 'CALIBRATING' ? (
            <span className="text-secondary font-medium flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span> STARTING
            </span>
          ) : (
            <span className="text-primary font-medium flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-primary"></span> READY
            </span>
          )}
        </div>
      </section>

      {configError && (
        <div className="mb-space-lg p-space-md rounded-DEFAULT border border-error/40 bg-error-container/20 font-body-sm text-body-sm text-on-surface">
          Cannot reach the AviSense API ({configError}). Start it from the project root with{' '}
          <code className="font-mono text-primary">python -m src.api.server</code>.
        </div>
      )}

      {/* Overview cards */}
      <section className="flex flex-col gap-space-md mb-space-xl">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md">
          <div className="p-space-md bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-space-xs">
                <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Risk Factors</span>
                <span className="font-label-sm text-label-sm text-primary font-semibold">05 FACTORS</span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-medium mb-space-xs">5 Risk Factors Evaluated</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-md">
                A transparent weighted formula: every alert keeps each factor's contribution, so it says why.
              </p>
            </div>
            <div className="flex flex-wrap gap-1 border-t border-outline-variant/20 pt-space-sm">
              {Object.values(FACTOR_LABELS).map((l) => (
                <span key={l} className="px-2 py-0.5 bg-surface-container text-on-surface-variant font-label-sm text-label-sm rounded-DEFAULT border border-outline-variant/20">
                  {l}
                </span>
              ))}
            </div>
          </div>

          <div className="p-space-md bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-space-xs">
                <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Classification</span>
                <span className="font-label-sm text-label-sm text-on-surface font-semibold">configs/risk.yaml</span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-medium mb-space-xs">Risk Levels</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-md">
                Score in [0, 1], smoothed over {config?.risk?.smoothing_frames ?? 15} frames, then classified.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-1 border-t border-outline-variant/20 pt-space-sm font-label-sm text-label-sm">
              <div className="flex flex-col px-2 py-1 bg-surface-container rounded-DEFAULT border border-outline-variant/20">
                <span className="text-primary font-medium">LOW</span>
                <span className="text-on-surface-variant">&lt; {medThreshold.toFixed(2)}</span>
              </div>
              <div className="flex flex-col px-2 py-1 bg-surface-container rounded-DEFAULT border border-outline-variant/20">
                <span className="text-secondary font-medium">MEDIUM</span>
                <span className="text-on-surface-variant">
                  {medThreshold.toFixed(2)}–{highThreshold.toFixed(2)}
                </span>
              </div>
              <div className="flex flex-col px-2 py-1 bg-surface-container rounded-DEFAULT border border-outline-variant/20">
                <span className="text-error font-medium">HIGH</span>
                <span className="text-on-surface-variant">≥ {highThreshold.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="p-space-md bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-space-xs">
                <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Pipeline</span>
                <span className="font-label-sm text-label-sm text-primary font-semibold">{config?.system?.device || '—'}</span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-medium mb-space-xs">Processing Chain</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-md">
                Camera-based detection of birds ~6 px in size, tracked across frames and scored per frame.
              </p>
            </div>
            <div className="flex items-center justify-between border-t border-outline-variant/20 pt-space-sm font-label-sm text-label-sm text-on-surface-variant">
              <span className="font-medium text-on-surface">OpenCV</span>
              <span className="material-symbols-outlined text-[12px] text-outline">arrow_forward</span>
              <span className="font-medium text-on-surface">YOLO11n-P2</span>
              <span className="material-symbols-outlined text-[12px] text-outline">arrow_forward</span>
              <span className="font-medium text-on-surface">ByteTrack</span>
              <span className="material-symbols-outlined text-[12px] text-outline">arrow_forward</span>
              <span className="font-medium text-primary">Risk</span>
            </div>
          </div>
        </div>
      </section>

      {/* Monitoring panel */}
      <section className="mb-space-xl">
        <div className="relative w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT overflow-hidden min-h-[440px] flex flex-col justify-between">
          {systemState === 'STANDBY' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-space-xl z-20">
              <div className="absolute inset-0 opacity-15 pointer-events-none">
                <svg className="w-full h-full" fill="none" viewBox="0 0 800 400" preserveAspectRatio="xMidYMid slice">
                  <defs>
                    <pattern height="40" id="runway-grid" patternUnits="userSpaceOnUse" width="40">
                      <path className="text-outline-variant" d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5"></path>
                    </pattern>
                  </defs>
                  <rect fill="url(#runway-grid)" height="100%" width="100%"></rect>
                  <circle className="text-outline" cx="400" cy="200" r="140" stroke="currentColor" strokeDasharray="4 4" strokeWidth="0.75"></circle>
                  <circle className="text-outline" cx="400" cy="200" r="80" stroke="currentColor" strokeWidth="0.75"></circle>
                  <circle className="text-primary" cx="400" cy="200" fill="currentColor" r="6"></circle>
                </svg>
              </div>

              <div className="relative z-10 flex flex-col items-center text-center max-w-xl">
                <div className="w-12 h-12 bg-surface-container border border-outline-variant/40 rounded-DEFAULT flex items-center justify-center text-primary mb-space-md">
                  <span className="material-symbols-outlined text-[24px]">{status === 'error' ? 'error' : 'videocam'}</span>
                </div>
                {status === 'finished' || status === 'stopped' ? (
                  <>
                    <h3 className="font-headline-lg text-headline-lg text-on-surface font-semibold mb-space-xs">
                      Run {status === 'finished' ? 'finished' : 'stopped'}
                    </h3>
                    <p className="font-body-md text-body-md text-on-surface-variant mb-space-lg leading-relaxed">
                      {snapshot?.source?.name}: {snapshot?.frame?.idx + 1 || 0} frames processed, {snapshot?.alerts_closed ?? 0} alert episode(s)
                      logged. The last frame and full timeline stay on Live Monitoring.
                    </p>
                  </>
                ) : status === 'error' ? (
                  <>
                    <h3 className="font-headline-lg text-headline-lg text-on-surface font-semibold mb-space-xs">The last run failed</h3>
                    <p className="font-body-md text-body-md text-error mb-space-lg leading-relaxed">{snapshot?.error}</p>
                  </>
                ) : (
                  <>
                    <h3 className="font-headline-lg text-headline-lg text-on-surface font-semibold mb-space-xs">Ready to Begin Monitoring</h3>
                    <p className="font-body-md text-body-md text-on-surface-variant mb-space-lg leading-relaxed">
                      Choose a video source and runway zones in the sidebar, then press Run to start detection, tracking and risk scoring.
                    </p>
                  </>
                )}
                <div className="flex flex-col sm:flex-row items-center gap-space-sm w-full justify-center">
                  <button
                    onClick={startRun}
                    disabled={!canRun}
                    className="btn-idle-glow h-10 px-space-xl bg-primary text-on-primary font-label-md text-label-md font-semibold rounded-DEFAULT hover:bg-primary-fixed hover:scale-105 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                    type="button"
                  >
                    <span className="material-symbols-outlined text-[18px]">play_circle</span>
                    {status === 'finished' || status === 'stopped' ? 'Run Again' : 'Start Run'}
                  </button>
                  <div className="h-10 px-space-md bg-surface-container border border-outline-variant/30 rounded-DEFAULT flex items-center gap-2 text-on-surface-variant font-label-sm text-label-sm">
                    <span className="material-symbols-outlined text-[16px] text-outline">tune</span>
                    <span>
                      Thresh: {medThreshold.toFixed(2)} / {highThreshold.toFixed(2)} · imgsz {settings?.imgsz ?? '—'}
                    </span>
                  </div>
                </div>
                {runError && <p className="mt-space-sm font-label-sm text-label-sm text-error">{runError}</p>}
              </div>

              <div className="absolute bottom-3 left-space-md right-space-md flex items-center justify-between text-outline font-label-sm text-label-sm pointer-events-none">
                <span>WEIGHTS: {weightsName || '—'}</span>
                <span>{config?.system?.gpu || 'CPU only'}</span>
              </div>
            </div>
          )}

          {systemState === 'CALIBRATING' && (
            <div className="absolute inset-0 bg-surface-container-lowest/95 backdrop-blur-md flex flex-col items-center justify-center z-30">
              <div className="flex flex-col items-center text-center max-w-md p-6">
                <div className="relative w-16 h-16 mb-4 flex items-center justify-center">
                  <span className="material-symbols-outlined text-primary text-[42px] animate-spin">refresh</span>
                  <span className="material-symbols-outlined text-primary text-[18px] absolute">sensors</span>
                </div>
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-surface-container border border-primary/30 text-primary font-label-sm text-label-sm mb-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping"></span>
                  <span>STARTING RUN</span>
                </div>
                <h4 className="font-headline-sm text-on-surface font-semibold tracking-wide mb-1 font-label-lg">{snapshot?.step || 'Starting…'}</h4>
                <p className="font-label-sm text-on-surface-variant">{fileName(snapshot?.params?.source) || sourceLabel}</p>
              </div>
            </div>
          )}

          {systemState === 'LIVE' && (
            <div className="relative w-full flex flex-col justify-between overflow-hidden select-none bg-[#0a0d0d]">
              <div className="relative z-20 p-3 bg-surface-container-lowest/85 backdrop-blur border-b border-outline-variant/30 flex items-center justify-between gap-2">
                <div className="flex items-center gap-space-md min-w-0">
                  <div className="flex items-center gap-2 px-2 py-0.5 rounded-DEFAULT bg-primary/10 border border-primary/40 text-primary font-label-sm text-label-sm font-semibold">
                    <span className="w-2 h-2 rounded-full bg-primary animate-ping"></span>
                    STREAM ACTIVE
                  </div>
                  <div className="flex items-center gap-1.5 font-label-sm text-label-sm text-on-surface min-w-0">
                    <span className="text-outline">SOURCE:</span>
                    <span className="font-medium truncate">{snapshot?.source?.name}</span>
                  </div>
                  <div className="hidden sm:flex items-center gap-1.5 font-label-sm text-label-sm text-on-surface-variant">
                    <span className="text-outline">FPS:</span>
                    <span className="font-medium text-primary">{fmt(snapshot?.proc_fps, 1)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-space-md">
                  <div className="flex items-center gap-2 font-label-sm text-label-sm text-on-surface">
                    <span className="material-symbols-outlined text-[15px] text-primary">timer</span>
                    <span className="font-mono text-primary font-medium">
                      {fmtVideoTime(snapshot?.frame?.t)}
                      {snapshot?.frame?.wallclock ? ` · ${fmtClock(snapshot.frame.wallclock)}` : ''}
                    </span>
                  </div>
                  <button
                    onClick={stopToStandby}
                    className="h-7 px-3 bg-surface-container-high border border-outline-variant text-on-surface hover:bg-error-container hover:text-error hover:border-error text-label-sm font-label-sm rounded-DEFAULT flex items-center gap-1.5 transition-colors cursor-pointer"
                    title="Stop the run"
                    type="button"
                  >
                    <span className="material-symbols-outlined text-[15px] text-error">stop</span>
                    <span>Stop</span>
                  </button>
                </div>
              </div>

              <div className="w-full max-w-[1100px] mx-auto">
                <VideoFeed snapshot={snapshot} proximityRange={proximityRange} />
              </div>

              <div className="relative z-20 px-3 py-1.5 bg-surface-container-lowest/90 backdrop-blur border-t border-outline-variant/30 flex items-center justify-between text-outline font-label-sm text-label-sm">
                <div className="flex items-center gap-3">
                  <span className="text-on-surface flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px] text-primary">visibility</span>
                    <span>{snapshot?.tracks?.length ?? 0} BIRDS TRACKED</span>
                  </span>
                  <span>•</span>
                  <span className={`font-medium ${style.text}`}>
                    RISK: {fmt(risk?.score)} ({risk?.level?.toUpperCase() || '—'})
                  </span>
                  {snapshot?.alert && (
                    <>
                      <span>•</span>
                      <span className="text-error font-medium">ALERT ACTIVE</span>
                    </>
                  )}
                </div>
                <Link to="/live" className="text-primary hover:text-primary-fixed-dim flex items-center gap-1">
                  Full live view <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                </Link>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Recent episodes */}
      <section className="flex flex-col gap-space-sm mb-space-xl">
        <div className="flex items-center justify-between mb-space-xs">
          <div className="flex items-center gap-space-sm">
            <span className="material-symbols-outlined text-outline text-[18px]">history</span>
            <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold tracking-tight">Recent Alert Episodes</h3>
            <span className="px-2 py-0.5 bg-surface-container border border-outline-variant/30 text-on-surface-variant font-label-sm text-label-sm rounded-DEFAULT">
              outputs/alerts.db
            </span>
          </div>
          <Link to="/alerts" className="font-label-sm text-label-sm text-primary hover:text-primary-fixed-dim transition-colors flex items-center gap-1">
            <span>View Full Alert History</span>
            <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
          </Link>
        </div>

        <div className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-surface-container border-b border-outline-variant/30">
                  {['Episode ID', 'Source', 'Video Time', 'Duration', 'Peak Risk Level', 'Peak Score', 'Main Factor', 'Action'].map((h) => (
                    <th
                      key={h}
                      className={`py-space-sm px-space-md font-label-sm text-label-sm text-outline uppercase tracking-wider font-semibold ${
                        h === 'Peak Score' || h === 'Action' ? 'text-right' : ''
                      }`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20 font-body-sm text-body-sm">
                {recent.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="py-6 text-center text-on-surface-variant font-label-sm text-label-sm">
                      No alert episodes logged yet.
                    </td>
                  </tr>
                ) : (
                  recent.map((a) => (
                    <tr key={a.id} className="hover:bg-surface-container/60 transition-colors">
                      <td className="py-2.5 px-space-md font-label-md text-label-md text-on-surface font-semibold">{episodeId(a.id)}</td>
                      <td className="py-2.5 px-space-md font-label-sm text-label-sm text-on-surface-variant truncate max-w-[220px]" title={a.source}>
                        {fileName(a.source)}
                      </td>
                      <td className="py-2.5 px-space-md font-label-sm text-label-sm text-on-surface-variant">
                        {fmtVideoTime(a.start_s)} – {fmtVideoTime(a.end_s)}
                      </td>
                      <td className="py-2.5 px-space-md font-label-sm text-label-sm text-on-surface-variant">{fmtDuration(a.duration_s)}</td>
                      <td className="py-2.5 px-space-md">
                        <LevelBadge level={a.peak_level}>{a.peak_level?.toUpperCase()}</LevelBadge>
                      </td>
                      <td className={`py-2.5 px-space-md font-label-md text-label-md text-right font-semibold ${levelStyle(a.peak_level).text}`}>
                        {fmt(a.peak_score)}
                      </td>
                      <td className="py-2.5 px-space-md text-on-surface">{FACTOR_LABELS[a.top_factor] || a.top_factor}</td>
                      <td className="py-2.5 px-space-md text-right">
                        <button onClick={() => inspect(a.id)} className="text-outline hover:text-on-surface transition-colors cursor-pointer" title="Inspect episode" type="button">
                          <span className="material-symbols-outlined text-[18px]">readiness_score</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="px-space-md py-2 bg-surface-container/50 border-t border-outline-variant/30 flex items-center justify-between text-outline font-label-sm text-label-sm">
            <span>
              Showing {recent.length} of {alerts.total} recorded episodes
            </span>
            <span>High-risk episodes: {highCount}</span>
          </div>
        </div>
      </section>

      {/* Diagnostics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-space-sm pt-space-xs border-t border-outline-variant/20">
        <div className="p-space-sm bg-surface-container-low border border-outline-variant/20 rounded-DEFAULT flex items-center justify-between gap-2">
          <span className="font-label-sm text-label-sm text-outline">VIDEO</span>
          <span className="font-label-sm text-label-sm text-primary font-medium truncate">
            {selectedVideo ? `${selectedVideo.width}×${selectedVideo.height} @ ${fmt(selectedVideo.fps, 0)} FPS` : isWebcam ? 'WEBCAM' : '—'}
          </span>
        </div>
        <div className="p-space-sm bg-surface-container-low border border-outline-variant/20 rounded-DEFAULT flex items-center justify-between gap-2">
          <span className="font-label-sm text-label-sm text-outline">ACCELERATION</span>
          <span className="font-label-sm text-label-sm text-primary font-medium truncate">{config?.system?.gpu || 'CPU ONLY'}</span>
        </div>
        <div className="p-space-sm bg-surface-container-low border border-outline-variant/20 rounded-DEFAULT flex items-center justify-between gap-2">
          <span className="font-label-sm text-label-sm text-outline">PROCESSING</span>
          <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
            {status === 'running' ? `${fmt(snapshot?.proc_fps, 1)} FPS` : 'IDLE'}
          </span>
        </div>
        <div className="p-space-sm bg-surface-container-low border border-outline-variant/20 rounded-DEFAULT flex items-center justify-between gap-2">
          <span className="font-label-sm text-label-sm text-outline">DETECTOR</span>
          <span className="font-label-sm text-label-sm text-on-surface-variant font-medium truncate" title={weightsName}>
            {weightsName || '—'}
          </span>
        </div>
      </section>
    </div>
  );
}
