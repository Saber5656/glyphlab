import { defineConfig } from "vitest/config";

export default defineConfig({
    test: {
        environment: "./src/test/environment.ts",
        environmentOptions: { jsdom: { url: "http://localhost/" } },
        setupFiles: ["./src/test/setup.ts"],
        globals: true,
        exclude: ["e2e/**", "node_modules/**"],
    },
});
