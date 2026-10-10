import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Where the FastAPI backend listens during local development.
  // Mirrors server.py (uvicorn on 127.0.0.1:8000) and nginx.conf (backend:8000).
  const backendTarget = env.VITE_DEV_BACKEND_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      // Proxying /api through the dev server keeps the browser on a single origin,
      // so the SSE stream needs no CORS handling and the backend location lives in
      // one place (VITE_DEV_BACKEND_URL) instead of being hardcoded in api.ts.
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          // Agent runs (browser automation, scraping) can stream for minutes;
          // the proxy's default 2-minute timeout would cut them off.
          timeout: 0,
          proxyTimeout: 0,
        },
      },
    },
  }
})
