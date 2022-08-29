import { defineConfig } from 'vite'

// vite.config.js
export default defineConfig({
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        entrypoint: 'src/index.js'
      },
    },
    outDir: 'dist'
  },
  base: '/static/',
})
