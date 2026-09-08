import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import {
    afterAll,
    afterEach,
    beforeAll,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";
import Build from "./Build";

const projectId = "00000000-0000-0000-0000-000000000001";
const jobId = "job-1";
const server = setupServer();
const artifact = (
    id: string,
    kind: "ttf" | "woff2" | "proof_html" | "qa_json",
    buildId = jobId,
) => ({
    id,
    kind,
    bytes: 4,
    sha256: "hash",
    created_at: "2026-09-08T10:00:00Z",
    job_id: buildId,
});

function renderBuild() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={[`/p/${projectId}/build`]}>
                <Routes>
                    <Route path="/p/:projectId/build" element={<Build />} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    );
}

function commonHandlers(artifacts: unknown[] = []) {
    server.use(
        http.get("http://localhost/api/projects/:projectId/artifacts", () =>
            HttpResponse.json({ artifacts }),
        ),
        http.get("http://localhost/api/projects/:projectId/glyphs", () =>
            HttpResponse.json({
                glyphs: [
                    {
                        codepoint: "U+0041",
                        char: "A",
                        status: "accepted",
                        advance: 500,
                        warnings: [],
                        updated_at: "now",
                    },
                ],
            }),
        ),
        http.get("http://localhost/api/projects/:projectId/jobs/:jobId", () =>
            HttpResponse.json({ status: "succeeded" }),
        ),
        http.get(
            "http://localhost/api/projects/:projectId/artifacts/:artifactId",
            ({ params }) => {
                if (params.artifactId === "qa-1")
                    return HttpResponse.json({
                        findings: [
                            { check_id: "check/name", severity: "FAIL" },
                        ],
                    });
                return new HttpResponse(new Uint8Array([0, 1, 2, 3]), {
                    headers: { "Content-Type": "font/woff2" },
                });
            },
        ),
    );
}

