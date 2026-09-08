import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { join } from "node:path";
import {
    corpusFor,
    deleteViaUI,
    downloadBytes,
    observeTokenSafety,
    openTokenLink,
    submitWithRateLimit,
} from "./helpers";

type Artifact = { id: string; kind: string; sha256: string };

test.describe.serial("Japanese hosted journey and upload recovery", () => {
    let link = "";
    let projectId = "";
    let corpus = "";
    let deleted = false;

    test("create, copy, print, ingest two pages, accept, build, download and reopen", async ({
        page,
        browser,
    }, info) => {
        const assertSafe = observeTokenSafety(page);
        const listings: Artifact[][] = [];
        page.on("response", async (response) => {
            if (
                /\/artifacts$/.test(new URL(response.url()).pathname) &&
                response.ok()
            ) {
                listings.push((await response.json()).artifacts);
            }
        });
        await page.goto("/");
        await expect(page.locator("html")).toHaveAttribute("lang", "ja");
        await page
            .getByLabel("プロジェクト名", { exact: true })
            .fill("手書き受入テスト");
        await page.getByLabel("フォント名", { exact: true }).fill("E2E Font");
        await page.getByLabel(/^文字セット/).selectOption("ascii");
        for (let attempt = 0; ; attempt++) {
            const responseEvent = page.waitForResponse(
                (response) =>
                    response.request().method() === "POST" &&
                    new URL(response.url()).pathname === "/api/projects",
            );
            await page
                .getByRole("button", { name: "作成する", exact: true })
                .click();
            const response = await responseEvent;
            if (response.status() !== 429) {
                expect(response.status()).toBe(201);
                break;
            }
            const seconds = Number(response.headers()["retry-after"]);
            if (
                attempt > 1 ||
                !Number.isFinite(seconds) ||
                seconds <= 0 ||
                seconds > 90
            ) {
                throw new Error(
                    "Project creation quota exhausted; use a fresh authorized E2E stack or wait for its reset",
                );
            }
            // Honor the server's deadline; never weaken production rate-limit settings.
            const retryAt = Date.now() + seconds * 1000;
            await expect
                .poll(() => Date.now(), {
                    timeout: seconds * 1000 + 3000,
                    intervals: [1000],
                })
                .toBeGreaterThanOrEqual(retryAt);
        }
        const panel = page.getByRole("dialog");
        await expect(panel).toBeVisible();
        link = await panel
            .getByLabel("共有リンク", { exact: true })
            .inputValue();
        projectId = new URL(link).pathname.split("/").pop()!;
        await panel
            .getByRole("button", { name: "リンクをコピー", exact: true })
            .click();
        await expect(
            panel.getByRole("button", { name: "コピーしました", exact: true }),
        ).toBeVisible();
        await expect
            .poll(() => page.evaluate(() => navigator.clipboard.readText()))
            .toBe(link);
        expect(
            await page.evaluate(
                (id) => localStorage.getItem(`glyphlab:token:${id}`),
                projectId,
            ),
        ).toMatch(/^glp_/);
        await panel
            .getByRole("button", { name: "保存したので閉じる", exact: true })
            .click();
        await expect(page).toHaveURL(new RegExp(`/p/${projectId}$`));
        const pdfEvent = page.waitForEvent("download");
        await page
            .getByRole("button", { name: "ダウンロード", exact: true })
            .click();
        const pdf = await pdfEvent;
        expect((await downloadBytes(pdf)).subarray(0, 4).toString()).toBe(
            "%PDF",
        );
        corpus = await corpusFor(projectId, pdf, info);
        await page
            .getByRole("link", { name: "書いてアップロード", exact: true })
            .click();
        const uploaded: string[] = [];
        page.on("request", (request) => {
            if (request.method() === "POST" && /\/uploads$/.test(request.url()))
                uploaded.push(request.url());
        });
        await page
            .locator("input[type=file]")
            .setInputFiles([
                join(corpus, "page-0.png"),
                join(corpus, "page-1.png"),
            ]);
        await expect(
            page.locator(".upload-item").filter({ hasText: "完了" }),
        ).toHaveCount(2, { timeout: 120_000 });
        expect(uploaded).toHaveLength(2);
        await expect(page.getByText("ページ 1", { exact: true })).toBeVisible();
        await expect(page.getByText("ページ 2", { exact: true })).toBeVisible();
        await expect(page.locator(".result").first()).toContainText(
            /(?:extracted:|抽出) [1-9]\d*/,
        );
        const svgRequests = new Map<string, number>();
        page.on("request", (request) => {
            const url = new URL(request.url());
            if (
                request.method() === "GET" &&
                url.pathname.endsWith(".svg") &&
                url.pathname.includes("/glyphs/")
            )
                svgRequests.set(url.href, (svgRequests.get(url.href) ?? 0) + 1);
        });
        await page
            .getByRole("link", { name: "確認画面へ", exact: true })
            .first()
            .click();
        const automatic = page.locator(".glyph-cell.status-auto");
        await expect(automatic.first()).toBeVisible();
        const count = await automatic.count();
        await submitWithRateLimit(
            page,
            `/api/projects/${projectId}/glyphs:review`,
            200,
            async () => {
                page.once("dialog", (dialog) => void dialog.accept());
                await page
                    .getByRole("button", { name: "AUTOをすべて採用", exact: true })
                    .click();
            },
        );
        await expect(automatic).toHaveCount(0);
        await expect(page.locator(".glyph-cell.status-accepted")).toHaveCount(
            count,
        );
        await page.screenshot({
            path: info.outputPath("review-grid.png"),
            fullPage: false,
        });
        await info.attach("review-grid", {
            path: info.outputPath("review-grid.png"),
            contentType: "image/png",
        });
        await page.getByRole("link", { name: "ビルドへ", exact: true }).click();
        await submitWithRateLimit(
            page,
            `/api/projects/${projectId}/builds`,
            202,
            () =>
                page
                    .getByRole("button", { name: "フォントを生成", exact: true })
                    .click(),
        );
        await expect(
            page.locator(".artifact").filter({ hasText: /^ttf/ }),
        ).toBeVisible({ timeout: 120_000 });
        // A quota retry must not hide the original duplicate-preview regression.
        expect(svgRequests.size).toBeGreaterThan(0);
        for (const [url, requests] of svgRequests) {
            expect(
                new URL(url).searchParams.get("v"),
                "SVG URL must carry its geometry revision",
            ).toBeTruthy();
            expect(
                requests,
                "Review must not refetch an unchanged geometry revision",
            ).toBe(1);
        }
        await expect
            .poll(
                () =>
                    page.evaluate(() =>
                        Array.from(document.fonts).some(
                            (face) =>
                                face.family === "GlyphlabPreview" &&
                                face.status === "loaded",
                        ),
                    ),
                { timeout: 30_000 },
            )
            .toBe(true);
        expect(
            await page.evaluate(() =>
                document.fonts.check("16px GlyphlabPreview"),
            ),
        ).toBe(true);
        await page.locator("textarea").fill("My handwriting 123");
        await expect(page.locator(".font-preview").first()).toHaveText(
            "My handwriting 123",
        );
        await expect(page.locator(".font-preview").first()).toHaveCSS(
            "font-family",
            /GlyphlabPreview/,
        );
        await page.screenshot({
            path: info.outputPath("build-preview.png"),
            fullPage: true,
        });
        await info.attach("build-preview", {
            path: info.outputPath("build-preview.png"),
            contentType: "image/png",
        });
        const ttfEvent = page.waitForEvent("download");
        await page
            .locator(".artifact")
            .filter({ hasText: /^ttf/ })
            .getByRole("button", { name: "ダウンロード", exact: true })
            .click();
        const bytes = await downloadBytes(await ttfEvent);
        const listed = listings
            .flat()
            .find((artifact) => artifact.kind === "ttf");
        expect(listed?.sha256).toMatch(/^[a-f0-9]{64}$/);
        expect(createHash("sha256").update(bytes).digest("hex")).toBe(
            listed!.sha256,
        );
        const fresh = await browser.newContext({
            locale: "ja-JP",
            viewport: page.viewportSize(),
        });
        try {
            const restored = await fresh.newPage();
            const assertFreshSafe = observeTokenSafety(restored);
            expect(await openTokenLink(restored, link)).toBe(200);
            await expect(restored).toHaveURL(new RegExp(`/p/${projectId}$`));
            expect(new URL(restored.url()).hash).toBe("");
            await expect(
                restored.getByText(new RegExp(`採用 ${count}・`)),
            ).toBeVisible();
            assertFreshSafe();
        } finally {
            await fresh.close();
        }
        assertSafe();
    });

    test("blank JPEG guidance, oversized precheck, deletion and expired link", async ({
        page,
    }) => {
        const assertSafe = observeTokenSafety(page);
        await openTokenLink(page, link);
        await page
            .getByRole("link", { name: "書いてアップロード", exact: true })
            .click();
        const uploadRequests: string[] = [];
        page.on("request", (request) => {
            if (request.method() === "POST" && /\/uploads$/.test(request.url()))
                uploadRequests.push(request.url());
        });
        let uploadAttempt = 0;
        await submitWithRateLimit(page, `/api/projects/${projectId}/uploads`, 202, async () => {
            if (uploadAttempt++ === 0)
                await page.locator("input[type=file]").setInputFiles(join(corpus, "blank.jpg"));
            else
                await page.locator(".upload-item").filter({ hasText: "blank.jpg" })
                    .getByRole("button", { name: "再試行", exact: true }).click();
        });
        await expect(
            page.getByText(
                "四隅のマーカーが見つかりません。ページ全体が写るように撮り直してください",
                { exact: true },
            ),
        ).toBeVisible({ timeout: 120_000 });
        await expect(
            page.locator(".upload-item").filter({ hasText: "blank.jpg" })
                .getByRole("button", { name: "再試行", exact: true }),
        ).toBeVisible();
        const submitted = uploadRequests.length;
        expect(submitted).toBeGreaterThanOrEqual(1);
        expect(submitted).toBeLessThanOrEqual(3);
        await page.locator("input[type=file]").setInputFiles({
            name: "too-large.jpg",
            mimeType: "image/jpeg",
            buffer: Buffer.alloc(12 * 1024 * 1024 + 1),
        });
        await expect(
            page.getByText(
                /^画像が大きすぎます。12MB(?:・3600万画素)?以内にしてください$/,
                {
                    exact: true,
                },
            ),
        ).toBeVisible();
        expect(uploadRequests).toHaveLength(submitted);
        await deleteViaUI(page);
        deleted = true;
        await expect
            .poll(() => page.evaluate(() => navigator.clipboard.readText()))
            .toBe(link);
        expect(
            await page.evaluate(
                (id) => localStorage.getItem(`glyphlab:token:${id}`),
                projectId,
            ),
        ).toBeNull();
        await openTokenLink(page, link);
        await expect(
            page.getByText(
                "プロジェクトが見つからないか、リンクが無効・期限切れです",
                { exact: true },
            ),
        ).toBeVisible();
        expect(new URL(page.url()).hash).toBe("");
        assertSafe();
    });

    test.afterAll(async ({ browser }) => {
        if (!link || deleted) return;
        const context = await browser.newContext();
        try {
            const page = await context.newPage();
            await openTokenLink(page, link);
            await deleteViaUI(page);
        } finally {
            await context.close();
        }
    });
});
