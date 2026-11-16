import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { fmt } from '../lib/format';
import './Results.css';

const pct = (v) => `${(v * 100).toFixed(1)}%`;

function Pod({ label, value, chip, note }) {
  return (
    <div className="flex flex-col justify-between p-space-md bg-surface-container-low rounded-lg shadow-sm border border-outline-variant/30">
      <div className="flex justify-between items-start mb-space-xs gap-2">
        <span className="font-label-md text-label-md text-on-surface-variant">{label}</span>
        {chip && <span className="font-label-sm text-label-sm px-1.5 py-0.5 rounded bg-surface-container text-primary font-medium whitespace-nowrap">{chip}</span>}
      </div>
      <span className="font-metric-display text-metric-display text-on-surface font-semibold">{value}</span>
      <div className="flex items-center gap-space-xs mt-space-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0"></span>
        <span className="font-label-sm text-label-sm text-on-surface-variant">{note}</span>
      </div>
    </div>
  );
}

function Figure({ tag, title, chip, caption, children }) {
  return (
    <div className="flex flex-col bg-surface-container-low p-space-md rounded-lg shadow-sm border border-outline-variant/30">
      <div className="flex justify-between items-center pb-space-sm mb-space-sm gap-2">
        <div className="flex items-center gap-space-xs">
          <span className="font-label-sm text-label-sm text-primary uppercase">{tag}</span>
          <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">{title}</span>
        </div>
        {chip && <span className="font-label-sm text-label-sm px-1.5 py-0.5 rounded bg-surface-container text-primary font-medium whitespace-nowrap">{chip}</span>}
      </div>
      <div className="w-full bg-surface-container-lowest rounded p-space-sm border border-outline-variant/20">{children}</div>
      <div className="flex items-start gap-space-xs mt-space-sm pt-space-xs">
        <span className="material-symbols-outlined text-outline text-sm mt-0.5">info</span>
        <p className="font-body-sm text-body-sm text-on-surface-variant">{caption}</p>
      </div>
    </div>
  );
}