describe("Build page", () => {
    beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
    afterEach(() => server.resetHandlers());
    afterAll(() => server.close());
    beforeEach(() => {
        localStorage.setItem(
            `glyphlab:token:${projectId}`,
            "glp_1234567890123456789012345678901234567890123",
        );
        class MockFontFace {
            family: string;
            constructor(family: string) {
                this.family = family;
            }
            load() {
                return Promise.resolve(this);
            }
        }
        vi.stubGlobal("FontFace", MockFontFace);
        Object.defineProperty(document, "fonts", {
            configurable: true,
            value: { add: vi.fn(), delete: vi.fn() },
        });
    });
    afterEach(() => {
        localStorage.clear();
        vi.unstubAllGlobals();
    });

    it("triggers a build, polls it, and renders three preview sizes", async () => {
        commonHandlers([artifact("woff-1", "woff2")]);
        server.use(
            http.post("http://localhost/api/projects/:projectId/builds", () =>
                HttpResponse.json({ job_id: jobId }, { status: 202 }),
            ),
            http.get(
                "http://localhost/api/projects/:projectId/jobs/:jobId",
                () => HttpResponse.json({ status: "succeeded" }),
            ),
        );
        const view = renderBuild();
        await userEvent
            .setup()
            .click(screen.getByRole("button", { name: "フォントを生成" }));
        await waitFor(() =>
            expect(
                screen
                    .getAllByText(
                        "きょうは「Glyphlab」でフォントを作った。ローマ字とかなが、ひとつの文で・ながく・つづく！",
                    )
                    .filter((element) =>
                        element.classList.contains("font-preview"),
                    ),
            ).toHaveLength(3),
        );
        expect(screen.getByText("成果物")).toBeVisible();
        expect(
            document.fonts.add as ReturnType<typeof vi.fn>,
        ).toHaveBeenCalled();
        view.unmount();
        expect(
            document.fonts.delete as ReturnType<typeof vi.fn>,
        ).toHaveBeenCalled();
    });

    it("resumes polling from the job id returned by a 409", async () => {
        commonHandlers([]);
        server.use(
            http.post("http://localhost/api/projects/:projectId/builds", () =>
                HttpResponse.json(
                    {
                        error: {
                            code: "E_BUILD_IN_PROGRESS",
                            message: "busy",
                            detail: { job_id: "job-running" },
                        },
                    },
                    { status: 409 },
                ),
            ),
            http.get(
                "http://localhost/api/projects/:projectId/jobs/job-running",
                () => HttpResponse.json({ status: "running" }),
            ),
        );
        renderBuild();
        await userEvent
            .setup()
            .click(screen.getByRole("button", { name: "フォントを生成" }));
        expect(
            await screen.findByText(
                "別のフォント生成が進行中です。完了を待って結果を表示します。",
            ),
        ).toBeVisible();
    });

    it("links to review when the server reports nothing to build", async () => {
        commonHandlers([]);
        server.use(
            http.post("http://localhost/api/projects/:projectId/builds", () =>
                HttpResponse.json(
                    {
                        error: {
                            code: "E_VALIDATION",
                            message: "invalid",
                            detail: { reason: "nothing_to_build" },
                        },
                    },
                    { status: 422 },
                ),
            ),
        );
        renderBuild();
        await userEvent
            .setup()
            .click(screen.getByRole("button", { name: "フォントを生成" }));
        expect(
            await screen.findByText(
                "採用できる文字がありません。確認画面で文字を採用してから生成してください。",
            ),
        ).toBeVisible();
        expect(
            screen.getByRole("link", { name: "文字の確認へ" }),
        ).toHaveAttribute("href", `/p/${projectId}/review`);
    });

    it("shows QA check ids while keeping the QA report downloadable", async () => {
        commonHandlers([
            artifact("qa-1", "qa_json"),
            artifact("woff-1", "woff2"),
        ]);
        server.use(
            http.get(
                "http://localhost/api/projects/:projectId/jobs/job-1",
                () =>
                    HttpResponse.json({
                        status: "failed",
                        error_code: "E_QA_FAILED",
                    }),
            ),
        );
        renderBuild();
        expect(
            await screen.findByText(
                "生成されたフォントは品質チェックに失敗しました",
            ),
        ).toBeVisible();
        await waitFor(
            () => expect(screen.getByText(/check\/name/)).toBeVisible(),
            { timeout: 3000 },
        );
        expect(
            screen.getAllByRole("button", { name: "ダウンロード" }).length,
        ).toBeGreaterThan(0);
    });

    it("groups two build histories and never places an API URL in the DOM", async () => {
        commonHandlers([
            artifact("new-1", "ttf", "job-new"),
            artifact("old-1", "ttf", "job-old"),
        ]);
        renderBuild();
        await waitFor(() =>
            expect(
                screen
                    .getAllByRole("button")
                    .filter((button) => button.textContent?.includes("· 1")),
            ).toHaveLength(2),
        );
        expect(document.body.innerHTML).not.toContain("/api/projects/");
    });

    it("lists typed characters outside the charset", async () => {
        commonHandlers([artifact("woff-1", "woff2")]);
        renderBuild();
        const textarea = await screen.findByRole("textbox");
        await userEvent.setup().clear(textarea);
        await userEvent.setup().type(textarea, "A?");
        expect(
            await screen.findByText("この文字はフォントに含まれません: ?"),
        ).toBeVisible();
    });

    it("shows a visible error when an artifact download fails", async () => {
        commonHandlers([artifact("ttf-fail", "ttf")]);
        server.use(
            http.get(
                "http://localhost/api/projects/:projectId/artifacts/ttf-fail",
                () =>
                    HttpResponse.json(
                        { error: { code: "E_INTERNAL", message: "failed" } },
                        { status: 500 },
                    ),
            ),
        );
        renderBuild();
        await userEvent
            .setup()
            .click(await screen.findByRole("button", { name: "ダウンロード" }));
        expect(
            await screen.findByText(
                "成果物をダウンロードできませんでした。もう一度お試しください。",
            ),
        ).toBeVisible();
    });
});
