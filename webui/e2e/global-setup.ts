import { expect, request, type FullConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

export default async function globalSetup(config: FullConfig) {
    const data = resolve(process.env.E2E_DATA_DIR ?? "../e2e-data");
    if (!existsSync(data))
        throw new Error("E2E_DATA_DIR must point to the compose bind mount");
    process.env.E2E_DATA_DIR = data;
    const python = resolve(process.env.E2E_PYTHON ?? "../.venv/bin/python");
    if (!existsSync(python))
        throw new Error(
            "E2E_PYTHON must point to the synchronized Python environment",
        );
    process.env.E2E_PYTHON = python;
    const api = await request.newContext({
        baseURL: process.env.E2E_API_URL ?? config.projects[0].use.baseURL,
    });
    try {
        await expect
            .poll(
                async () => {
                    try {
                        return (await api.get("/healthz")).status();
                    } catch {
                        return 0;
                    }
                },
                { timeout: 60_000, intervals: [500, 1000, 2000] },
            )
            .toBe(200);
    } finally {
        await api.dispose();
    }
}
