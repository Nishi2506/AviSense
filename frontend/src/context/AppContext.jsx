import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import { FACTORS } from '../lib/format';

const AppContext = createContext();
const STORAGE_KEY = 'avisense.settings.v1';
const WEBCAM = '__webcam__';

function loadStored() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

/** Defaults taken from the server's config (configs/risk.yaml and the pipeline defaults). */
function defaultsFrom(config) {
  const r = config.risk;
  return {
    detectorWeights: config.defaults.weights,
    imgsz: config.defaults.imgsz,
    conf: config.defaults.conf,
    minMotion: config.defaults.min_motion,
    minTrackAge: config.defaults.min_track_age,
    weights: Object.fromEntries(FACTORS.map((f) => [f, Math.round((r.weights[f] || 0) * 100)])),
    medThreshold: r.levels.medium,
    highThreshold: r.levels.high,
    minDuration: r.alerts?.min_duration_s ?? 1,
    mergeGap: r.alerts?.merge_gap_s ?? 2,
    audioAlertEnabled: false,
    startTimeMode: 'auto', // 'auto' (from file name) | 'manual' | 'none'
    manualStartTime: '',
    selectedPreset: 'standard'
  };
}

export function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + delay + 0.18);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.2);
    });
    setTimeout(() => ctx.close(), 800);
  } catch {
    /* audio unavailable */
  }
}

