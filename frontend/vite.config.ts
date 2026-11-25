import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// The FastAPI server only serves "/" -> server/static/index.html (no /assets mount),
// so the build is inlined into one self-contained index.html.
export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  build: {
    outDir: "../server/static",
    emptyOutDir: false, // never wipe legacy.html / stats.html
    assetsInlineLimit: 100_000_000,
  },
});
