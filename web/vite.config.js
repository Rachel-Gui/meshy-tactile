import { defineConfig } from 'vite';
import { copyFileSync, mkdirSync } from 'node:fs';
import { basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const backendPort = process.env.VITE_BACKEND_PORT ?? '8000';
const backendUrl = `http://127.0.0.1:${backendPort}`;
const playbackFiles = [
  '../tactile_data_for_colleague_20260819/tactile_96points_20260817_194852.csv',
  '../tactile_data_for_colleague_20260819/tactile_96points_20260817_200426.csv',
  '../tactile_data_for_colleague_20260819/tactile_96points_20260825_144129.csv',
  '../tactile_data_for_colleague_20260819/tactile_96points_20260825_144214.csv',
  '../tactile_96points_20260827_115909.csv',
];

function copyPlaybackData() {
  return {
    name: 'copy-playback-data',
    closeBundle() {
      const outputDirectory = fileURLToPath(new URL('./dist/data/', import.meta.url));
      mkdirSync(outputDirectory, { recursive: true });
      playbackFiles.forEach((relativePath) => {
        const source = fileURLToPath(new URL(relativePath, import.meta.url));
        copyFileSync(source, `${outputDirectory}/${basename(source)}`);
      });
    },
  };
}

export default defineConfig({
  plugins: [copyPlaybackData()],
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
