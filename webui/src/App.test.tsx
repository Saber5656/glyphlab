import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, it } from "vitest";
import App from "./App";
import { t } from "./i18n/ja";
const id = "00000000-0000-0000-0000-000000000001";
const server = setupServer(
    http.get(`http://localhost/api/projects/${id}`, () =>
        HttpResponse.json({
            project_id: id,
            name: "Project",
            family_name: "Font",
            charset: { id: "ascii", drawn: 94 },
            counts: { auto: 0, accepted: 0, rejected: 0, missing: 94 },
            expires_at: "2099-01-01",
        }),
    ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => {
    cleanup();
    localStorage.clear();
    window.history.replaceState({}, "", "/");
    server.resetHandlers();
});
function mount() {
    return render(
        <QueryClientProvider
            client={
                new QueryClient({
                    defaultOptions: { queries: { retry: false } },
                })
            }
        >
            <MemoryRouter initialEntries={[`/p/${id}/upload`]}>
                <App />
            </MemoryRouter>
        </QueryClientProvider>,
    );
}
it("consumes the fragment before mounting authenticated child queries", async () => {
    const token = `glp_${"a".repeat(43)}`;
    window.history.replaceState({}, "", `/p/${id}/upload#t=${token}`);
    mount();
    expect(
        await screen.findByRole("heading", { name: t("upload") }),
    ).toBeVisible();
    expect(window.location.hash).toBe("");
    expect(localStorage.getItem(`glyphlab:token:${id}`)).toBe(token);
    expect(screen.queryByText(t("tokenNeeded"))).not.toBeInTheDocument();
});
it("does not mount upload or poll jobs when the token is missing", () => {
    mount();
    expect(screen.getByLabelText(t("separateToken"))).toBeVisible();
    expect(
        screen.queryByRole("heading", { name: t("upload") }),
    ).not.toBeInTheDocument();
});
