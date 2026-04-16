import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Configure the frontend build and local API proxy.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   import("vite").UserConfig: Vite configuration.
 *
 * Raises:
 *   This module does not raise errors directly.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
