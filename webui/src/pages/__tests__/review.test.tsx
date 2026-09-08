import { beforeAll, afterAll, beforeEach, afterEach, it, expect, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { readFileSync } from "node:fs";
import Review from "../Review";
import { apiFetch } from "../../lib/api";
import { glyphSvgCache } from "../../lib/svgCache";
import type { GlyphResponse, ReviewRequest } from "../../generated/types";

const fixture: GlyphResponse[] = [
  { codepoint: "U+0041", char: "A", status: "auto", warnings: ["LOW_INK"], updated_at: "2026-09-08T00:00:00Z", svg_url: "/api/projects/p/glyphs/U+0041.svg" },
  { codepoint: "U+0042", char: "B", status: "accepted", warnings: [], updated_at: "2026-09-08T00:00:00Z" },
  { codepoint: "U+3042", char: "あ", status: "rejected", warnings: [], updated_at: "2026-09-08T00:00:00Z" },
  { codepoint: "U+30A2", char: "ア", status: "missing", warnings: [], updated_at: "2026-09-08T00:00:00Z" },
  { codepoint: "U+3001", char: "、", status: "auto", warnings: [], updated_at: "2026-09-08T00:00:00Z" },
];
let glyphs: GlyphResponse[];
let calls: ReviewRequest[];
const server = setupServer(
  http.get("http://localhost/api/projects/p", () => HttpResponse.json({ accepted: glyphs.filter(g => g.status === "accepted").length })),
  http.get("http://localhost/api/projects/p/glyphs", () => HttpResponse.json({ glyphs, next_cursor: null })),
  http.get("http://localhost/api/projects/p/glyphs/:cp", ({ request }) => {
    expect(request.headers.get("Authorization")).toBe("Bearer glp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");
    expect(request.url).toContain("U+0041.svg");
    return new HttpResponse('<svg xmlns="http://www.w3.org/2000/svg"/>', { headers: { "Content-Type": "image/svg+xml" } });
  }),
  http.post("http://localhost/api/projects/p/glyphs:review", async ({ request }) => {
    const body = await request.json() as ReviewRequest; calls.push(body);
    glyphs = glyphs.map(g => ({ ...g, status: body.accept?.includes(g.codepoint) ? "accepted" : body.reject?.includes(g.codepoint) ? "rejected" : g.status }));
    return HttpResponse.json({ updated: 1, unchanged: 0, errors: [] });
  }),
);
let interceptedFetch: typeof fetch;
beforeAll(() => { server.listen({ onUnhandledRequest: "error" }); interceptedFetch = globalThis.fetch; });
afterAll(() => server.close());
beforeEach(() => {
  glyphs = structuredClone(fixture); calls = [];
  localStorage.setItem("glyphlab:token:p", "glp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");
  globalThis.fetch = (input, init) => interceptedFetch(typeof input === "string" ? new URL(input, window.location.origin) : input, init);
  URL.createObjectURL = vi.fn(() => "blob:preview"); URL.revokeObjectURL = vi.fn();
});
afterEach(() => { cleanup(); glyphSvgCache.clear(); server.resetHandlers(); vi.restoreAllMocks(); globalThis.fetch = interceptedFetch; });
function SummaryObserver() {
  const summary = useQuery({ queryKey: ["summary", "p"], queryFn: () => apiFetch<{ accepted: number }>("/projects/p", { projectId: "p" }) });
  return <output aria-label="summary-accepted">{summary.data?.accepted}</output>;
}
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><SummaryObserver /><MemoryRouter initialEntries={["/p/p/review"]}><Routes><Route path="/p/:projectId/review" element={<Review />} /></Routes></MemoryRouter></QueryClientProvider>);
  return client;
}
it("renders canonical codepoints, sections, statuses and an authenticated blob image", async () => {
  mount(); await screen.findByRole("button", { name: "A 未確認" });
  for (const name of ["英数", "ひらがな", "カタカナ", "記号"]) expect(screen.getByRole("heading", { name })).toBeVisible();
  expect(screen.getByRole("button", { name: "ア 未取込" })).toBeVisible();
  await waitFor(() => expect(screen.getByRole("img", { name: "A" })).toHaveAttribute("src", "blob:preview"));
  expect(screen.getByTitle("インクが薄い")).toBeVisible();
  expect(screen.getByLabelText("文字の状態集計")).toHaveTextContent("未確認 2");
});
it("uses canonical U+ strings for keyboard review and refreshes the summary", async () => {
  const client = mount(); const invalidate = vi.spyOn(client, "invalidateQueries");
  fireEvent.keyDown(await screen.findByRole("button", { name: "A 未確認" }), { key: "a" });
  await waitFor(() => expect(calls).toEqual([{ accept: ["U+0041"], reject: [] }]));
  await screen.findByRole("button", { name: "A 採用" });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["summary", "p"] });
  fireEvent.keyDown(screen.getByRole("button", { name: "A 採用" }), { key: "r" });
  await screen.findByRole("button", { name: "A 却下" });
});
it("optimistically accepts and rolls back a rejected request", async () => {
  let finish!: () => void;
  server.use(http.post("http://localhost/api/projects/p/glyphs:review", async () => {
    await new Promise<void>(resolve => { finish = resolve; });
    return HttpResponse.json({ error: { code: "E_INTERNAL", message: "failed" } }, { status: 500 });
  }));
  mount(); fireEvent.click(await screen.findByRole("button", { name: "A 未確認" }));
  fireEvent.click(screen.getByRole("button", { name: "A を採用" }));
  await screen.findByRole("button", { name: "A 採用" });
  await waitFor(() => expect(finish).toBeTypeOf("function")); finish();
  await screen.findByRole("alert"); await screen.findByRole("button", { name: "A 未確認" });
});
it.each(["採用", "却下"])("batches checkbox selections into one %s request and clears them", async label => {
  mount(); await screen.findByRole("button", { name: "A 未確認" });
  fireEvent.click(screen.getByRole("checkbox", { name: "複数選択" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "A を選択" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "あ を選択" }));
  fireEvent.click(screen.getByRole("button", { name: `選択した文字を${label}` }));
  await waitFor(() => expect(calls).toHaveLength(1));
  expect(calls[0][label === "採用" ? "accept" : "reject"]).toEqual(["U+0041", "U+3042"]);
  expect(screen.queryByText("2字を選択中")).not.toBeInTheDocument();
});
it("confirms AUTO count, filters by warnings and searches codepoints", async () => {
  mount(); await screen.findByRole("button", { name: "A 未確認" });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.click(screen.getByRole("button", { name: "AUTOをすべて採用" }));
  expect(confirm.mock.calls[0][0]).toContain("2"); expect(calls).toHaveLength(0);
  confirm.mockReturnValue(true); fireEvent.click(screen.getByRole("button", { name: "AUTOをすべて採用" }));
  await waitFor(() => expect(calls[0].accept).toEqual(["U+0041", "U+3001"]));
  fireEvent.click(screen.getByRole("button", { name: "警告あり" }));
  expect(screen.queryByRole("button", { name: "B 採用" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "すべて" }));
  fireEvent.change(screen.getByPlaceholderText("文字・U+コードを検索"), { target: { value: "U+3042" } });
  expect(screen.getByRole("button", { name: "あ 却下" })).toBeVisible();
  expect(screen.queryByRole("button", { name: /A 採用/ })).not.toBeInTheDocument();
});
it("moves focus through missing cells and disables an empty build", async () => {
  glyphs = fixture.map(g => ({ ...g, status: "missing" })); mount();
  const a = await screen.findByRole("button", { name: "A 未取込" }); act(() => a.focus()); fireEvent.keyDown(a, { key: "ArrowRight" });
  expect(screen.getByRole("button", { name: "B 未取込" })).toHaveFocus();
  expect(screen.getByRole("button", { name: "ビルドへ" })).toBeDisabled();
});
it("does not inline untrusted SVG markup", () => {
  expect(readFileSync("src/pages/Review.tsx", "utf8")).not.toContain("dangerouslySetInnerHTML");
});
it("reconciles partial review errors with the server and clears selection with Escape", async () => {
  server.use(http.post("http://localhost/api/projects/p/glyphs:review", () => HttpResponse.json({ updated: 0, unchanged: 0, errors: [{ codepoint: "U+0041", code: "E_VALIDATION" }] })));
  mount(); const a = await screen.findByRole("button", { name: "A 未確認" });
  fireEvent.click(screen.getByRole("checkbox", { name: "複数選択" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "A を選択" }));
  fireEvent.keyDown(a, { key: "Escape" });
  expect(screen.queryByText("1字を選択中")).not.toBeInTheDocument();
  fireEvent.keyDown(a, { key: "a" }); await screen.findByRole("alert");
  await screen.findByRole("button", { name: "A 未確認" });
});
it("loads SVG only when near the viewport and ignores late completion after unmount", async () => {
  let intersect!: IntersectionObserverCallback;
  const disconnect = vi.fn();
  vi.stubGlobal("IntersectionObserver", class { constructor(callback: IntersectionObserverCallback) { intersect = callback; } observe() {} disconnect = disconnect; });
  let finish!: () => void; let requests = 0;
  server.use(http.get("http://localhost/api/projects/p/glyphs/:cp", async () => {
    requests++; await new Promise<void>(resolve => { finish = resolve; }); return new HttpResponse("<svg/>");
  }));
  mount(); await screen.findByRole("button", { name: "A 未確認" }); expect(requests).toBe(0);
  act(() => intersect([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver));
  await waitFor(() => expect(requests).toBe(1)); cleanup(); glyphSvgCache.clear(); finish();
  await waitFor(() => expect(disconnect).toHaveBeenCalled());
  expect(URL.createObjectURL).not.toHaveBeenCalled(); vi.unstubAllGlobals();
});

it("navigates vertically by grid geometry and horizontally by charset order", async () => {
  mount(); const a = await screen.findByRole("button", { name: "A 未確認" });
  const cells = [a, screen.getByRole("button", { name: "B 採用" }), screen.getByRole("button", { name: "あ 却下" }), screen.getByRole("button", { name: "ア 未取込" }), screen.getByRole("button", { name: "、 未確認" })];
  cells.forEach((cell, index) => vi.spyOn(cell, "getBoundingClientRect").mockReturnValue({ x: index % 2 * 100, y: Math.floor(index / 2) * 100, left: index % 2 * 100, top: Math.floor(index / 2) * 100, width: 80, height: 80, right: 0, bottom: 0, toJSON() {} }));
  act(() => a.focus()); fireEvent.keyDown(a, { key: "ArrowDown" }); expect(cells[2]).toHaveFocus();
  fireEvent.keyDown(cells[2], { key: "ArrowUp" }); expect(a).toHaveFocus();
  fireEvent.keyDown(a, { key: "ArrowRight" }); expect(cells[1]).toHaveFocus();
  fireEvent.keyDown(cells[1], { key: "ArrowLeft" }); expect(a).toHaveFocus();
});

it("reflects explicit accept/reject round trips in a summary sharing server state", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "A 未確認" }));
  fireEvent.click(screen.getByRole("button", { name: "A を採用" }));
  await waitFor(() => expect(screen.getByLabelText("summary-accepted")).toHaveTextContent("2"));
  await waitFor(() => expect(screen.getByRole("button", { name: "A を却下" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "A を却下" }));
  await waitFor(() => expect(screen.getByLabelText("summary-accepted")).toHaveTextContent("1"));
  expect(calls[1].reject).toEqual(["U+0041"]);
});

