import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // Dev server configuration
  server: {
    port: 5173,
    host: true, // Required for Docker — listen on 0.0.0.0

    // Proxy /api/* requests to the FastAPI backend
    // In local dev: backend runs at localhost:8000
    // In docker-compose: backend service is resolved by Docker DNS
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  // Build output directory
  build: {
    outDir: 'dist',
    sourcemap: true, // Enable source maps for debugging
  },
})
