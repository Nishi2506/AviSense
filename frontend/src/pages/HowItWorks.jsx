import React from 'react';
import { useApp } from '../context/AppContext';
import { fileName, fmt } from '../lib/format';
import './HowItWorks.css';

function Stage({ n, icon, title, text, input, output, last }) {
  return (
    <div className="flex flex-col justify-between p-space-md bg-surface-container rounded-DEFAULT border border-surface-bright/60 hover:border-primary/40 transition-colors">
      <div className="flex flex-col gap-space-sm">
        <div className="flex items-center justify-between">
          <span className="font-label-sm text-label-sm text-primary font-semibold px-2 py-0.5 rounded-DEFAULT bg-surface-container-low border border-primary/20">
            STAGE {n}
          </span>
          <span className="material-symbols-outlined text-primary text-[18px]">{icon}</span>
        </div>
        <div>
          <h3 className="font-headline-sm text-headline-sm text-on-surface font-medium tracking-tight">{title}</h3>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-1.5 leading-relaxed">{text}</p>
        </div>
        <div className="flex flex-col gap-1 pt-1 border-t border-surface-bright/40 font-label-sm text-label-sm">
          <div className="flex items-center justify-between gap-2 text-on-surface-variant/70">
            <span className="uppercase">Input:</span> <span className="text-on-surface font-medium truncate">{input}</span>
          </div>
          <div className="flex items-center justify-between gap-2 text-on-surface-variant/70">
            <span className="uppercase">Output:</span> <span className="text-primary font-medium truncate">{output}</span>
          </div>
        </div>
      </div>
      <div className="mt-space-md pt-space-xs border-t border-surface-bright/40 flex justify-end">
        <span className="material-symbols-outlined text-[16px] text-primary">{last ? 'done_all' : 'arrow_forward'}</span>
      </div>
    </div>
  );
}

function Factor({ n, weight, title, text, formula, note }) {
  return (
    <div className="flex flex-col justify-between p-space-md bg-surface-container rounded-DEFAULT border border-surface-bright/60">
      <div className="flex flex-col gap-space-sm">
        <div className="flex items-center justify-between">
          <span className="font-label-sm text-label-sm text-on-surface-variant font-semibold">FACTOR {n}</span>
          <span className="font-label-sm text-label-sm text-primary font-semibold">{weight}% WEIGHT</span>
        </div>
        <div className="w-full h-1.5 bg-[#242828] rounded-full overflow-hidden">
          <div className="bg-primary h-full" style={{ width: `${weight}%` }}></div>
        </div>
        <div>
          <h4 className="font-headline-sm text-headline-sm text-on-surface font-medium">{title}</h4>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-1.5 leading-relaxed">{text}</p>
        </div>
        <div className="bg-surface-container-low p-2 rounded-DEFAULT border border-surface-bright/40 flex flex-col gap-0.5 font-label-sm text-label-sm">
          <span className="text-on-surface-variant/70 uppercase">Formula</span>
          <span className="text-on-surface font-metric-display-mobile text-[12px]">{formula}</span>
        </div>
      </div>
      <div className="mt-space-md pt-space-xs border-t border-surface-bright/40">
        <span className="font-label-sm text-label-sm text-on-surface-variant/70 uppercase block">Note</span>
        <p className="font-body-sm text-body-sm text-on-surface mt-1">{note}</p>
      </div>
    </div>
  );
}