/** Simple multi-series line chart over epochs. */
function EpochChart({ curves, series, yMax, bestEpoch }) {
  const X0 = 40, X1 = 380, Y0 = 140, Y1 = 20;
  const n = curves.length;
  const top = yMax ?? Math.max(...series.flatMap((s) => curves.map((c) => c[s.key] ?? 0))) * 1.05;
  const x = (i) => X0 + (i / Math.max(n - 1, 1)) * (X1 - X0);
  const y = (v) => Y0 - (Math.min(v, top) / top) * (Y0 - Y1); // values above the axis are drawn at the top
  return (
    <div className="relative w-full h-56">
      <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 400 180">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} stroke="#343535" strokeDasharray="3,3" strokeWidth="1" x1={X0} x2={X1} y1={y(f * top)} y2={y(f * top)} />
        ))}
        <line stroke="#3c4a42" strokeWidth="1.5" x1={X0} x2={X1} y1={Y0} y2={Y0} />
        <line stroke="#3c4a42" strokeWidth="1.5" x1={X0} x2={X0} y1={Y1} y2={Y0} />
        {[0, 0.5, 1].map((f) => (
          <text key={f} fill="#86948a" fontFamily="JetBrains Mono" fontSize="9" textAnchor="end" x="35" y={y(f * top) + 3}>
            {fmt(f * top, top < 2 ? 2 : 1)}
          </text>
        ))}
        <text fill="#86948a" fontFamily="JetBrains Mono" fontSize="9" textAnchor="middle" x={X0} y="156">
          Ep {curves[0]?.epoch}
        </text>
        <text fill="#86948a" fontFamily="JetBrains Mono" fontSize="9" textAnchor="end" x={X1} y="156">
          Epoch {curves[n - 1]?.epoch}
        </text>
        {bestEpoch && (
          <g>
            <line stroke="#4edea3" strokeDasharray="2,2" strokeOpacity="0.5" x1={x(bestEpoch - 1)} x2={x(bestEpoch - 1)} y1={Y1} y2={Y0} />
            <text fill="#4edea3" fontFamily="JetBrains Mono" fontSize="9" textAnchor="middle" x={x(bestEpoch - 1)} y="14">
              best {bestEpoch}
            </text>
          </g>
        )}
        {series.map((s) => (
          <path
            key={s.key}
            d={curves.map((c, i) => `${i ? 'L' : 'M'} ${x(i).toFixed(1)},${y(c[s.key] ?? 0).toFixed(1)}`).join(' ')}
            fill="none"
            stroke={s.color}
            strokeWidth="1.8"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className="absolute top-1 right-2 flex items-center gap-space-sm bg-surface-container-high/90 px-space-sm py-1 rounded border border-outline-variant/30">
        {series.map((s) => (
          <div key={s.key} className="flex items-center gap-1">
            <span className="w-2.5 h-0.5" style={{ background: s.color }}></span>
            <span className="font-label-sm text-label-sm text-on-surface">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Results() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.results().then(setData).catch((e) => setError(e.message));
  }, []);

  const best = useMemo(() => data?.models.find((m) => m.current), [data]);

  const exportCSV = () => {
    const headers = ['weights', 'training_data', 'training', 'test_imgsz', 'precision', 'recall', 'mAP50', 'mAP50-95'];
    const rows = data.models.map((m) => [m.weights, `"${m.data}"`, `"${m.training}"`, m.test_imgsz, m.precision, m.recall, m.map50, m.map50_95]);
    const blob = new Blob([[headers.join(','), ...rows.map((r) => r.join(','))].join('\n')], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'avisense_model_results.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  };

  if (error) return <p className="font-body-md text-body-md text-error">Could not load results: {error}</p>;
  if (!data) return <p className="font-body-md text-body-md text-on-surface-variant">Loading results…</p>;

  const d = data.detector;
  const t = data.tracking;
  const ts = data.test_set;

  return (
    <div className="flex flex-col w-full pb-space-xl results-container">
      <div className="flex flex-col gap-space-md mb-space-lg">
        <div className="flex flex-col gap-space-xs">
          <span className="font-label-sm text-label-sm text-primary uppercase">Offline evaluation</span>
          <h1 className="font-headline-xl text-headline-xl text-on-surface tracking-tight font-semibold">Model Evaluation Results</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
            Bird detection and tracking measured on the held-out test sequence ({ts.name}: {ts.frames.toLocaleString()} full frames,{' '}
            {ts.birds.toLocaleString()} labelled birds, a day not used for training).
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-space-sm p-space-sm bg-surface-container-low rounded-lg shadow-sm border border-outline-variant/30">
          {[
            ['database', 'Training data', `${d.train_tiles.toLocaleString()} TILES · 640×640`],
            ['memory', 'Deployed weights', `${data.run}.pt`],
            ['model_training', 'Training run', `${d.epochs_run} / ${d.epochs_max} EPOCHS · BEST ${d.best_epoch} · ${d.train_hours} H`],
            ['tune', 'Test image size', `${ts.imgsz} PX FULL FRAMES`]
          ].map(([icon, label, value]) => (
            <div key={label} className="flex items-center gap-space-xs px-space-sm py-1 bg-surface-container rounded min-w-0">
              <span className="material-symbols-outlined text-outline text-sm">{icon}</span>
              <div className="flex flex-col min-w-0">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">{label}</span>
                <span className="font-label-sm text-label-sm text-on-surface font-medium truncate" title={value}>
                  {value}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md mb-space-xl">
        <Pod label="Detection mAP@50" value={pct(d.map50)} chip={`mAP@50-95 ${pct(d.map50_95)}`} note="IoU ≥ 0.5 on ~6 px birds" />
        <Pod label="Detection Precision / Recall" value={`${fmt(d.precision)} / ${fmt(d.recall)}`} chip="test split" note={d.model} />
        <Pod label="Tracking Precision / Recall" value={`${fmt(t.precision)} / ${fmt(t.recall)}`} chip={`${pct(t.false_alarm_frames)} false-alarm frames`} note="Tracked boxes, conf ≥ 0.3, 20 px motion filter" />
        <Pod label="Pipeline Speed" value={<>{fmt(data.speed.pipeline_fps, 1)} <span className="font-body-sm text-body-sm text-on-surface-variant font-normal">FPS</span></>} chip={data.speed.gpu} note={`Full frames at imgsz ${data.speed.imgsz}; much slower on battery`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg mb-space-xl">
        <Figure
          tag="01 // MATRIX"
          title="Confusion Matrix (Test)"
          chip="1 class: bird"
          caption="Ultralytics confusion matrix on the test split: correctly found birds, missed birds (bird → background) and false detections (background → bird)."
        >
          {data.images.confusion_test ? <img src={data.images.confusion_test} alt="Confusion matrix on the test split" className="w-full rounded" /> : 'Figure not found'}
        </Figure>
        <Figure tag="02 // PR CURVE" title="Precision–Recall (Test)" chip={`mAP@50 = ${fmt(d.map50, 3)}`} caption="Precision against recall over all confidence thresholds, test split at image size 1920.">
          {data.images.pr_curve_test ? <img src={data.images.pr_curve_test} alt="Precision-recall curve on the test split" className="w-full rounded" /> : 'Figure not found'}
        </Figure>
        <Figure tag="03 // CONVERGENCE" title="Training Losses" chip={`${data.curves.length} EPOCHS`} caption="Training box, classification and distribution-focal losses per epoch (from the run's results.csv). Values above the axis (the first epochs) are drawn clipped at the top.">
          {data.curves.length ? (
            <EpochChart
              curves={data.curves}
              series={[
                { key: 'box_loss', label: 'Box', color: '#4edea3' },
                { key: 'cls_loss', label: 'Cls', color: '#ffb95f' },
                { key: 'dfl_loss', label: 'DFL', color: '#86948a' }
              ]}
              yMax={3}
            />
          ) : (
            'results.csv not found'
          )}
        </Figure>
        <Figure
          tag="04 // VALIDATION"
          title="Validation mAP per Epoch"
          chip={`best epoch ${d.best_epoch}`}
          caption="Validation metrics during training. The validation set is mostly other cameras, so values are lower than on the test camera; they were used only to pick the best epoch."
        >
          {data.curves.length ? (
            <EpochChart
              curves={data.curves}
              series={[
                { key: 'map50', label: 'mAP50', color: '#4edea3' },
                { key: 'map50_95', label: 'mAP50-95', color: '#ffb95f' }
              ]}
              bestEpoch={d.best_epoch}
            />
          ) : (
            'results.csv not found'
          )}
        </Figure>
      </div>

      {(data.images.test_pred || data.images.test_labels) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg mb-space-xl">
          <Figure tag="05 // PREDICTIONS" title="Test Frames: Model Output" caption="Detections on a batch of motion-stacked test frames (moving birds appear as coloured dots).">
            <img src={data.images.test_pred} alt="Model predictions on test frames" className="w-full rounded" />
          </Figure>
          <Figure tag="06 // GROUND TRUTH" title="Test Frames: Labels" caption="The dataset's ground-truth boxes for the same frames, for comparison.">
            <img src={data.images.test_labels} alt="Ground-truth labels on the same test frames" className="w-full rounded" />
          </Figure>
        </div>
      )}

      <div className="flex flex-col bg-surface-container-low p-space-md rounded-lg shadow-sm border border-outline-variant/30">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-space-xs pb-space-sm mb-space-sm">
          <div className="flex items-center gap-space-xs">
            <span className="font-label-sm text-label-sm text-primary uppercase">Model history</span>
            <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">Every Detector Trained, Same Test Split</span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">Source: README results table</span>
        </div>
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left font-body-sm text-body-sm">
            <thead className="bg-surface-container font-label-sm text-label-sm text-outline uppercase">
              <tr>
                <th className="py-2.5 px-space-md font-medium">Weights</th>
                <th className="py-2.5 px-space-md font-medium">Training data</th>
                <th className="py-2.5 px-space-md font-medium">Change</th>
                <th className="py-2.5 px-space-md text-right font-medium">Precision</th>
                <th className="py-2.5 px-space-md text-right font-medium">Recall</th>
                <th className="py-2.5 px-space-md text-right font-medium">mAP50</th>
                <th className="py-2.5 px-space-md font-medium">mAP50 bar</th>
                <th className="py-2.5 px-space-md text-right font-medium">mAP50-95</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container font-label-md text-label-md">
              {data.models.map((m) => (
                <tr key={m.weights} className={`hover:bg-surface-container/60 transition-colors ${m.current ? 'bg-primary/5' : ''}`}>
                  <td className="py-3 px-space-md font-medium text-on-surface">
                    <span className="font-mono text-[12px]">{m.weights}</span>
                    {m.current && <span className="ml-2 font-label-sm text-label-sm px-1.5 py-0.5 rounded bg-primary/15 text-primary">CURRENT</span>}
                  </td>
                  <td className="py-3 px-space-md text-on-surface-variant font-body-sm text-body-sm">{m.data}</td>
                  <td className="py-3 px-space-md text-on-surface-variant font-body-sm text-body-sm">{m.training}</td>
                  <td className="py-3 px-space-md text-right text-on-surface font-mono">{fmt(m.precision, 3)}</td>
                  <td className="py-3 px-space-md text-right text-on-surface font-mono">{fmt(m.recall, 3)}</td>
                  <td className={`py-3 px-space-md text-right font-mono font-semibold ${m.current ? 'text-primary' : 'text-on-surface'}`}>{fmt(m.map50, 3)}</td>
                  <td className="py-3 px-space-md">
                    <div className="w-28 bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                      <div className={`${m.current ? 'bg-primary' : 'bg-outline'} h-full`} style={{ width: `${m.map50 * 100}%` }}></div>
                    </div>
                  </td>
                  <td className="py-3 px-space-md text-right text-on-surface font-mono">{fmt(m.map50_95, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col sm:flex-row justify-between items-center gap-space-sm mt-space-md pt-space-sm bg-surface-container-lowest p-space-sm rounded border border-outline-variant/30">
          <div className="flex items-center gap-space-xs text-outline font-label-sm text-label-sm">
            <span className="material-symbols-outlined text-sm">info</span>
            <span>
              mAP50-95 stays low by nature here: on a 6×6 px bird a one-pixel offset already drops IoU to ~0.7.
              {best ? ` Current: ${best.weights}.` : ''}
            </span>
          </div>
          <div className="flex items-center gap-space-sm">
            <button
              onClick={exportCSV}
              className="h-8 px-space-md bg-surface-container hover:bg-surface-container-high text-on-surface rounded font-label-md text-label-md flex items-center gap-space-xs transition-colors cursor-pointer border border-outline-variant/30"
              type="button"
            >
              <span className="material-symbols-outlined text-sm">download</span>
              <span>EXPORT CSV</span>
            </button>
            <button
              onClick={() => window.print()}
              className="h-8 px-space-md bg-primary hover:bg-primary-fixed-dim text-on-primary rounded font-label-md text-label-md font-medium flex items-center gap-space-xs transition-colors cursor-pointer"
              type="button"
            >
              <span className="material-symbols-outlined text-sm">print</span>
              <span>PRINT REPORT</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
