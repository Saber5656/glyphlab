import { afterEach, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "./api";

afterEach(() => vi.restoreAllMocks());
it("normalizes the error envelope", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "E_NOT_FOUND", message: "missing", detail: { x: 1 } } }), { status: 404 }));
  await expect(apiFetch("/projects/x")).rejects.toEqual(expect.objectContaining({ code: "E_NOT_FOUND", status: 404, detail: { x: 1 } }));
});
