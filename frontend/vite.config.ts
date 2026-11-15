import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The API the dev server proxies to. GOS_API overrides it when port 8000 is taken.
const API = process.env.GOS_API ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // One small app; Recharts is most of the bundle. Fine for a local demo.
  build: { chunkSizeWarningLimit: 1000 },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: API, changeOrigin: true },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': { target: API, changeOrigin: true },
    },
  },
})
