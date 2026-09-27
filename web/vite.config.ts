import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/session': 'http://127.0.0.1:8000',
      '/quit': 'http://127.0.0.1:8000',
      '/video': 'http://127.0.0.1:8000',
      '/events': { target: 'ws://127.0.0.1:8000', ws: true },
      '/health': 'http://127.0.0.1:8000',
      '/cameras': 'http://127.0.0.1:8000',
      '/config': 'http://127.0.0.1:8000',
      '/sessions': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
  },
})
