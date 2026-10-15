import { defineConfig } from "vite";

export default defineConfig({
  build: {
    modulePreload: false,
    outDir: "../custom_components/australian_disaster_watch/frontend",
    emptyOutDir: true,
    target: "es2022",
    minify: true,
    sourcemap: false,
    reportCompressedSize: false,
    rollupOptions: {
      input: {
        "aus-disaster-card": "src/index.ts",
      },
      output: {
        format: "es",
        entryFileNames: "[name].js",
        chunkFileNames: "[name]-[hash].js",
      },
    },
  },
});
