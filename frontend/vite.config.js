import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Plugin to rewrite SPA routes to spa.html
function spaFallback() {
  return {
    name: 'spa-fallback',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        // SPA routes that should fallback to spa.html
        const spaRoutes = ['/', '/demo', '/a/', '/flight-recorder'];
        const isSpaRoute = spaRoutes.some(route =>
          req.url === route || req.url.startsWith(route)
        );
        // Don't rewrite files with extensions or special paths
        const hasExtension = /\.\w+$/.test(req.url);
        const isSpecialPath = req.url.startsWith('/@') || req.url.startsWith('/src') || req.url.startsWith('/node_modules');

        if (isSpaRoute && !hasExtension && !isSpecialPath) {
          req.url = '/spa.html';
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), spaFallback()],
  root: '.',
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: './spa.html',
    },
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/static': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
  },
});