function Tier({ color, range, tag, title, text, bullets, protocol, icon }) {
  return (
    <div className="flex flex-col justify-between p-space-lg bg-surface-container rounded-DEFAULT border border-surface-bright/60 relative overflow-hidden">
      <div className={`absolute top-0 left-0 right-0 h-1 bg-${color}`}></div>
      <div className="flex flex-col gap-space-md">
        <div className="flex items-center justify-between gap-2">
          <span className={`font-label-sm text-label-sm text-${color} uppercase font-semibold tracking-wider`}>{range}</span>
          <span className={`px-2 py-0.5 text-label-sm font-label-sm rounded-DEFAULT text-${color} border border-${color}/40 uppercase font-medium`}>{tag}</span>
        </div>
        <div>
          <h4 className="font-headline-lg text-headline-lg text-on-surface font-semibold tracking-tight">{title}</h4>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-2 leading-relaxed">{text}</p>
        </div>
        <ul className="font-body-sm text-body-sm text-on-surface flex flex-col gap-1 list-none p-0 m-0 pt-space-xs border-t border-surface-bright/40">
          {bullets.map((b) => (
            <li key={b} className="flex items-start gap-2">
              <span className={`material-symbols-outlined text-${color} text-[14px] mt-0.5`}>{icon}</span> {b}
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-space-lg pt-space-sm border-t border-surface-bright/40 flex items-center justify-between gap-2">
        <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">In AviSense</span>
        <span className={`font-label-sm text-label-sm text-${color} font-medium text-right`}>{protocol}</span>
      </div>
    </div>
  );
}

export default function HowItWorks() {
  const { config, settings, medThreshold, highThreshold } = useApp();
  const r = config?.risk;
  const n = r?.normalise || {};
  const w = settings?.weights || {};
  const total = Object.values(w).reduce((a, b) => a + b, 0) || 100;
  const pct = (f) => Math.round(((w[f] || 0) / total) * 100);
  const windows = r?.time_of_day?.windows || [];
  const winText = windows.map((x) => `${String(x.start).padStart(2, '0')}–${String(x.end).padStart(2, '0')} h → ${x.value}`).join(', ');
  const alertsCfg = r?.alerts || {};
  const tracker = config?.tracker || {};

  return (
    <div className="flex flex-col w-full gap-space-xl pb-space-xl how-it-works-container">
      <section className="flex flex-col gap-space-sm">
        <span className="self-start font-label-sm text-label-sm text-primary uppercase tracking-widest px-2 py-0.5 rounded-DEFAULT bg-surface-container-low border border-primary/20">
          Methodology &amp; Architecture
        </span>
        <h2 className="font-headline-xl text-headline-xl text-on-surface tracking-tight font-semibold">How It Works</h2>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
          AviSense is a research prototype of a low-cost, camera-based alternative to avian radar: it detects birds in video, tracks
          them, and turns what they do near the runway into an explainable Low / Medium / High risk level. Values below are read from
          the running configuration.
        </p>
      </section>

      <section className="flex flex-col gap-space-md">
        <div className="flex items-center gap-space-xs border-b border-surface-bright/40 pb-space-xs">
          <span className="font-label-sm text-label-sm text-primary font-semibold">01</span>
          <span className="font-label-sm text-label-sm text-on-surface uppercase tracking-wider font-semibold">Pipeline</span>
          <span className="text-on-surface-variant/40">/</span>
          <span className="font-label-sm text-label-sm text-on-surface-variant">Frame to risk level, once per frame</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-space-sm">
          <Stage n="01" icon="videocam" title="Video Input" text="OpenCV reads a video file or a webcam frame by frame at full resolution (AirBirds: 1920×1080)." input="Video file / webcam" output="BGR frames" />
          <Stage
            n="02"
            icon="filter_center_focus"
            title="Bird Detection"
            text={`YOLO11n with an extra stride-4 (P2) head for ~6 px birds. Motion models see frames t−4, t−2 and t as three channels, so moving birds stand out from static clutter. Runs on full frames at image size ${settings?.imgsz ?? 1920}.`}
            input="Frames"
            output={`Boxes (conf ≥ ${tracker.conf ?? 0.1})`}
          />
          <Stage
            n="03"
            icon="timeline"
            title="Tracking"
            text={`ByteTrack links boxes across frames, matching on boxes enlarged to ${tracker.assoc_size ?? 60} px because birds move further than their own size per frame. A track is reported only after it has moved ${tracker.min_motion ?? 20} px, which removes most static false detections.`}
            input="Boxes"
            output="Track IDs + trails"
          />
          <Stage
            n="04"
            icon="analytics"
            title="Feature Extraction"
            text="Per frame: bird count, largest flock, fastest bird and nearest bird to a runway zone. Distances and speeds are fractions of the frame diagonal, so zones work at any resolution."
            input="Tracks + zones"
            output="Frame features"
          />
          <Stage
            n="05"
            icon="crisis_alert"
            title="Scoring & Alerts"
            text={`Weighted sum of five normalised factors, averaged over ${r?.smoothing_frames ?? 15} frames, then classified. Frames at ${alertsCfg.min_level ?? 'Medium'} or above form alert episodes, logged to SQLite.`}
            input="Frame features"
            output="Level + alert log"
            last
          />
        </div>
      </section>

      <section className="flex flex-col gap-space-md">
        <div className="flex items-center justify-between border-b border-surface-bright/40 pb-space-xs">
          <div className="flex items-center gap-space-xs">
            <span className="font-label-sm text-label-sm text-primary font-semibold">02</span>
            <span className="font-label-sm text-label-sm text-on-surface uppercase tracking-wider font-semibold">Risk Factors</span>
            <span className="text-on-surface-variant/40">/</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">each normalised to [0, 1]</span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant/60">WEIGHTED LINEAR MODEL · configs/risk.yaml</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-space-sm">
          <Factor
            n="01"
            weight={pct('proximity')}
            title="Runway Proximity"
            text="Distance from the nearest tracked bird to a runway-zone polygon drawn for this camera."
            formula={`P = clamp(1 − d / ${n.proximity_range ?? 0.3}, 0, 1)`}
            note={`1 inside a zone, falling to 0 at ${n.proximity_range ?? 0.3} of the frame diagonal away; 0 with no birds.`}
          />
          <Factor
            n="02"
            weight={pct('count')}
            title="Bird Count"
            text="Number of tracked birds in the current frame."
            formula={`C = min(n / ${n.count_cap ?? 20}, 1)`}
            note={`${n.count_cap ?? 20} or more birds count as the maximum.`}
          />
          <Factor
            n="03"
            weight={pct('flock_size')}
            title="Flock Size"
            text="Largest group of birds within 0.05 of the frame diagonal of each other."
            formula={`F = min(flock / ${n.flock_cap ?? 10}, 1)`}
            note={`A flock of ${n.flock_cap ?? 10} or more counts as the maximum.`}
          />
          <Factor
            n="04"
            weight={pct('speed')}
            title="Speed"
            text="Speed of the fastest tracked bird, from its recent track positions."
            formula={`V = min(v / ${n.speed_cap ?? 0.5} diag/s, 1)`}
            note="Measured in frame diagonals per second; no camera calibration is needed."
          />
          <Factor
            n="05"
            weight={pct('time_of_day')}
            title="Time of Day"
            text="Bird activity peaks around dawn and dusk. Needs the video's start time (read from the file name when it has a timestamp)."
            formula={`T = ${winText || 'dawn/dusk windows'}, else ${r?.time_of_day?.default ?? 0.4}`}
            note={`${r?.time_of_day?.unknown ?? 0.5} when the start time is unknown; only counts when birds are present.`}
          />
        </div>
      </section>

      <section className="flex flex-col gap-space-md">
        <div className="flex items-center justify-between border-b border-surface-bright/40 pb-space-xs">
          <div className="flex items-center gap-space-xs">
            <span className="font-label-sm text-label-sm text-primary font-semibold">03</span>
            <span className="font-label-sm text-label-sm text-on-surface uppercase tracking-wider font-semibold">Risk Levels</span>
            <span className="text-on-surface-variant/40">/</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">thresholds on the smoothed score</span>
          </div>
          <div className="flex items-center gap-space-md font-label-sm text-label-sm">
            <span className="text-on-surface-variant/80">
              MED: <span className="text-secondary font-semibold">{medThreshold.toFixed(2)}</span>
            </span>
            <span className="text-on-surface-variant/80">
              HIGH: <span className="text-error font-semibold">{highThreshold.toFixed(2)}</span>
            </span>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-space-md">
          <Tier
            color="primary"
            range={`SCORE < ${medThreshold.toFixed(2)}`}
            tag="Low"
            title="Low Risk"
            text="No birds, or birds far from the runway zone in small numbers."
            bullets={['Shown on the timeline', 'No alert is raised']}
            protocol="Logged per frame only"
            icon="check_circle"
          />
          <Tier
            color="secondary"
            range={`SCORE ${medThreshold.toFixed(2)} – ${highThreshold.toFixed(2)}`}
            tag="Medium"
            title="Medium Risk"
            text="Typically a bird inside or close to the runway zone, or a larger group elsewhere in view."
            bullets={[
              `Opens an alert episode after ${alertsCfg.min_duration_s ?? 1} s`,
              `Episodes less than ${alertsCfg.merge_gap_s ?? 2} s apart are merged`
            ]}
            protocol="Alert episode + optional sound"
            icon="warning"
          />
          <Tier
            color="error"
            range={`SCORE ≥ ${highThreshold.toFixed(2)}`}
            tag="High"
            title="High Risk"
            text="Several factors high at once, e.g. a flock over the runway zone at dawn or dusk. A single bird alone cannot reach this level with the default weights."
            bullets={['Same alert episode, marked High', 'Peak factors stored for review']}
            protocol="Alert episode + optional sound"
            icon="emergency"
          />
        </div>
      </section>

      <section className="p-space-lg bg-surface-container-low rounded-DEFAULT border border-surface-bright/40 flex flex-col gap-space-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-space-md border-b border-surface-bright/40 pb-space-sm">
          <div className="flex items-center gap-space-md">
            <span className="material-symbols-outlined text-primary text-[24px]">functions</span>
            <div className="flex flex-col">
              <span className="font-label-md text-label-md text-on-surface font-semibold uppercase tracking-wider">Composite Risk Formula</span>
              <span className="font-metric-display-mobile text-body-md text-primary font-semibold mt-1 tracking-tight">
                R = {fmt(pct('proximity') / 100)}·P + {fmt(pct('count') / 100)}·C + {fmt(pct('flock_size') / 100)}·F + {fmt(pct('speed') / 100)}·V +{' '}
                {fmt(pct('time_of_day') / 100)}·T
              </span>
            </div>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Weights from Settings, normalised to sum to 1 · detector: {fileName(settings?.detectorWeights) || '—'}
          </span>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          The weights and thresholds are set by hand and have not yet been validated against human risk labels; the risk-labelling study
          and the optional ML classifier (notebooks/risk_classifier_colab.ipynb) are the planned check.
        </p>
      </section>
    </div>
  );
}
