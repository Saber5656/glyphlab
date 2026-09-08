import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, it } from "vitest";
import Upload from "./Upload";
import { t, errorMessages, errorText } from "../i18n/ja";
const result = {
    page_index: 1,
    counts: { extracted: 4, empty: 2, skipped_accepted: 1, failed: 0 },
    cells: [{ warnings: ["LOW_INK", "LOW_INK"] }],
};
const server = setupServer(
    http.get("http://localhost/api/projects/p", () =>
        HttpResponse.json({
            charset: { drawn: 94 },
            counts: { auto: 4, accepted: 0, rejected: 0, missing: 90 },
        }),
    ),
    http.post("http://localhost/api/projects/p/uploads", () =>
        HttpResponse.json(
            { job_id: "job", deduplicated: true },
            { status: 200 },
        ),
    ),
    http.get("http://localhost/api/projects/p/jobs/job", () =>
        HttpResponse.json({ status: "succeeded", result }),
    ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => {
    cleanup();
    server.resetHandlers();
});
function mount() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    const view = render(
        <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={["/p/p/upload"]}>
                <Routes>
                    <Route path="/p/:projectId/upload" element={<Upload />} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    );
    return { ...view, client };
}
function choose(
    file = new File([new Uint8Array([255, 216, 255, 217])], "page.jpg", {
        type: "image/jpeg",
    }),
) {
    fireEvent.change(screen.getByTestId("upload-input"), {
        target: { files: [file] },
    });
}
it("uses real XHR and job fetch to render localized counts, dedup, warnings and coverage", async () => {
    let summaryRequests = 0;
    server.use(
        http.get("http://localhost/api/projects/p", () => {
            summaryRequests++;
            return HttpResponse.json({
                charset: { drawn: 94 },
                counts: {
                    auto: summaryRequests === 1 ? 0 : 4,
                    accepted: 0,
                    rejected: 0,
                    missing: 90,
                },
            });
        }),
    );
    mount();
    await screen.findByRole("progressbar");
    choose();
    expect(await screen.findByText(t("complete"))).toBeVisible();
    expect(screen.getByText(t("page", { number: 2 }))).toBeVisible();
    expect(
        screen.getByText(
            t("uploadCounts", {
                extracted: 4,
                empty: 2,
                skipped: 1,
                failed: 0,
            }),
        ),
    ).toBeVisible();
    expect(screen.getByText(t("deduplicated"))).toBeVisible();
    expect(screen.getAllByText("インクが薄い")).toHaveLength(1);
    await waitFor(() =>
        expect(screen.getByRole("progressbar")).toHaveAttribute(
            "aria-valuenow",
            "4",
        ),
    );
    expect(screen.getByRole("link", { name: t("openReview") })).toHaveAttribute(
        "href",
        "/p/p/review",
    );
});
it.each(Object.keys(errorMessages))(
    "renders canonical Japanese guidance and technical code for %s",
    async (code) => {
        server.use(
            http.get("http://localhost/api/projects/p/jobs/job", () =>
                HttpResponse.json({ status: "failed", error_code: code }),
            ),
        );
        mount();
        choose();
        expect(await screen.findByText(errorText(code))).toBeVisible();
        expect(screen.getByRole("button", { name: t("retry") })).toBeVisible();
        await userEvent.click(screen.getByText(t("technicalCode")));
        expect(screen.getByText(code)).toBeVisible();
    },
);
it("prechecks reject oversized or zip input, including retry, without upload requests", async () => {
    let posts = 0;
    server.use(
        http.post("http://localhost/api/projects/p/uploads", () => {
            posts++;
            return HttpResponse.json({ job_id: "job" });
        }),
    );
    mount();
    choose(new File([new Uint8Array(13 * 1024 * 1024)], "large.jpg"));
    expect(await screen.findByText(errorText("E_IMG_TOO_LARGE"))).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: t("retry") }));
    choose(new File(["PK\u0003\u0004"], "archive.zip"));
    expect(await screen.findByText(errorText("E_IMG_FORMAT"))).toBeVisible();
    expect(posts).toBe(0);
});
