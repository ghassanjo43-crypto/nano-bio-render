/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Backend origin the dev server proxies to. Only the proxy target — the browser
 * never sees this address.
 */
const BACKEND = process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Both loopback spellings, so the app works at whichever the user types.
    host: true,
    /*
     * Same-origin proxy — this is a correctness fix, not a convenience.
     *
     * The session cookie is `SameSite=Lax`. When the app was served from
     * `localhost:5173` and called the API directly at `127.0.0.1:8000`, those
     * are DIFFERENT SITES: the browser accepted the cookie on the login
     * response but then refused to send it on any subsequent request, so the
     * user was signed out the instant they signed in. Chrome's third-party
     * cookie restrictions produce the same result.
     *
     * Proxying through the dev server's own origin means there is no
     * cross-site request at all, and the cookie behaves correctly at
     * `localhost`, `127.0.0.1` or a LAN address alike.
     */
    proxy: {
      '/api': { target: BACKEND, changeOrigin: false },
      '/health': { target: BACKEND, changeOrigin: false },
      '/ready': { target: BACKEND, changeOrigin: false },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
