import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:5001' },
    // 开发期预热入口文件，首屏请求不再等待按需编译。
    warmup: { clientFiles: ['./src/bootstrap.tsx', './src/main.tsx'] },
  },
  optimizeDeps: {
    // 预打包体积大或含 CJS 的依赖，避免开发期反复触发重新预构建。
    include: ['react', 'react-dom', 'react-dom/client', 'lucide-react'],
  },
  build: {
    target: 'es2020',
    cssCodeSplit: true,
    // 只对首屏真正用到的代码设阈值告警，超过 250 kB 说明分包退化。
    chunkSizeWarningLimit: 250,
    rollupOptions: {
      output: {
        // 框架与图标库各自成包：发版时用户只需重新下载业务分包，
        // 这两个分包的内容哈希不变，可继续命中强缓存。
        codeSplitting: {
          groups: [
            { name: 'vendor-react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/, priority: 20 },
            { name: 'vendor-icons', test: /node_modules[\\/]lucide-react[\\/]/, priority: 10 },
          ],
        },
      },
    },
  },
  test: { environment: 'jsdom', globals: true },
})
