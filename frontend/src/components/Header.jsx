import React from 'react';
import { useApp } from '../context/AppContext';
import { fileName, fmtClock } from '../lib/format';

export default function Header() {
  const { selectedVideo, isWebcam, snapshot, status, utcClock, configError } = useApp();

  const active = status === 'running' || status === 'loading';
  const sourceName = active ? snapshot?.source?.name || fileName(snapshot?.params?.source) : isWebcam ? 'Webcam (device 0)' : selectedVideo?.name || 'No video selected';
  const camera = active ? snapshot?.source?.camera : null;
  const videoClock = active ? fmtClock(snapshot?.frame?.wallclock) : null;

  let pillDotClass = 'inline-block w-1.5 h-1.5 rounded-full bg-outline';
  let pillText = 'STANDBY IDLE';
  let pillBorderClass = 'border-outline-variant/30';
  if (configError) {
    pillDotClass = 'inline-block w-1.5 h-1.5 rounded-full bg-error';
    pillText = 'SERVER OFFLINE';
    pillBorderClass = 'border-error/40';
  } else if (status === 'loading') {
    pillDotClass = 'inline-block w-1.5 h-1.5 rounded-full bg-secondary animate-ping';
    pillText = 'STARTING…';
    pillBorderClass = 'border-secondary/40';
  } else if (status === 'running') {
    pillDotClass = 'inline-block w-1.5 h-1.5 rounded-full bg-primary animate-ping';
    pillText = 'MONITORING ACTIVE';
    pillBorderClass = 'border-primary/40';
  } else if (status === 'error') {
    pillDotClass = 'inline-block w-1.5 h-1.5 rounded-full bg-error';
    pillText = 'RUN FAILED';
    pillBorderClass = 'border-error/40';
  } else if (status === 'finished' || status === 'stopped') {
    pillText = status === 'finished' ? 'RUN FINISHED' : 'RUN STOPPED';
  }

  return (
    <header className="fixed top-0 left-80 right-0 h-14 bg-surface-container-lowest/90 backdrop-blur-md border-b border-outline-variant/30 z-40 flex items-center justify-between px-gutter-desktop">
      <div className="flex items-center gap-space-md min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="material-symbols-outlined text-[18px] text-primary">videocam</span>
          <span className="font-label-md text-label-md text-on-surface tracking-wide font-semibold truncate" title={sourceName}>
            {sourceName}
          </span>
          {camera && <span className="font-label-sm text-label-sm text-on-surface-variant">· {camera}</span>}
        </div>
        <span className="text-outline-variant">|</span>
        <div className="flex items-center gap-2 font-label-md text-label-md text-on-surface-variant whitespace-nowrap">
          <span className="material-symbols-outlined text-[16px]">schedule</span>
          <span title={videoClock ? 'Wall-clock time in the video' : 'Current time'}>{videoClock ? `${videoClock} video time` : utcClock}</span>
        </div>
      </div>
      <div
        className={`flex items-center gap-2 px-2.5 py-1 rounded-DEFAULT bg-surface-container border font-label-sm text-label-sm text-on-surface-variant ${pillBorderClass}`}
      >
        <span className={pillDotClass}></span>
        <span className="font-semibold text-on-surface tracking-wider">{pillText}</span>
      </div>
    </header>
  );
}
