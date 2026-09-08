import {
    expect,
    type Download,
    type Page,
    type Response,
    type Request,
    type TestInfo,
} from "@playwright/test";
import { execFile } from "node:child_process";
import { readFile, mkdir } from "node:fs/promises";
import { basename, resolve } from "node:path";
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
    const home = page.getByRole("link", { name: "glyphlab", exact: true });
    const target = await home.getAttribute("href");
    expect(target).toBeTruthy();
    const path = new URL(target!, page.url()).pathname.replace("/p/", "/api/projects/");
    await home.click();
    await submitWithRateLimit(page, path, 204, async () => {
        page.once("dialog", (dialog) => void dialog.accept());
        await page.getByRole("button", { name: "今すぐ削除", exact: true }).click();
    }, "DELETE");
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
    method: "POST" | "DELETE" | "GET" = "POST",
    initial?: { response: Response; receivedAt: number },
    notice = "アクセスが集中しています。しばらく待って再試行してください",
) {
    for (let attempt = 0; ; attempt++) {
        let observed = attempt === 0 ? initial : undefined;
        if (!observed) {
            const responseEvent = page.waitForResponse(
                (response) =>
                    response.request().method() === method &&
                    new URL(response.url()).pathname === path,
            );
            await action();
            observed = { response: await responseEvent, receivedAt: Date.now() };
        }
        const { response, receivedAt } = observed;
        if (response.status() !== 429) {
            expect(response.status(), `UI submission to ${path}`).toBe(
                expectedStatus,
            );
            return response;
        }
        await expect(
            page.getByText(notice, { exact: true }).first(),
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
        const deadline = receivedAt + seconds * 1000;
        await expect
            .poll(() => Date.now(), {
                timeout: Math.max(0, deadline - Date.now()) + 3000,
                intervals: [1000],
            })
            .toBeGreaterThanOrEqual(deadline);
    }
}

/** Keep the real one-shot batch input and retry only files the API rejected with 429. */
export async function uploadBatchWithRateLimit(page: Page, projectId: string, files: string[]) {
    const path = `/api/projects/${projectId}/uploads`;
    const responses: { response: Response; receivedAt: number }[] = [];
    let active = 0;
    let maximumActive = 0;
    const matches = (request: Request) =>
        request.method() === "POST" && new URL(request.url()).pathname === path;
    const requested = (request: Request) => {
        if (matches(request)) maximumActive = Math.max(maximumActive, ++active);
    };
    const responded = (response: Response) => {
        if (matches(response.request())) {
            active--;
            responses.push({ response, receivedAt: Date.now() });
        }
    };
    page.on("request", requested);
    page.on("response", responded);
    try {
        await page.locator("input[type=file]").setInputFiles(files);
        for (let index = 0; index < files.length; index++) {
            await expect.poll(() => responses.length, { timeout: 120_000 })
                .toBeGreaterThan(index);
            const status = responses[index].response.status();
            if (status !== 429) expect(status, "Initial upload response").toBe(202);
        }
        expect(responses).toHaveLength(files.length);
        const initial = responses.slice();
        for (const [index, file] of files.entries()) {
            const item = page.locator(".upload-item").filter({ hasText: basename(file) });
            if (initial[index].response.status() === 429)
                await expect(item.getByText("アクセスが集中しています。しばらく待って再試行してください", { exact: true })).toBeVisible();
            await submitWithRateLimit(page, path, 202,
                () => item.getByRole("button", { name: "再試行", exact: true }).click(),
                "POST", initial[index]);
            await expect(item.locator("small[aria-live]")).toHaveText("完了", { timeout: 120_000 });
        }
        expect(maximumActive, "Batch uploads must use the sequential queue").toBe(1);
        expect(responses.filter(({ response }) => response.status() === 202),
            "Each file must be accepted exactly once").toHaveLength(files.length);
        expect(responses.every(({ response }) => [202, 429].includes(response.status()))).toBe(true);
        expect(responses.length).toBeLessThanOrEqual(files.length * 3);
    } finally {
        page.off("request", requested);
        page.off("response", responded);
    }
}

/** Listen throughout quota waits; start the bounded event assertion only after GET200. */
export async function downloadWithRateLimit(
    page: Page,
    path: string,
    action: () => Promise<void>,
    notice?: string,
): Promise<Download> {
    const downloads: Download[] = [];
    const received = (download: Download) => downloads.push(download);
    page.on("download", received);
    try {
        await submitWithRateLimit(page, path, 200, action, "GET", undefined, notice);
        await expect.poll(() => downloads.length).toBe(1);
        return downloads[0];
    } finally {
        page.off("download", received);
    }
}
