import { readFileSync } from "node:fs";
import ts from "typescript";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
    afterAll,
    afterEach,
    beforeAll,
    beforeEach,
    expect,
    it,
    vi,
} from "vitest";
import App from "../App";
import { getToken, saveToken } from "../lib/token";
import { t, errorText } from "../i18n/ja";
const id = "00000000-0000-0000-0000-000000000001",
    token = `glp_${"a".repeat(43)}`;
const summary = {
    project_id: id,
    name: "My Project",
    family_name: "My Font",
    charset: { id: "ascii", drawn: 94, encoded: 95, pages: 2 },
    counts: { auto: 3, accepted: 2, rejected: 1, missing: 88 },
    expires_at: "2099-01-01T00:00:00Z",
    template_pages: 2,
};
const server = setupServer(
    http.get("http://localhost/api/meta", () =>
        HttpResponse.json({
            charsets: [{ id: "ascii", drawn: 94, encoded: 95, pages: 2 }],
            retention_days: 3,
            version: "1",
        }),
    ),
    http.get(`http://localhost/api/projects/${id}`, () =>
        HttpResponse.json(summary),
    ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, "", "/");
});
afterEach(() => {
    cleanup();
    server.resetHandlers();
    vi.restoreAllMocks();
});
function mount(path = "/") {
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    });
    const view = render(
        <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={[path]}>
                <App />
            </MemoryRouter>
        </QueryClientProvider>,
    );
    return { ...view, client };
}
it("loads real metadata and creates a project with normalized input", async () => {
    const user = userEvent.setup();
    let body: unknown;
    server.use(
        http.post("http://localhost/api/projects", async ({ request }) => {
            body = await request.json();
            return HttpResponse.json(
                { ...summary, token, retention_days: 3 },
                { status: 201 },
            );
        }),
    );
    mount();
    expect(await screen.findByText(t("retention", { days: 3 }))).toBeVisible();
    await user.type(screen.getByLabelText(t("name")), "Cafe\u0301");
    await user.type(screen.getByLabelText(t("familyName")), "My Font");
    await user.click(screen.getByRole("button", { name: t("submit") }));
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(body).toEqual({
        name: "Café",
        family_name: "My Font",
        charset_id: "ascii",
    });
    expect(getToken(id)).toBe(token);
    expect(
        screen.getByRole("button", { name: t("closeSaved") }),
    ).toBeDisabled();
    expect(screen.getByText(t("tokenAutosaved"))).toBeVisible();
});
it("metadata failure has retry and no fabricated retention or selectable charset", async () => {
    server.use(
        http.get("http://localhost/api/meta", () =>
            HttpResponse.json(
                { error: { code: "E_INTERNAL", message: "down" } },
                { status: 503 },
            ),
        ),
    );
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(
        errorText("E_INTERNAL"),
    );
    expect(screen.getByRole("button", { name: t("submit") })).toBeDisabled();
    expect(
        screen.queryByText(t("retention", { days: 14 })),
    ).not.toBeInTheDocument();
    server.resetHandlers();
    await userEvent.click(screen.getByRole("button", { name: t("retry") }));
    expect(await screen.findByText(t("retention", { days: 3 }))).toBeVisible();
});
it("rejects malformed UUID links without storing credentials", async () => {
    mount();
    await userEvent.type(
        screen.getByLabelText(t("sharedLink")),
        `http://localhost/p/${"-".repeat(36)}#t=${token}`,
    );
    await userEvent.click(
        screen.getByRole("button", { name: t("openButton") }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
        t("linkInvalid"),
    );
    expect(getToken("-".repeat(36))).toBeNull();
});
it("offers token input for absent or expired credentials and recovers without reloading", async () => {
    server.use(
        http.get(`http://localhost/api/projects/${id}`, ({ request }) =>
            request.headers.get("authorization") === `Bearer ${token}`
                ? HttpResponse.json(summary)
                : HttpResponse.json(
                      { error: { code: "E_NOT_FOUND", message: "missing" } },
                      { status: 404 },
                  ),
        ),
    );
    saveToken(id, `glp_${"b".repeat(43)}`);
    mount(`/p/${id}`);
    const field = await screen.findByLabelText(t("separateToken"));
    await userEvent.type(field, token);
    await userEvent.click(
        screen.getByRole("button", { name: t("openButton") }),
    );
    expect(
        await screen.findByRole("heading", { name: summary.name }),
    ).toBeVisible();
});
it("deletes only this project's cached data and carries the deletion toast home", async () => {
    server.use(
        http.delete(
            `http://localhost/api/projects/${id}`,
            () => new HttpResponse(null, { status: 204 }),
        ),
    );
    saveToken(id, token);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { client } = mount(`/p/${id}`);
    client.setQueryData(["summary", "other"], { name: "preserved" });
    await userEvent.click(
        await screen.findByRole("button", { name: t("deleteNow") }),
    );
    expect(await screen.findByText(t("deleted"))).toBeVisible();
    expect(getToken(id)).toBeNull();
    expect(client.getQueryData(["summary", "other"])).toEqual({
        name: "preserved",
    });
    expect(client.getQueryData(["summary", id])).toBeUndefined();
});
it("shows template errors instead of creating an unhandled rejection", async () => {
    server.use(
        http.get(`http://localhost/api/projects/${id}/template.pdf`, () =>
            HttpResponse.json(
                { error: { code: "E_RATE_LIMITED", message: "later" } },
                { status: 429 },
            ),
        ),
    );
    saveToken(id, token);
    mount(`/p/${id}`);
    await userEvent.click(
        await screen.findByRole("button", { name: t("download") }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
        errorText("E_RATE_LIMITED"),
    );
});
it("canceling deletion keeps the project and credentials", async () => {
    let deletes = 0;
    server.use(
        http.delete(`http://localhost/api/projects/${id}`, () => {
            deletes++;
            return new HttpResponse(null, { status: 204 });
        }),
    );
    saveToken(id, token);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mount(`/p/${id}`);
    await userEvent.click(
        await screen.findByRole("button", { name: t("deleteNow") }),
    );
    expect(deletes).toBe(0);
    expect(getToken(id)).toBe(token);
    expect(screen.getByRole("heading", { name: summary.name })).toBeVisible();
});
it("rejects invalid name and non-ASCII family before project creation", async () => {
    let posts = 0;
    server.use(
        http.post("http://localhost/api/projects", () => {
            posts++;
            return HttpResponse.json({});
        }),
    );
    mount();
    await screen.findByText(t("retention", { days: 3 }));
    await userEvent.type(screen.getByLabelText(t("name")), " leading");
    await userEvent.type(screen.getByLabelText(t("familyName")), "日本語");
    expect(screen.getByLabelText(t("name"))).toHaveAttribute(
        "aria-invalid",
        "true",
    );
    expect(screen.getByLabelText(t("familyName"))).toHaveAttribute(
        "aria-invalid",
        "true",
    );
    expect(screen.getByRole("button", { name: t("submit") })).toBeDisabled();
    expect(posts).toBe(0);
    expect(screen.getByText(t("familyHelp"))).toBeVisible();
});

it("validates fields during editing without initial error noise and enables valid submission", async () => {
    mount();
    await screen.findByText(t("retention", { days: 3 }));
    const name = screen.getByLabelText(t("name"));
    const family = screen.getByLabelText(t("familyName"));
    const submit = screen.getByRole("button", { name: t("submit") });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(name).not.toHaveAttribute("aria-invalid", "true");
    expect(submit).toBeDisabled();
    await userEvent.type(name, " leading");
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(t("nameInvalid"));
    await userEvent.clear(name);
    await userEvent.type(name, "Café");
    await userEvent.type(family, "My Font");
    expect(name).toHaveAttribute("aria-invalid", "false");
    expect(family).toHaveAttribute("aria-invalid", "false");
    expect(submit).toBeEnabled();
    await userEvent.clear(family);
    expect(family).toHaveAttribute("aria-invalid", "true");
    expect(submit).toBeDisabled();
});
it("centralizes static page copy including ASCII JSX text", () => {
    for (const filename of ["Landing.tsx", "ProjectHome.tsx", "Upload.tsx"]) {
        const source = readFileSync(new URL(filename, import.meta.url), "utf8");
        const tree = ts.createSourceFile(
            filename,
            source,
            ts.ScriptTarget.Latest,
            true,
            ts.ScriptKind.TSX,
        );
        const literals: string[] = [];
        function visit(node: ts.Node) {
            if (ts.isJsxText(node) && node.text.trim()) {
                const text = node.text.trim();
                // Numbered checklist steps and count separators are structural notation.
                if (!/^[0-9\s/]+$/.test(text)) literals.push(text);
            }
            ts.forEachChild(node, visit);
        }
        visit(tree);
        expect(literals, filename).toEqual([]);
    }
});
