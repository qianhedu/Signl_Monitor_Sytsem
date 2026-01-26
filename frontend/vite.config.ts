import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Vite 配置说明文档：https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5873,
    proxy: {
      '/api': {
        target: 'http://localhost:8802',
        changeOrigin: true,
      }
    }
  }
})
