import React, { useEffect, useRef, useState } from 'react';
import { frameUrl } from '../api';
import { fmt, zoneDistance } from '../lib/format';

/**
 * Latest processed frame with zone polygons, tracked-bird boxes and trails drawn on top.
 * The image for a state is preloaded before it is shown, so boxes always match the picture.
 */
export default function VideoFeed({ snapshot, proximityRange = 0.3, className = '', showLabels = true }) {
  const [shown, setShown] = useState(null);
  const pending = useRef(null);

  const seq = snapshot?.frame?.seq;
  const runId = snapshot?.run_id;

  useEffect(() => {
    if (seq === undefined || seq === null) return;
    const key = `${runId}:${seq}`;
    if (pending.current === key || shown?.key === key) return;
    pending.current = key;
    const img = new Image();
    const snap = snapshot;
    img.onload = () => {
      if (pending.current === key) {
        setShown({ key, src: img.src, tracks: snap.tracks, zones: snap.zones, source: snap.source });
        pending.current = null;
      }
    };
    img.onerror = () => {
      if (pending.current === key) pending.current = null;
    };
    img.src = frameUrl(seq, runId);
  }, [seq, runId]); // eslint-disable-line react-hooks/exhaustive-deps

  // a new run starts with an empty view
  useEffect(() => {
    setShown(null);
  }, [runId]);

  const w = shown?.source?.width || snapshot?.source?.width || 16;
  const h = shown?.source?.height || snapshot?.source?.height || 9;
  const vbW = 1000;
  const vbH = (1000 * h) / w;
  const minHalf = 9; // viewBox units: boxes stay visible around ~6 px birds

  return (
    <div className={`relative w-full overflow-hidden bg-surface-container-lowest ${className}`} style={{ aspectRatio: `${w} / ${h}` }}>
      {shown ? (
        <>
          <img className="absolute inset-0 w-full h-full object-fill" src={shown.src} alt="Latest processed video frame" />
          <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox={`0 0 ${vbW} ${vbH}`} preserveAspectRatio="none">
            {shown.zones?.map((z) => {
              const pts = z.polygon.map(([x, y]) => `${x * vbW},${y * vbH}`).join(' ');
              const [lx, ly] = z.polygon.reduce(([ax, ay], [x, y]) => [Math.min(ax, x), Math.min(ay, y)], [1, 1]);
              return (
                <g key={z.name}>
                  <polygon points={pts} fill="rgba(255, 122, 115, 0.10)" stroke="#ff7a73" strokeDasharray="6,4" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
                  <text x={lx * vbW + 6} y={ly * vbH - 6} fill="#ff7a73" fontFamily="JetBrains Mono" fontSize="11" fontWeight="600" letterSpacing="0.06em">
                    {z.name.toUpperCase()} ZONE
                  </text>
                </g>
              );
            })}
            {shown.tracks?.map((t) => {
              const [x1, y1, x2, y2] = t.box;
              const cx = ((x1 + x2) / 2) * vbW;
              const cy = ((y1 + y2) / 2) * vbH;
              const half = Math.max(minHalf, (Math.max(x2 - x1, (y2 - y1) * (vbH / vbW)) * vbW) / 2 + 4);
              const d = zoneDistance((x1 + x2) / 2, (y1 + y2) / 2, shown.zones, w, h);
              const color = d === 0 ? '#ef4444' : d !== null && d < proximityRange / 2 ? '#f59e0b' : '#10b981';
              const trail = t.trail?.map(([x, y]) => `${x * vbW},${y * vbH}`).join(' ');
              return (
                <g key={t.id}>
                  {trail && <polyline points={trail} fill="none" stroke={color} strokeOpacity="0.7" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />}
                  <rect x={cx - half} y={cy - half} width={half * 2} height={half * 2} fill={color} fillOpacity="0.08" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                  {showLabels && (
                    <text x={cx - half} y={cy - half - 4} fill={color} fontFamily="JetBrains Mono" fontSize="10" fontWeight="600">
                      #{t.id} · {fmt(t.conf)}
                      {d === 0 ? ' · IN ZONE' : d !== null ? ` · d ${fmt(d)}` : ''}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center font-label-sm text-label-sm text-on-surface-variant">
          Waiting for the first processed frame…
        </div>
      )}
    </div>
  );
}
