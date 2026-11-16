import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// `npm run dev` serves the UI on :3000 and forwards /api to the Python server
// (python -m src.api.server, default http://127.0.0.1:8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: false,
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  }
});
