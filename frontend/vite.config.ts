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
          if (id.indexOf("@tiptap") !== -1) {
            return "tiptap";
          }
          if (id.indexOf("react") !== -1 || id.indexOf("scheduler") !== -1) {
            return "react-vendor";
          }
          if (id.indexOf("zustand") !== -1) {
            return "state-vendor";
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
