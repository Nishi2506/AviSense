import React, { useEffect, useState } from 'react';
import { useApp, beep } from '../context/AppContext';
import { api, videoFrameUrl } from '../api';
import { FACTORS, FACTOR_LABELS, fileName, fmt } from '../lib/format';
import './Settings.css';

const IMAGE_SIZES = [640, 960, 1280, 1600, 1920];
const PRESETS = {
  conservative: { medThreshold: 0.2, highThreshold: 0.5, label: 'Conservative' },
  standard: { medThreshold: 0.3, highThreshold: 0.6, label: 'Standard' },
  reduced: { medThreshold: 0.4, highThreshold: 0.7, label: 'Fewer Alerts' }
};

function Panel({ icon, title, right, children }) {
  return (
    <div className="bg-surface rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md border border-outline-variant/30">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-space-sm">
          <span className="material-symbols-outlined text-outline">{icon}</span>
          <h2 className="font-headline-sm text-headline-sm text-on-surface font-semibold">{title}</h2>
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Stepper({ value, onChange, step, min, max, unit }) {
  return (
    <div className="flex items-center gap-space-xs bg-surface-container rounded px-space-sm py-1 border border-outline-variant/30">
      <button onClick={() => onChange(Math.max(min, +(value - step).toFixed(2)))} className="text-outline hover:text-on-surface cursor-pointer" type="button">
        <span className="material-symbols-outlined text-sm">remove</span>
      </button>
      <span className="font-label-md text-label-md text-on-surface font-mono font-medium px-space-xs min-w-[3.5rem] text-center">
        {value}
        {unit}
      </span>
      <button onClick={() => onChange(Math.min(max, +(value + step).toFixed(2)))} className="text-outline hover:text-on-surface cursor-pointer" type="button">
        <span className="material-symbols-outlined text-sm">add</span>
      </button>
    </div>
  );
}

export default function Settings() {
  const { config, settings, updateSettings, resetRiskDefaults, selectedVideo, isWebcam, zonesFile, status } = useApp();
  const [zone, setZone] = useState(null);
  const [zoneError, setZoneError] = useState('');

  useEffect(() => {
    setZone(null);
    setZoneError('');
    if (zonesFile) api.zones(zonesFile).then(setZone).catch((e) => setZoneError(e.message));
  }, [zonesFile]);

  if (!settings || !config) return <p className="font-body-md text-body-md text-on-surface-variant">Loading settings…</p>;

  const { medThreshold, highThreshold, weights } = settings;
  const running = status === 'running' || status === 'loading';

  const setMed = (v) => updateSettings({ medThreshold: v, highThreshold: v >= highThreshold ? +(v + 0.05).toFixed(2) : highThreshold, selectedPreset: null });
  const setHigh = (v) => updateSettings({ highThreshold: v, medThreshold: v <= medThreshold ? +(v - 0.05).toFixed(2) : medThreshold, selectedPreset: null });
  const preset = (key) => updateSettings({ medThreshold: PRESETS[key].medThreshold, highThreshold: PRESETS[key].highThreshold, selectedPreset: key });

  const totalWeights = FACTORS.reduce((s, f) => s + (weights[f] || 0), 0);
  const isNormalized = totalWeights === 100;
  const lowWidth = medThreshold * 100;
  const medWidth = Math.max(0, (highThreshold - medThreshold) * 100);
  const highWidth = Math.max(0, (1 - highThreshold) * 100);
  const aspect = selectedVideo ? `${selectedVideo.width} / ${selectedVideo.height}` : '16 / 9';

  return (
    <div className="flex flex-col w-full pb-space-xl settings-container">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md border-b border-[#242828] pb-space-md mb-space-md">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight font-semibold">Runway Zone Viewer &amp; Settings</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
            Detection, risk thresholds, factor weights and alert rules. Settings are saved in this browser and apply when you press Run.
          </p>
        </div>
        <div className={`px-space-md py-space-xs rounded bg-surface-container-high flex items-center gap-space-xs border border-outline-variant/30 ${running ? 'text-secondary' : 'text-primary'}`}>
          <span className="material-symbols-outlined text-sm">{running ? 'pending' : 'tune'}</span>
          <span className="font-label-sm text-label-sm tracking-wider uppercase">{running ? 'Run in progress: changes apply to the next run' : 'Applied at next run'}</span>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-gutter-desktop mt-space-md">
        {/* LEFT */}
        <div className="col-span-12 xl:col-span-7 flex flex-col gap-gutter-desktop">
          <div className="bg-surface rounded-xl overflow-hidden shadow-sm flex flex-col border border-outline-variant/30">
            <div className="px-space-md py-space-sm bg-surface-container-low flex items-center justify-between border-b border-outline-variant/30 gap-2">
              <div className="flex items-center gap-space-sm min-w-0">
                <span className="w-2 h-2 rounded-full bg-primary-container"></span>
                <span className="font-label-md text-label-md text-on-surface uppercase font-medium truncate">
                  {zonesFile || 'No zones file'} on {isWebcam ? 'webcam' : selectedVideo?.name || 'no video'}
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-outline font-mono whitespace-nowrap">{zone?.camera ? `CAMERA ${zone.camera}` : ''}</span>
            </div>

            <div className="relative w-full bg-surface-container-lowest overflow-hidden select-none" style={{ aspectRatio: aspect }}>
              {selectedVideo ? (
                <img alt={`First frame of ${selectedVideo.name}`} className="absolute inset-0 w-full h-full object-fill" src={videoFrameUrl(selectedVideo.path)} />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center font-label-sm text-label-sm text-on-surface-variant">
                  {isWebcam ? 'No preview for the webcam; zones are drawn on the live feed during a run.' : 'Choose a video in the sidebar.'}
                </div>
              )}
              {zone && (
                <svg className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none" viewBox="0 0 1000 1000">
                  {zone.zones.map((z) => (
                    <g key={z.name}>
                      <polygon
                        fill="#ef4444"
                        fillOpacity="0.18"
                        points={z.polygon.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}
                        stroke="#ef4444"
                        strokeWidth="2"
                        vectorEffect="non-scaling-stroke"
                      />
                      {z.polygon.map(([x, y], i) => (
                        <circle key={i} cx={x * 1000} cy={y * 1000} r="5" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                      ))}
                    </g>
                  ))}
                </svg>
              )}
              <div className="absolute top-space-sm left-space-sm flex flex-col gap-1 pointer-events-none">
                {zone?.zones.map((z) => (
                  <span key={z.name} className="font-label-sm text-label-sm px-space-xs py-0.5 rounded bg-surface-container-lowest/90 text-error uppercase backdrop-blur-md border border-outline-variant/30">
                    {z.name} zone · {z.polygon.length} points
                  </span>
                ))}
              </div>
            </div>

            <div className="px-space-md py-space-sm bg-surface-container flex flex-col gap-1 border-t border-outline-variant/30 font-label-sm text-label-sm">
              {zoneError && <span className="text-error">{zoneError}</span>}
              {zone?.zones.map((z) => (
                <div key={z.name} className="flex flex-wrap items-center gap-x-space-sm gap-y-1 text-on-surface-variant">
                  <span className="material-symbols-outlined text-outline text-base">square_foot</span>
                  <span className="text-on-surface">{z.name}:</span>
                  {z.polygon.map(([x, y], i) => (
                    <span key={i} className="font-mono">
                      P{i + 1} ({fmt(x, 3)}, {fmt(y, 3)})
                    </span>
                  ))}
                </div>
              ))}
              <span className="text-outline">
                Vertices are fractions of the frame width/height. Edit with:{' '}
                <code className="font-mono text-on-surface">
                  python -m src.risk_scoring.zone_editor --source {selectedVideo?.path || '<video>'} --out configs/zones/{zonesFile || '<cam>.json'}
                </code>
              </span>
            </div>
          </div>

          <Panel icon="filter_center_focus" title="Detection & Tracking">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-space-md">
              <div className="md:col-span-12 flex flex-col gap-space-xs">
                <label className="font-label-sm text-label-sm text-on-surface-variant uppercase" htmlFor="weights-select">
                  Detector Weights
                </label>
                <select
                  id="weights-select"
                  value={settings.detectorWeights || ''}
                  onChange={(e) => updateSettings({ detectorWeights: e.target.value })}
                  className="h-9 px-space-sm bg-surface-container border border-outline-variant/30 rounded text-on-surface font-label-md text-label-md focus:outline-none focus:border-primary"
                >
                  {config.weights.map((w) => (
                    <option key={w} value={w}>
                      {fileName(w)}
                      {w === config.defaults.weights ? ' (best on test split)' : w === 'yolo11n.pt' ? ' (COCO, untrained for AirBirds)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-12 flex flex-col gap-space-xs">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Inference Image Size</span>
                <div className="grid grid-cols-5 gap-space-xs">
                  {IMAGE_SIZES.map((s) => (
                    <button
                      key={s}
                      onClick={() => updateSettings({ imgsz: s })}
                      className={`h-9 rounded font-label-md text-label-md transition-colors cursor-pointer border border-outline-variant/30 ${
                        settings.imgsz === s ? 'bg-surface-container-high text-primary font-medium' : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                      }`}
                      type="button"
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <span className="font-label-sm text-label-sm text-outline">Tile-trained weights expect 1920 on 1920×1080 video; smaller is faster but misses small birds.</span>
              </div>

              <div className="md:col-span-6 flex flex-col gap-1.5">
                <div className="flex justify-between items-center font-label-sm text-label-sm">
                  <span className="text-on-surface uppercase">Detection Confidence</span>
                  <span className="text-primary font-mono">{fmt(settings.conf)}</span>
                </div>
                <input className="w-full accent-primary h-1.5 cursor-pointer" type="range" min="0.05" max="0.9" step="0.05" value={settings.conf} onChange={(e) => updateSettings({ conf: +e.target.value })} />
                <span className="font-label-sm text-label-sm text-outline">Low values help ByteTrack keep tracks alive (default {config.defaults.conf}).</span>
              </div>

              <div className="md:col-span-6 flex flex-col gap-space-sm">
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm text-on-surface uppercase">Motion Filter</span>
                  <Stepper value={settings.minMotion} onChange={(v) => updateSettings({ minMotion: v })} step={5} min={0} max={100} unit=" px" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm text-on-surface uppercase">Min Track Age</span>
                  <Stepper value={settings.minTrackAge} onChange={(v) => updateSettings({ minTrackAge: v })} step={1} min={0} max={30} unit=" fr" />
                </div>
                <span className="font-label-sm text-label-sm text-outline">A bird is reported once it has moved this far; 0 also keeps birds that never move.</span>
              </div>

              <div className="md:col-span-12 flex flex-col gap-space-xs border-t border-outline-variant/30 pt-space-sm">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Video Start Time (for the time-of-day factor)</span>
                <div className="flex flex-wrap items-center gap-space-sm">
                  {[
                    ['auto', `From file name${selectedVideo?.start_time ? ` (${selectedVideo.start_time.replace('T', ' ')})` : ' (none found)'}`],
                    ['manual', 'Set manually'],
                    ['none', 'Unknown']
                  ].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-1.5 font-label-sm text-label-sm text-on-surface cursor-pointer">
                      <input type="radio" name="start-mode" className="accent-primary" checked={settings.startTimeMode === key} onChange={() => updateSettings({ startTimeMode: key })} />
                      {label}
                    </label>
                  ))}
                  {settings.startTimeMode === 'manual' && (
                    <input
                      type="datetime-local"
                      step="1"
                      value={settings.manualStartTime}
                      onChange={(e) => updateSettings({ manualStartTime: e.target.value })}
                      className="h-8 px-2 bg-surface-container border border-outline-variant/30 rounded text-on-surface font-label-md text-label-md [color-scheme:dark]"
                    />
                  )}
                </div>
              </div>
            </div>
          </Panel>
        </div>

        {/* RIGHT */}
        <div className="col-span-12 xl:col-span-5 flex flex-col gap-gutter-desktop">
          <Panel icon="tune" title="Risk Threshold Calibration" right={<span className="font-label-sm text-label-sm text-outline font-mono">configs/risk.yaml</span>}>
            <div className="flex flex-col gap-space-xs">
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Sensitivity Presets</span>
              <div className="grid grid-cols-3 gap-space-xs p-1 bg-surface-container-lowest rounded-lg border border-outline-variant/30">
                {Object.entries(PRESETS).map(([key, p]) => (
                  <button
                    key={key}
                    onClick={() => preset(key)}
                    className={`py-1.5 px-space-xs text-center rounded font-label-sm text-label-sm transition-colors cursor-pointer ${
                      settings.selectedPreset === key ? 'bg-surface-container-high text-primary font-medium' : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                    type="button"
                  >
                    {p.label} ({fmt(p.medThreshold)}/{fmt(p.highThreshold)})
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-space-xs pt-space-xs">
              <div className="flex justify-between items-center font-label-sm text-label-sm">
                <span className="text-on-surface-variant uppercase">Risk Bands</span>
                <span className="font-mono text-outline">0.00 — 1.00 SCORE</span>
              </div>
              <div className="h-3 w-full rounded overflow-hidden flex bg-surface-container-lowest border border-outline-variant/30">
                <div className="h-full bg-primary-container transition-all duration-150" style={{ width: `${lowWidth}%` }} title={`Low: 0.00 to ${fmt(medThreshold)}`}></div>
                <div className="h-full bg-secondary-container transition-all duration-150" style={{ width: `${medWidth}%` }} title={`Medium: ${fmt(medThreshold)} to ${fmt(highThreshold)}`}></div>
                <div className="h-full bg-tertiary-container transition-all duration-150" style={{ width: `${highWidth}%` }} title={`High: ${fmt(highThreshold)} to 1.00`}></div>
              </div>
              <div className="flex justify-between text-xs font-label-sm text-label-sm pt-1">
                <span className="text-primary">LOW (&lt; {fmt(medThreshold)})</span>
                <span className="text-secondary">
                  MED ({fmt(medThreshold)} - {fmt(highThreshold)})
                </span>
                <span className="text-tertiary">HIGH (≥ {fmt(highThreshold)})</span>
              </div>
            </div>

            <div className="flex flex-col gap-space-md pt-space-xs">
              {[
                ['Medium Risk Threshold', medThreshold, setMed, 0.1, 0.5, 'secondary'],
                ['High Risk Threshold', highThreshold, setHigh, 0.4, 0.9, 'tertiary']
              ].map(([label, value, onChange, min, max, color]) => (
                <div key={label} className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center">
                    <span className="font-label-sm text-label-sm text-on-surface uppercase">{label}</span>
                    <span className={`font-label-md text-label-md text-${color} font-mono bg-surface-container px-space-xs py-0.5 rounded border border-outline-variant/30`}>{fmt(value)}</span>
                  </div>
                  <input className={`w-full accent-${color} h-1.5 cursor-pointer`} type="range" min={min} max={max} step="0.05" value={value} onChange={(e) => onChange(+e.target.value)} />
                  <div className="flex justify-between font-label-sm text-label-sm text-outline">
                    <span>{fmt(min)}</span>
                    <span>{fmt(max)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel
            icon="balance"
            title="Factor Weight Calibration"
            right={
              <div className="flex items-center gap-space-xs px-space-sm py-0.5 rounded bg-surface-container-high border border-outline-variant/30">
                <span className={`w-2 h-2 rounded-full ${isNormalized ? 'bg-primary-container' : 'bg-secondary'}`}></span>
                <span className={`font-label-sm text-label-sm font-mono font-medium ${isNormalized ? 'text-primary' : 'text-secondary'}`}>
                  {totalWeights}% {isNormalized ? '' : '(rescaled to 100%)'}
                </span>
              </div>
            }
          >
            <p className="font-body-sm text-body-sm text-on-surface-variant">Relative importance of each factor in the risk score. Weights are rescaled to sum to 1 when a run starts.</p>
            <div className="flex flex-col gap-space-sm">
              {FACTORS.map((f) => (
                <div key={f} className="flex flex-col gap-1">
                  <div className="flex justify-between items-center font-label-sm text-label-sm">
                    <span className="text-on-surface">{FACTOR_LABELS[f]}</span>
                    <span className="text-primary font-mono">
                      {weights[f]}%{!isNormalized && totalWeights > 0 ? ` → ${Math.round((weights[f] / totalWeights) * 100)}%` : ''}
                    </span>
                  </div>
                  <input
                    className="w-full accent-primary h-1.5 cursor-pointer"
                    type="range"
                    min="0"
                    max="60"
                    value={weights[f]}
                    onChange={(e) => updateSettings({ weights: { ...weights, [f]: parseInt(e.target.value, 10) } })}
                  />
                </div>
              ))}
            </div>
          </Panel>

          <Panel icon="notifications_active" title="Alerts">
            <div className="flex items-center justify-between py-space-xs gap-space-md">
              <div className="flex flex-col">
                <span className="font-body-md text-body-md text-on-surface font-medium">Sound on New Alert</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">Two short beeps in this browser when an alert episode starts</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input checked={settings.audioAlertEnabled} onChange={(e) => updateSettings({ audioAlertEnabled: e.target.checked })} className="sr-only peer" type="checkbox" />
                <div className="w-11 h-6 bg-surface-container-high rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-container"></div>
              </label>
            </div>
            <div className="flex items-center justify-between py-space-xs gap-space-md">
              <div className="flex flex-col">
                <span className="font-body-md text-body-md text-on-surface font-medium">Minimum Alert Duration</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">Shorter Medium/High stretches are ignored</span>
              </div>
              <Stepper value={settings.minDuration} onChange={(v) => updateSettings({ minDuration: v })} step={0.5} min={0} max={10} unit=" s" />
            </div>
            <div className="flex items-center justify-between py-space-xs gap-space-md">
              <div className="flex flex-col">
                <span className="font-body-md text-body-md text-on-surface font-medium">Merge Gap</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">Episodes closer than this become one alert</span>
              </div>
              <Stepper value={settings.mergeGap} onChange={(v) => updateSettings({ mergeGap: v })} step={0.5} min={0} max={30} unit=" s" />
            </div>
            <div className="grid grid-cols-2 gap-space-sm pt-space-xs">
              <button
                onClick={beep}
                className="h-9 bg-surface-container-high hover:bg-surface-variant text-on-surface rounded font-label-md text-label-md font-medium transition-colors flex items-center justify-center gap-space-xs cursor-pointer border border-outline-variant/30"
                type="button"
              >
                <span className="material-symbols-outlined text-sm">volume_up</span>
                <span>Test Sound</span>
              </button>
              <button
                onClick={resetRiskDefaults}
                className="h-9 bg-surface-container-high hover:bg-surface-variant text-on-surface rounded font-label-md text-label-md font-medium transition-colors flex items-center justify-center gap-space-xs cursor-pointer border border-outline-variant/30"
                type="button"
              >
                <span className="material-symbols-outlined text-sm">history</span>
                <span>Reset to risk.yaml</span>
              </button>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
