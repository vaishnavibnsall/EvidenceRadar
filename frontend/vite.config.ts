import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// EvidenceRadar frontend — dev server proxies /api to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          maps: ["leaflet", "react-leaflet"],
          icons: ["lucide-react"],
        },
      },
    },
  },
});
