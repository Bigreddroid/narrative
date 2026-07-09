/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The app calls the API at the relative path /api. In dev, Vite proxies that to
// a backend. Default is a local backend on :8000; set VITE_API_TARGET (in web/.env)
// to the deployed URL to run the frontend against the live prod backend with no
// local backend at all. Dev-server only — has no effect on the production build.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_TARGET || "http://localhost:8000";

  return {
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
          target: apiTarget,
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
  };
});
