import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/app/" : "/",
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/cart": "http://127.0.0.1:8000",
      "/products": "http://127.0.0.1:8000",
      "/promotions": "http://127.0.0.1:8000"
    }
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true
  }
}));
