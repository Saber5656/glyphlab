import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
    testDir: "./e2e",
    testMatch: process.env.E2E_FAILURE_PROBE
        ? "failure-probe.ts"
        : "hosted.spec.ts",
    timeout: 180_000,
    expect: { timeout: 15_000 },
    fullyParallel: false,
    workers: 1,
    forbidOnly: Boolean(process.env.CI),
    retries: process.env.CI ? 1 : 0,
    reporter: [["list"], ["html", { open: "never" }]],
    globalSetup: "./e2e/global-setup.ts",
    use: {
        baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
        locale: "ja-JP",
        permissions: ["clipboard-read"],
        actionTimeout: 15_000,
        trace: "retain-on-failure",
        video: "retain-on-failure",
        screenshot: "only-on-failure",
    },
    projects: [
        {
            name: "chromium",
            use: {
                ...devices["Desktop Chrome"],
                permissions: ["clipboard-read", "clipboard-write"],
            },
        },
        { name: "webkit", use: { ...devices["Desktop Safari"] } },
        {
            name: "chromium-mobile",
            use: {
                ...devices["Pixel 7"],
                permissions: ["clipboard-read", "clipboard-write"],
            },
        },
    ],
});
