import {
    expect,
    type Download,
    type Page,
    type TestInfo,
} from "@playwright/test";
import { execFile } from "node:child_process";
import { readFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { promisify } from "node:util";

export const execute = promisify(execFile);
export function observeTokenSafety(page: Page) {
    const leaks: string[] = [];
    page.on("request", (req) => {
        if (req.url().includes("glp_")) leaks.push(req.url().split("glp_")[0]);
    });
    return () =>
        expect(leaks, "A request URL contained a bearer token").toEqual([]);
}
export async function downloadBytes(download: Download) {
    const path = await download.path();
    expect(path).not.toBeNull();
    return readFile(path!);
}
export async function corpusFor(
    projectId: string,
    pdf: Download,
    info: TestInfo,
) {
    const dir = info.outputPath("corpus");
    await mkdir(dir, { recursive: true });
    const path = info.outputPath("template.pdf");
    await pdf.saveAs(path);
    await execute(
        process.env.E2E_PYTHON ?? resolve("../.venv/bin/python"),
        [
            resolve("e2e/generate-corpus.py"),
            "--data",
            process.env.E2E_DATA_DIR!,
            "--project",
            projectId,
            "--pdf",
            path,
            "--out",
            dir,
        ],
        {
            timeout: 60_000,
            env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
        },
    );
    return dir;
}
export async function deleteViaUI(page: Page) {
    await page.getByRole("link", { name: "glyphlab", exact: true }).click();
    page.once("dialog", (dialog) => void dialog.accept());
    await page.getByRole("button", { name: "今すぐ削除", exact: true }).click();
    await expect(page).toHaveURL(/\/$/);
}

export async function openTokenLink(page: Page, link: string) {
    const projectPath = new URL(link).pathname.replace("/p/", "/api/projects/");
    for (let attempt = 0; ; attempt++) {
        const responseEvent = page.waitForResponse(
            (response) =>
                response.request().method() === "GET" &&
                new URL(response.url()).pathname === projectPath,
        );
        if (attempt) await page.reload();
        else await page.goto(link);
        const response = await responseEvent;
        if (response.status() !== 429) return response.status();
        const seconds = Number(response.headers()["retry-after"]);
        if (
            attempt >= 2 ||
            !Number.isFinite(seconds) ||
            seconds <= 0 ||
            seconds > 90
        )
            throw new Error(
                "Project view quota cannot recover within the browser acceptance budget",
            );
        const deadline = Date.now() + seconds * 1000;
        await expect
            .poll(() => Date.now(), {
                timeout: seconds * 1000 + 3000,
                intervals: [1000],
            })
            .toBeGreaterThanOrEqual(deadline);
    }
}

/** Retry only an explicitly rejected UI mutation, following the server's deadline. */
export async function submitWithRateLimit(
    page: Page,
    path: string,
    expectedStatus: number,
    action: () => Promise<void>,
) {
    for (let attempt = 0; ; attempt++) {
        const responseEvent = page.waitForResponse(
            (response) =>
                response.request().method() === "POST" &&
                new URL(response.url()).pathname === path,
        );
        await action();
        const response = await responseEvent;
        if (response.status() !== 429) {
            expect(response.status(), `UI submission to ${path}`).toBe(
                expectedStatus,
            );
            return;
        }
        await expect(
            page.getByText("アクセスが集中しています。しばらく待って再試行してください", { exact: true }).first(),
        ).toBeVisible();
        const seconds = Number(response.headers()["retry-after"]);
        if (
            attempt >= 2 ||
            !Number.isFinite(seconds) ||
            seconds <= 0 ||
            seconds > 90
        )
            throw new Error(
                "UI submission quota cannot recover within the browser acceptance budget",
            );
        const deadline = Date.now() + seconds * 1000;
        await expect
            .poll(() => Date.now(), {
                timeout: seconds * 1000 + 3000,
                intervals: [1000],
            })
            .toBeGreaterThanOrEqual(deadline);
    }
}
