/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Split large, independently-cacheable vendors out of the app chunk.
          react: ["react", "react-dom", "react-router-dom"],
          motion: ["framer-motion"],
          d3: ["d3", "topojson-client"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    // worker_threads tear down uncleanly on Node 24/Windows (Tinypool crash on
    // exit even when all tests pass); child-process forks exit cleanly.
    pool: "forks",
    setupFiles: "./src/test/setup.js",
    // Component/hook tests only. The standalone lib property tests
    // (src/lib/*.test.mjs) run via plain node in CI, not vitest.
    include: ["src/**/*.test.{js,jsx}"],
    exclude: ["**/*.test.mjs", "node_modules/**"],
  },
});
