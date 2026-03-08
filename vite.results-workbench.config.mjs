import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    emptyOutDir: false,
    outDir: path.resolve('frontend/assets/dist'),
    lib: {
      entry: path.resolve('frontend/app/results-workbench/main.js'),
      name: 'ResultsWorkbenchVueShell',
      formats: ['iife'],
      fileName: () => 'results-workbench-vue-shell.js',
    },
    rollupOptions: {
      output: {
        banner: 'var process = globalThis.process || { env: { NODE_ENV: "production" } };',
        assetFileNames: 'results-workbench-vue-shell.[ext]',
      },
    },
  },
});
