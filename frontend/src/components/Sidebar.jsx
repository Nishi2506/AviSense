import React, { useRef, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useApp } from '../context/AppContext';

const selectClass =
  'w-full h-9 px-space-sm bg-surface-container border border-outline-variant/40 rounded-DEFAULT appearance-none text-body-sm text-on-surface font-body-sm focus:outline-none focus:border-primary pr-8 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed';

export default function Sidebar() {
  const {
    config,
    videoPath,
    selectVideo,
    WEBCAM,
    zonesFile,
    setZonesFile,
    uploadVideo,
    systemState,
    canRun,
    startRun,
    stopToStandby,
    runError,
    medThreshold,
    highThreshold
  } = useApp();
  const fileInput = useRef(null);
  const [uploading, setUploading] = useState('');

  const navItems = [
    { path: '/', label: 'Start Page', num: '01' },
    { path: '/live', label: 'Live Monitoring', num: '02' },
    { path: '/alerts', label: 'Alert History', num: '03' },
    { path: '/how-it-works', label: 'How It Works', num: '04' },
    { path: '/results', label: 'Results', num: '05' },
    { path: '/settings', label: 'Settings', num: '06' }
  ];

  const isRunning = systemState === 'LIVE' || systemState === 'CALIBRATING';

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(`Uploading ${file.name}…`);
    try {
      await uploadVideo(file);
      setUploading('');
    } catch (err) {
      setUploading(`Upload failed: ${err.message}`);
    }
  };

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-80 bg-surface-container-low border-r border-outline-variant/30 z-50 flex flex-col justify-between overflow-y-auto">
      <div className="p-space-lg flex flex-col gap-space-lg">
        <div>
          <div className="flex items-center gap-space-sm mb-1">
            <span className="material-symbols-outlined text-primary text-[20px]">radar</span>
            <h1 className="font-headline-sm text-headline-sm text-on-surface tracking-tight font-semibold">AviSense</h1>
          </div>
          <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider pl-7">
            Bird-Strike Risk Monitoring
          </p>
        </div>

        <div className="flex flex-col gap-space-xs">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase px-space-xs tracking-wider">
            Navigation
          </span>
          <nav className="flex flex-col gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `px-space-md py-space-sm rounded-DEFAULT transition-colors font-body-md text-body-md flex items-center justify-between ${
                    isActive
                      ? 'bg-surface-container-high text-on-surface border-l-2 border-primary font-medium'
                      : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span>{item.label}</span>
                    <span className={`font-label-sm text-label-sm ${isActive ? 'text-primary font-semibold' : 'text-on-surface-variant/60'}`}>
                      {item.num}
                    </span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="border-t border-outline-variant/30 pt-space-md flex flex-col gap-space-md">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase px-space-xs tracking-wider">
            Controls
          </span>

          <div className="flex flex-col gap-space-xs">
            <label className="font-label-sm text-label-sm text-on-surface-variant" htmlFor="video-source-select">
              Video Source
            </label>
            <div className="relative">
              <select
                id="video-source-select"
                value={videoPath || ''}
                onChange={(e) => selectVideo(e.target.value)}
                disabled={isRunning || !config}
                className={selectClass}
              >
                {!config?.videos.length && <option value="">Put videos in data/videos/</option>}
                {config?.videos.map((v) => (
                  <option key={v.path} value={v.path}>
                    {v.name}
                  </option>
                ))}
                <option value={WEBCAM}>Webcam (device 0)</option>
              </select>
              <span className="material-symbols-outlined text-[16px] text-on-surface-variant absolute right-2.5 top-2.5 pointer-events-none">
                expand_more
              </span>
            </div>
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={isRunning}
              className="self-start font-label-sm text-label-sm text-primary hover:text-primary-fixed-dim flex items-center gap-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[14px]">upload</span>
              Upload a video
            </button>
            <input ref={fileInput} type="file" accept=".mp4,.avi,.mov,.mkv" className="hidden" onChange={onUpload} />
            {uploading && <span className="font-label-sm text-label-sm text-on-surface-variant">{uploading}</span>}
          </div>

          <div className="flex flex-col gap-space-xs">
            <label className="font-label-sm text-label-sm text-on-surface-variant" htmlFor="zones-select">
              Runway Zones
            </label>
            <div className="relative">
              <select
                id="zones-select"
                value={zonesFile || ''}
                onChange={(e) => setZonesFile(e.target.value || null)}
                disabled={isRunning || !config}
                className={selectClass}
              >
                <option value="">Choose zones…</option>
                {config?.zones.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </select>
              <span className="material-symbols-outlined text-[16px] text-on-surface-variant absolute right-2.5 top-2.5 pointer-events-none">
                expand_more
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-space-sm pt-space-xs">
            <button
              id="sidebar-run-btn"
              type="button"
              onClick={startRun}
              disabled={isRunning || !canRun}
              className={`h-9 bg-primary text-on-primary font-label-md text-label-md font-medium rounded-DEFAULT hover:bg-primary-fixed-dim active:scale-[0.98] transition-all flex items-center justify-center gap-1 shadow-sm ${
                isRunning || !canRun ? 'opacity-50 pointer-events-none' : 'cursor-pointer'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">play_arrow</span>
              Run
            </button>
            <button
              id="sidebar-stop-btn"
              type="button"
              onClick={stopToStandby}
              disabled={!isRunning}
              className={`h-9 bg-surface-container border border-outline-variant/40 text-on-surface font-label-md text-label-md font-medium rounded-DEFAULT hover:bg-surface-container-high active:scale-[0.98] transition-all flex items-center justify-center gap-1 ${
                !isRunning ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">stop</span>
              Stop
            </button>
          </div>
          {runError && (
            <p className="font-label-sm text-label-sm text-error leading-snug" role="alert">
              {runError}
            </p>
          )}

          <div className="flex flex-col gap-space-sm pt-space-xs">
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center text-label-sm font-label-sm">
                <span className="text-on-surface-variant">Medium Threshold</span>
                <span className="text-secondary font-medium">{medThreshold.toFixed(2)}</span>
              </div>
              <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden">
                <div className="bg-secondary h-full transition-all duration-200" style={{ width: `${Math.round(medThreshold * 100)}%` }}></div>
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center text-label-sm font-label-sm">
                <span className="text-on-surface-variant">High Threshold</span>
                <span className="text-error font-medium">{highThreshold.toFixed(2)}</span>
              </div>
              <div className="w-full h-1 bg-surface-container-highest rounded-full overflow-hidden">
                <div className="bg-error h-full transition-all duration-200" style={{ width: `${Math.round(highThreshold * 100)}%` }}></div>
              </div>
            </div>
            <NavLink to="/settings" className="font-label-sm text-label-sm text-on-surface-variant hover:text-on-surface flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px]">tune</span>
              Adjust in Settings
            </NavLink>
          </div>
        </div>
      </div>
    </aside>
  );
}
