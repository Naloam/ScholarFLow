import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.indexOf("node_modules") === -1) {
            return undefined;
          }
          // React core in its own chunk; everything else shares "vendor".
          // (Keeps the dep graph acyclic — react-markdown pulls deps that would
          // otherwise cycle between vendor and react-vendor.)
          if (
            id.indexOf("/react/") !== -1 ||
            id.indexOf("/react-dom/") !== -1 ||
            id.indexOf("/scheduler/") !== -1
          ) {
            return "react-vendor";
          }
          return "vendor";
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
