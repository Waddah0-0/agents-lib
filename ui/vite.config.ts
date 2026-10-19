import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // 3000 is the origin the API allows by default (AGENTS_API_CORS_ORIGINS)
  server: { port: 3000, strictPort: true },
  preview: { port: 3000, strictPort: true },
  test: { environment: "jsdom", setupFiles: ["src/test/setup.ts"] },
});