export function AppProvider({ children }) {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState('');
  const [settings, setSettings] = useState(null);
  const [videoPath, setVideoPath] = useState(() => loadStored().videoPath || null);
  const [zonesFile, setZonesFile] = useState(() => loadStored().zonesFile || null);
  const [snapshot, setSnapshot] = useState(null);
  const [history, setHistory] = useState([]);
  const [runError, setRunError] = useState('');
  const [alerts, setAlerts] = useState({ total: 0, alerts: [] });
  const [selectedEpisodeId, setSelectedEpisodeId] = useState(null);
  const [utcClock, setUtcClock] = useState('');

  // ---- config ----
  const loadConfig = useCallback(async () => {
    try {
      const c = await api.config();
      setConfig(c);
      setConfigError('');
      setSettings((prev) => prev || { ...defaultsFrom(c), ...loadStored().settings });
      return c;
    } catch (e) {
      setConfigError(e.message);
      return null;
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // keep the selection valid for the videos/zones that exist
  useEffect(() => {
    if (!config) return;
    const paths = config.videos.map((v) => v.path);
    if (videoPath !== WEBCAM && !paths.includes(videoPath)) {
      const v = config.videos.find((x) => x.zones) || config.videos[0];
      setVideoPath(v ? v.path : null);
      if (v?.zones) setZonesFile(v.zones);
    }
    if (zonesFile && !config.zones.includes(zonesFile)) setZonesFile(null);
  }, [config]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ settings, videoPath, zonesFile }));
    } catch {
      /* storage unavailable */
    }
  }, [settings, videoPath, zonesFile]);

  const selectVideo = useCallback(
    (path) => {
      setVideoPath(path);
      const v = config?.videos.find((x) => x.path === path);
      if (v?.zones) setZonesFile(v.zones);
    },
    [config]
  );

  const updateSettings = useCallback((patch) => setSettings((s) => ({ ...s, ...patch })), []);
  const resetRiskDefaults = useCallback(() => {
    if (!config) return;
    const d = defaultsFrom(config);
    updateSettings({
      weights: d.weights,
      medThreshold: d.medThreshold,
      highThreshold: d.highThreshold,
      minDuration: d.minDuration,
      mergeGap: d.mergeGap,
      selectedPreset: 'standard'
    });
  }, [config, updateSettings]);

  // ---- alerts ----
  const refreshAlerts = useCallback(async () => {
    try {
      setAlerts(await api.alerts());
    } catch {
      /* keep the last list */
    }
  }, []);

  useEffect(() => {
    refreshAlerts();
  }, [refreshAlerts]);

  // ---- run state polling ----
  const sinceRef = useRef(0);
  const runIdRef = useRef(null);
  const statusRef = useRef(null);
  const alertKeyRef = useRef(null);
  const audioRef = useRef(false);
  audioRef.current = settings?.audioAlertEnabled;

  useEffect(() => {
    let stopped = false;
    let timer = null;
    let lastAlertsRefresh = 0;

    const poll = async () => {
      let active = false;
      try {
        let s = await api.state(sinceRef.current);
        if (s.run_id !== runIdRef.current) {
          // new run (or first poll): fetch its whole timeline
          runIdRef.current = s.run_id;
          if (s.history_start !== 0) s = await api.state(0);
          setHistory(s.history);
        } else if (s.history.length) {
          setHistory((h) => h.concat(s.history));
        }
        sinceRef.current = s.history_len;
        setSnapshot(s);
        active = s.status === 'loading' || s.status === 'running';

        const key = s.alert ? `${s.run_id}:${s.alert.start_frame}` : null;
        if (key && key !== alertKeyRef.current && audioRef.current) beep();
        alertKeyRef.current = key;

        const finishedNow = statusRef.current && statusRef.current !== s.status && !active;
        statusRef.current = s.status;
        if (finishedNow || (active && Date.now() - lastAlertsRefresh > 3000)) {
          lastAlertsRefresh = Date.now();
          refreshAlerts();
        }
      } catch {
        /* server not reachable yet; keep polling */
      }
      if (!stopped) timer = setTimeout(poll, active ? 250 : 1500);
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [refreshAlerts]);

  // ---- clock ----
  useEffect(() => {
    const tick = () => setUtcClock(`${new Date().toISOString().slice(11, 19)} UTC`);
    tick();
    const i = setInterval(tick, 1000);
    return () => clearInterval(i);
  }, []);

  // ---- derived ----
  const status = snapshot?.status || 'idle';
  const systemState = status === 'running' ? 'LIVE' : status === 'loading' ? 'CALIBRATING' : 'STANDBY';
  const isWebcam = videoPath === WEBCAM;
  const selectedVideo = useMemo(
    () => (isWebcam ? null : config?.videos.find((v) => v.path === videoPath) || null),
    [config, videoPath, isWebcam]
  );

  const startTimeFor = useCallback(() => {
    if (!settings) return null;
    if (settings.startTimeMode === 'manual') return settings.manualStartTime || null;
    if (settings.startTimeMode === 'auto') return selectedVideo?.start_time || null;
    return null;
  }, [settings, selectedVideo]);

  const startRun = useCallback(async () => {
    if (!settings) return;
    setRunError('');
    try {
      await api.run({
        source: isWebcam ? '0' : videoPath,
        zones: zonesFile,
        weights: settings.detectorWeights,
        imgsz: settings.imgsz,
        conf: settings.conf,
        min_motion: settings.minMotion,
        min_track_age: settings.minTrackAge,
        start_time: startTimeFor(),
        risk_weights: settings.weights,
        medium: settings.medThreshold,
        high: settings.highThreshold,
        min_duration_s: settings.minDuration,
        merge_gap_s: settings.mergeGap
      });
    } catch (e) {
      setRunError(e.message);
    }
  }, [settings, isWebcam, videoPath, zonesFile, startTimeFor]);

  const stopToStandby = useCallback(async () => {
    try {
      await api.stop();
    } catch (e) {
      setRunError(e.message);
    }
  }, []);

  const uploadVideo = useCallback(
    async (file) => {
      const { path } = await api.upload(file);
      const c = await loadConfig();
      if (c) selectVideo(path);
      return path;
    },
    [loadConfig, selectVideo]
  );

  const canRun = Boolean(settings && zonesFile && (isWebcam || videoPath) && settings.detectorWeights);

  const value = {
    config,
    configError,
    settings,
    updateSettings,
    resetRiskDefaults,
    videoPath,
    selectVideo,
    isWebcam,
    WEBCAM,
    selectedVideo,
    zonesFile,
    setZonesFile,
    uploadVideo,
    startTimeFor,
    snapshot,
    status,
    systemState,
    history,
    runError,
    canRun,
    startRun,
    stopToStandby,
    alerts,
    refreshAlerts,
    selectedEpisodeId,
    setSelectedEpisodeId,
    utcClock,
    medThreshold: settings?.medThreshold ?? 0.3,
    highThreshold: settings?.highThreshold ?? 0.6
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
