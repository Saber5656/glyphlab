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
        process.env.E2E_PYTHON ?? "python3",
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
