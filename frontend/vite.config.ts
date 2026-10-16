import { defineConfig } from "vitest/config";

export default defineConfig({
  // Chunks load relative to the bundle, which HA serves at /ausnz_disaster_watch/.
  base: "./",
  build: {
    modulePreload: false,
    outDir: "../custom_components/ausnz_disaster_watch/frontend",
    // The output folder holds only generated files: stale map chunks must not linger.
    emptyOutDir: true,
    target: "es2022",
    minify: true,
    sourcemap: false,
    reportCompressedSize: false,
    rollupOptions: {
      input: {
        "ausnz-disaster-card": "src/index.ts",
      },
      output: {
        format: "es",
        entryFileNames: "[name].js",
        chunkFileNames: "ausnz-disaster-[name]-[hash].js",
      },
    },
  },
  test: {
    include: ["tests/unit/**/*.test.ts"],
    environment: "node",
  },
});
