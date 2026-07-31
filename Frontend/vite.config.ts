import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The frontend is a static SPA. There is no Node server: in dev we proxy /api
// straight to FastAPI, and in prod the built assets are served statically.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
