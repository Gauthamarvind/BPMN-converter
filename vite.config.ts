/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        // import.meta.dirname needs Node >= 20.11 (CI and the Dockerfile use Node 20).
        '@': path.resolve(import.meta.dirname, '.'),
      },
    },
    build: {
      rollupOptions: {
        output: {
          // Keep the libraries that rarely change in their own chunks so a code change does
          // not invalidate them, and so the first paint does not wait on the animation and
          // icon bundles. bpmn-js is already loaded on demand by BpmnViewer.
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return undefined;
            if (id.includes('react-dom') || /node_modules\/(react|scheduler)\//.test(id)) return 'react';
            if (id.includes('motion') || id.includes('framer-motion')) return 'motion';
            if (id.includes('lucide-react')) return 'icons';
            return undefined;
          },
        },
      },
      chunkSizeWarningLimit: 700,
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy: {
        '/api': 'http://localhost:8000',
      },
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      css: false,
    },
  };
});
