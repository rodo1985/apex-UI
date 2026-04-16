import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Configure the Vitest environment for the React portal.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   import("vitest/config").UserConfig: Vitest configuration.
 *
 * Raises:
 *   This module does not raise errors directly.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
