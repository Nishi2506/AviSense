// Thin client for the AviSense API (src/api/server.py).

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  config: () => request('/api/config'),
  state: (since = 0) => request(`/api/state?since=${since}`),
  run: (body) =>
    request('/api/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  stop: () => request('/api/stop', { method: 'POST' }),
  alerts: (limit = 500) => request(`/api/alerts?limit=${limit}`),
  zones: (name) => request(`/api/zones/${encodeURIComponent(name)}`),
  results: () => request('/api/results'),
  upload: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/api/videos', { method: 'POST', body: form });
  }
};

export const frameUrl = (seq, runId) => `/api/frame.jpg?seq=${seq}&run=${runId}`;
export const videoFrameUrl = (path) => `/api/videos/frame?path=${encodeURIComponent(path)}`;
