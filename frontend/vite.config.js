import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: false,
    proxy: {
      '/auth': { target: 'http://127.0.0.1:5000', changeOrigin: true, credentials: 'include' },
      '/sessions': { target: 'http://127.0.0.1:5000', changeOrigin: true, credentials: 'include' },
      '/analytics': { target: 'http://127.0.0.1:5000', changeOrigin: true, credentials: 'include' }
    }
  }
})

