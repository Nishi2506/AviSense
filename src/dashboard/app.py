"""AviSense live dashboard (Streamlit).

Run from the project root:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # streamlit puts only the script's folder on sys.path
    sys.path.insert(0, str(ROOT))

import altair as alt
import cv2
import pandas as pd
import streamlit as st

from src.alert_log import DEFAULT_DB, AlertLog
from src.pipeline import Pipeline, parse_start_time
from src.risk_scoring.risk import DEFAULT_CONFIG, FACTORS, RiskConfig
from src.risk_scoring.zones import load_zones

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}
LEVEL_STYLE = {  # status palette: good / warning / critical, always with icon + label
    "Low": {"color": "#0ca30c", "icon": "✔", "ink": "#ffffff"},
    "Medium": {"color": "#fab219", "icon": "▲", "ink": "#0b0b0b"},
    "High": {"color": "#d03b3b", "icon": "⬣", "ink": "#ffffff"},
}
FACTOR_LABELS = {"count": "Bird count", "speed": "Speed", "proximity": "Runway proximity",
                 "flock_size": "Flock size", "time_of_day": "Time of day"}
CHART_EVERY = 5  # redraw charts every N frames to keep the video smooth

st.set_page_config(page_title="AviSense", page_icon="🦅", layout="wide")


def theme_colors() -> dict:
    dark = getattr(getattr(st.context, "theme", None), "type", "light") == "dark"
    if dark:
        return {"series": "#3987e5", "track": "#184f95", "muted": "#898781", "ink": "#ffffff"}
    return {"series": "#2a78d6", "track": "#cfe2f9", "muted": "#898781", "ink": "#0b0b0b"}


# ---------- sidebar ----------
st.sidebar.title("AviSense")
st.sidebar.caption("Bird strike risk detection")

videos = sorted(p for p in (ROOT / "data" / "videos").rglob("*") if p.suffix.lower() in VIDEO_EXTS)
uploaded = st.sidebar.file_uploader("Upload a video", type=[e[1:] for e in VIDEO_EXTS])
if uploaded is not None:
    dest = ROOT / "data" / "videos" / "uploads" / uploaded.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_bytes(uploaded.getbuffer())
    source = str(dest)
else:
    options = [str(p.relative_to(ROOT)) for p in videos]
    choice = st.sidebar.selectbox("Video", options, index=None,
                                  placeholder="Put videos in data/videos/" if not options else "Choose a video")
    source = str(ROOT / choice) if choice else None
webcam = st.sidebar.checkbox("Use webcam instead")
if webcam:
    source = "0"

zone_files = sorted((ROOT / "configs" / "zones").glob("*.json"))
zone_choice = st.sidebar.selectbox("Runway zones", [p.name for p in zone_files], index=None,
                                   placeholder="Draw one with zone_editor" if not zone_files else "Choose zones")

weights_files = ["yolo11n.pt"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "models").glob("*.pt"))
BEST_WEIGHTS = "airbirds_tiles_temporal2_hn_e1_yolo11n-p2_640.pt"  # best on the test split (see README)
preferred = [i for i, w in enumerate(weights_files) if w.endswith(BEST_WEIGHTS)] or \
            [i for i, w in enumerate(weights_files) if "airbirds_tiles_" in w]
weights = st.sidebar.selectbox("Detector weights", weights_files,
                               index=preferred[0] if preferred else len(weights_files) - 1)

with st.sidebar.expander("Detection settings"):
    imgsz = st.select_slider("Image size", [640, 960, 1280, 1600, 1920],
                             value=1920 if "airbirds_tiles_" in weights else 1280,
                             help="Larger finds smaller birds but runs slower. "
                                  "Use 1920 with tile-trained weights (airbirds_tiles_*).")
    conf = st.slider("Confidence threshold", 0.05, 0.9, 0.1, 0.05)
    all_classes = st.checkbox("Detect all classes (testing only)")
    min_age = st.number_input("Ignore tracks younger than (frames)", 0, 30, 3)
    min_motion = st.number_input("Ignore birds until they move (px)", 0, 100, 20,
                                 help="Most false detections are static specks. 0 keeps everything, "
                                      "including birds that never move.")

base_cfg = RiskConfig.load(ROOT / DEFAULT_CONFIG)
with st.sidebar.expander("Risk weights & thresholds"):
    raw_w = {f: st.slider(FACTOR_LABELS[f], 0.0, 1.0, float(base_cfg.weights[f]), 0.05) for f in FACTORS}
    total = sum(raw_w.values()) or 1.0
    st.caption("Normalised to sum to 1: " + ", ".join(f"{FACTOR_LABELS[f]} {v / total:.2f}" for f, v in raw_w.items()))
    t_med, t_high = st.slider("Medium / High thresholds", 0.0, 1.0,
                              (base_cfg.levels["medium"], base_cfg.levels["high"]), 0.05)

guess = parse_start_time(source) if source else None
use_time = st.sidebar.checkbox("Set video start time", value=guess is not None,
                               help="Needed for the time-of-day factor. Read from the filename when possible.")
start_time = None
if use_time:
    d = st.sidebar.date_input("Date", (guess or datetime.now()).date())
    t = st.sidebar.time_input("Start time", (guess or datetime.now()).time().replace(microsecond=0), step=60)
    start_time = datetime.combine(d, t)

col_run, col_stop = st.sidebar.columns(2)
if col_run.button("▶ Run", type="primary", disabled=not (source and zone_choice), width="stretch"):
    st.session_state.running = True
if col_stop.button("■ Stop", width="stretch"):
    st.session_state.running = False
if not (source and zone_choice):
    st.sidebar.info("Choose a video and a zones file to start.")


# ---------- layout ----------
def level_tile(level: str, score: float, alert: dict | None) -> str:
    s = LEVEL_STYLE[level]
    note = (f"<div style='font-size:0.95rem;margin-top:6px'>ALERT active · driven by "
            f"{FACTOR_LABELS.get(alert['top_factor'], alert['top_factor'])}</div>") if alert else ""
    return (f"<div style='background:{s['color']};color:{s['ink']};border-radius:10px;padding:14px 18px'>"
            f"<div style='font-size:0.9rem;opacity:0.85'>Current risk</div>"
            f"<div style='font-size:3rem;font-weight:700;line-height:1.1'>{s['icon']} {level.upper()}</div>"
            f"<div style='font-size:1.1rem'>score {score:.2f}</div>{note}</div>")


def risk_timeline(df: pd.DataFrame, med: float, high: float, c: dict) -> alt.Chart:
    base = alt.Chart(df).encode(x=alt.X("time_s:Q", title="Video time (s)"))
    line = base.mark_line(strokeWidth=2, color=c["series"]).encode(
        y=alt.Y("risk_score:Q", title="Risk score", scale=alt.Scale(domain=[0, 1])))
    hover = alt.selection_point(fields=["time_s"], nearest=True, on="pointerover", empty=False)
    points = base.mark_point(size=80, filled=True, color=c["series"], stroke="white", strokeWidth=2).encode(
        y="risk_score:Q", opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("time_s:Q", title="Time (s)", format=".1f"),
                 alt.Tooltip("risk_score:Q", title="Risk", format=".2f"),
                 alt.Tooltip("risk_level:N", title="Level"),
                 alt.Tooltip("count:Q", title="Birds"),
                 alt.Tooltip("top_factor:N", title="Main factor")]).add_params(hover)
    rule = base.mark_rule(color=c["muted"], strokeWidth=1).encode(
        opacity=alt.condition(hover, alt.value(0.6), alt.value(0))).transform_filter(hover)
    th = pd.DataFrame({"y": [med, high], "label": [f"Medium ≥ {med:.2f}", f"High ≥ {high:.2f}"]})
    th_rules = alt.Chart(th).mark_rule(strokeDash=[4, 4], color=c["muted"]).encode(y="y:Q")
    th_text = alt.Chart(th).mark_text(align="left", dx=4, dy=-6, color=c["muted"], fontSize=11).encode(
        y="y:Q", x=alt.value(0), text="label:N")
    return (th_rules + th_text + line + rule + points).properties(height=240)


def contribution_chart(contrib: dict, weights: dict, c: dict) -> alt.Chart:
    df = pd.DataFrame({"factor": [FACTOR_LABELS[f] for f in FACTORS],
                       "contribution": [contrib[f] for f in FACTORS],
                       "max": [weights[f] for f in FACTORS]})
    order = [FACTOR_LABELS[f] for f in FACTORS]
    y = alt.Y("factor:N", sort=order, title=None)
    x_scale = alt.Scale(domain=[0, max(weights.values()) * 1.2])  # room for the value labels
    track = alt.Chart(df).mark_bar(color=c["track"], cornerRadiusEnd=4, height=14).encode(
        y=y, x=alt.X("max:Q", scale=x_scale, axis=alt.Axis(tickCount=5),
                     title="Contribution to risk score (pale track = factor's weight)"),
        tooltip=[alt.Tooltip("factor:N", title="Factor"), alt.Tooltip("max:Q", title="Weight", format=".2f")])
    bar = alt.Chart(df).mark_bar(color=c["series"], cornerRadiusEnd=4, height=14).encode(
        y=y, x="contribution:Q",
        tooltip=[alt.Tooltip("factor:N", title="Factor"),
                 alt.Tooltip("contribution:Q", title="Contribution", format=".3f"),
                 alt.Tooltip("max:Q", title="Weight", format=".2f")])
    label = alt.Chart(df).mark_text(align="left", dx=6, color=c["ink"], fontSize=12).encode(
        y=y, x="max:Q", text=alt.Text("contribution:Q", format=".2f"))
    return (track + bar + label).properties(height=200)


st.title("AviSense · Bird Strike Risk Monitor")
top_l, top_r = st.columns([3, 2], gap="large")
video_ph = top_l.empty()
tile_ph = top_r.empty()
kpi_ph = top_r.empty()
contrib_ph = top_r.empty()
timeline_ph = st.empty()
alerts_ph = st.empty()
table_ph = st.empty()


def render_kpis(risk) -> None:
    f = risk.features
    with kpi_ph.container():
        a, b = st.columns(2)
        a.metric("Birds tracked", f["count"])
        b.metric("Largest flock", f["flock_size"])
        dist = f["min_dist_to_zone"]
        a.metric("Nearest to runway", "in zone" if dist == 0 else "—" if pd.isna(dist) else f"{dist:.2f} diag",
                 help="Distance as a fraction of the frame diagonal.")
        b.metric("Fastest bird", f"{f['max_speed']:.2f} diag/s")


def render_alerts(log: AlertLog) -> None:
    df = log.recent(20)
    with alerts_ph.container():
        st.subheader("Alerts")
        if df.empty:
            st.caption("No alerts logged yet.")
            return
        show = df[["id", "status", "peak_level", "peak_score", "top_factor", "max_count",
                   "start_s", "end_s", "duration_s", "started_at", "source"]].copy()
        show["top_factor"] = show["top_factor"].map(lambda f: FACTOR_LABELS.get(f, f))
        show["peak_level"] = show["peak_level"].map(lambda l: f"{LEVEL_STYLE[l]['icon']} {l}" if l in LEVEL_STYLE else l)
        show["source"] = show["source"].map(lambda s: Path(str(s)).name)
        st.dataframe(show, hide_index=True, width="stretch", column_config={
            "peak_score": st.column_config.NumberColumn("Peak score", format="%.2f"),
            "start_s": st.column_config.NumberColumn("Start (s)", format="%.1f"),
            "end_s": st.column_config.NumberColumn("End (s)", format="%.1f"),
            "duration_s": st.column_config.NumberColumn("Duration (s)", format="%.1f"),
            "top_factor": "Main factor", "max_count": "Max birds", "peak_level": "Peak level",
            "started_at": "Wall-clock start"})


log = AlertLog(ROOT / DEFAULT_DB)
render_alerts(log)

if st.session_state.get("running") and source and zone_choice:
    cfg = RiskConfig.load(ROOT / DEFAULT_CONFIG)
    cfg.weights = {f: v / total for f, v in raw_w.items()}
    cfg.levels = {"medium": t_med, "high": t_high}
    camera, zones = load_zones(ROOT / "configs" / "zones" / zone_choice)
    colors = theme_colors()

    with st.spinner("Loading model..."):
        pipe = Pipeline(zones, cfg, str(ROOT / weights) if weights != "yolo11n.pt" else weights,
                        conf=conf, imgsz=imgsz, alert_log=log, start_time=start_time,
                        meta={"source": source, "camera": camera}, birds_only=not all_classes,
                        min_track_age=int(min_age), min_motion=float(min_motion))

    history: list[dict] = []
    last_alert_id = None
    try:
        for res in pipe.run(source):
            r = res.risk
            history.append({"time_s": res.time_s, "risk_score": r.score, "risk_level": r.level,
                            "count": r.features["count"], "top_factor": FACTOR_LABELS.get(r.top_factor, "—")})
            video_ph.image(cv2.cvtColor(res.annotated, cv2.COLOR_BGR2RGB), width="stretch",
                           caption=f"{Path(source).name} · frame {res.frame_idx} · {res.time_s:.1f}s")
            tile_ph.markdown(level_tile(r.level, r.score, res.alert), unsafe_allow_html=True)

            if res.alert and id(pipe.alerts.current) != last_alert_id:
                last_alert_id = id(pipe.alerts.current)
                st.toast(f"{LEVEL_STYLE[res.alert['peak_level']]['icon']} {res.alert['peak_level']} risk alert "
                         f"({FACTOR_LABELS.get(res.alert['top_factor'])})")

            if res.frame_idx % CHART_EVERY == 0:
                render_kpis(r)
                contrib_ph.altair_chart(contribution_chart(r.contributions, cfg.weights, colors),
                                        width="stretch", theme="streamlit")
                df = pd.DataFrame(history)
                timeline_ph.altair_chart(risk_timeline(df, t_med, t_high, colors),
                                         width="stretch", theme="streamlit")
                if res.frame_idx % (CHART_EVERY * 6) == 0:
                    render_alerts(log)
    finally:
        pipe.alerts.finish()
        st.session_state.running = False

    render_alerts(log)
    if history:
        with table_ph.expander("Risk data table"):
            st.dataframe(pd.DataFrame(history).round(3), hide_index=True, width="stretch")
    st.success(f"Finished: {len(history)} frames, {len(pipe.alerts.closed)} alert episode(s).")
else:
    video_ph.info("Choose a video and a runway zones file in the sidebar, then press ▶ Run.")
