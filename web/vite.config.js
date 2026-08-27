import { defineConfig } from 'vite';

const backendPort = process.env.VITE_BACKEND_PORT ?? '8000';
const backendUrl = `http://127.0.0.1:${backendPort}`;

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        ws: true,
      },
    },
  },
  build: {
    target: 'es2022',
  },
});