it("keeps the SVG preview when review changes only status and its timestamp", async () => {
  glyphs[0].svg_url = "/api/projects/p/glyphs/U+0041.svg?v=upload-1";
  const load = vi.spyOn(glyphSvgCache, "load");
  server.use(http.post("http://localhost/api/projects/p/glyphs:review", () => {
    glyphs[0] = { ...glyphs[0], status: "accepted", updated_at: "2026-09-08T00:01:00Z" };
    return HttpResponse.json({ updated: 1, unchanged: 0, errors: [] });
  }));
  const client = mount();
  await screen.findByRole("img", { name: "A" });
  fireEvent.keyDown(screen.getByRole("button", { name: "A 未確認" }), { key: "a" });
  await waitFor(() => expect(client.getQueryData<{ glyphs: GlyphResponse[] }>(["glyphs", "p"])?.glyphs[0].updated_at).toBe("2026-09-08T00:01:00Z"));
  await screen.findByRole("button", { name: "A 採用" });
  expect(load).toHaveBeenCalledTimes(1);
  expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
});

it("fetches the new geometry revision even when timestamps match", async () => {
  glyphs[0].svg_url = "/api/projects/p/glyphs/U+0041.svg?v=upload-1";
  const revisions: (string | null)[] = [];
  server.use(http.get("http://localhost/api/projects/p/glyphs/:cp", ({ request }) => {
    revisions.push(new URL(request.url).searchParams.get("v"));
    return new HttpResponse("<svg/>");
  }));
  vi.mocked(URL.createObjectURL).mockReturnValueOnce("blob:first").mockReturnValueOnce("blob:second");
  const client = mount();
  await waitFor(() => expect(screen.getByRole("img", { name: "A" })).toHaveAttribute("src", "blob:first"));
  glyphs[0] = { ...glyphs[0], svg_url: "/api/projects/p/glyphs/U+0041.svg?v=upload-2" };
  await act(() => client.invalidateQueries({ queryKey: ["glyphs", "p"] }));
  await waitFor(() => expect(screen.getByRole("img", { name: "A" })).toHaveAttribute("src", "blob:second"));
  expect(revisions).toEqual(["upload-1", "upload-2"]);
});

it("recovers an initial glyph-list rate limit through an explicit reload", async () => {
  let requests = 0;
  server.use(http.get("http://localhost/api/projects/p/glyphs", () => {
    requests++;
    return requests === 1
      ? HttpResponse.json({ error: { code: "E_RATE_LIMITED", message: "later" } }, { status: 429, headers: { "Retry-After": "1" } })
      : HttpResponse.json({ glyphs, next_cursor: null });
  }));
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("アクセスが集中しています");
  expect(screen.queryByRole("button", { name: "A 未確認" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "文字を再取得" }));
  expect(await screen.findByRole("button", { name: "A 未確認" })).toBeVisible();
  expect(requests).toBe(2);
  expect(screen.queryByRole("button", { name: "文字を再取得" })).not.toBeInTheDocument();
  expect(calls).toEqual([]);
});
