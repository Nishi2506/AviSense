// Shared labels, colours and formatting for risk data.

export const FACTORS = ['proximity', 'count', 'flock_size', 'speed', 'time_of_day'];

export const FACTOR_LABELS = {
  proximity: 'Runway Proximity',
  count: 'Bird Count',
  flock_size: 'Flock Size',
  speed: 'Speed',
  time_of_day: 'Time of Day'
};

// Design system status colours: Low = primary (green), Medium = secondary (amber), High = error (red).
export const LEVEL_STYLE = {
  Low: { text: 'text-primary', bg: 'bg-primary', hex: '#10b981', icon: 'check_circle', chip: 'bg-[#10b981]/15 border border-[#10b981]/30 text-[#10b981]', border: 'border-[#10b981]' },
  Medium: { text: 'text-secondary', bg: 'bg-secondary', hex: '#f59e0b', icon: 'report_problem', chip: 'bg-[#f59e0b]/15 border border-[#f59e0b]/30 text-[#f59e0b]', border: 'border-[#f59e0b]' },
  High: { text: 'text-error', bg: 'bg-error', hex: '#ef4444', icon: 'warning', chip: 'bg-[#ef4444]/15 border border-[#ef4444]/30 text-[#ef4444]', border: 'border-[#ef4444]' }
};

export const levelStyle = (level) => LEVEL_STYLE[level] || LEVEL_STYLE.Low;

export const fmt = (v, digits = 2, fallback = '—') =>
  v === null || v === undefined || Number.isNaN(v) ? fallback : Number(v).toFixed(digits);

/** Seconds -> "m:ss.s" (or "h:mm:ss" for long runs). */
export function fmtVideoTime(s) {
  if (s === null || s === undefined) return '—';
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(Math.floor(sec)).padStart(2, '0')}`;
  return `${m}:${sec.toFixed(1).padStart(4, '0')}`;
}

export function fmtDuration(s) {
  if (s === null || s === undefined) return '—';
  if (s < 60) return `${s.toFixed(1)} s`;
  return `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`;
}

/** ISO wall-clock -> "HH:MM:SS" (local camera time, as recorded). */
export const fmtClock = (iso) => (iso ? iso.slice(11, 19) : null);

export const episodeId = (id) => `EP-${String(id).padStart(4, '0')}`;

export const fileName = (path) => (path ? String(path).split(/[\\/]/).pop() : '');

/** Distance from a point to a polygon (0 inside), in pixels; coords are normalised [0, 1]. */
export function distanceToPolygon(px, py, polygon, w, h) {
  const pts = polygon.map(([x, y]) => [x * w, y * h]);
  const x = px * w;
  const y = py * h;
  let inside = false;
  let best = Infinity;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i];
    const [xj, yj] = pts[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    const dx = xj - xi;
    const dy = yj - yi;
    const len2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((x - xi) * dx + (y - yi) * dy) / len2));
    best = Math.min(best, Math.hypot(x - (xi + t * dx), y - (yi + t * dy)));
  }
  return inside ? 0 : best;
}

/** Nearest-zone distance as a fraction of the frame diagonal (the unit the risk formula uses). */
export function zoneDistance(px, py, zones, w, h) {
  if (!zones?.length || !w || !h) return null;
  const diag = Math.hypot(w, h);
  return Math.min(...zones.map((z) => distanceToPolygon(px, py, z.polygon, w, h))) / diag;
}
