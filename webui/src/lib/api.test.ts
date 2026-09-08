import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { apiFetch, downloadBlob } from "./api";
import { consumeFragmentToken, getToken, saveToken } from "./token";
const token = `glp_${"a".repeat(43)}`;
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/"); });
afterEach(() => vi.unstubAllGlobals());
it("uses an absolute same-origin URL and sends credentials only in the header", async () => {
  saveToken("p", token);
  const fetcher = vi.fn().mockResolvedValue(new Response('{"ok":true}'));
  vi.stubGlobal("fetch", fetcher);
  await apiFetch("/projects/p", { projectId: "p" });
  expect(String(fetcher.mock.calls[0][0])).toBe("http://localhost/api/projects/p");
  expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe(`Bearer ${token}`);
});
it("normalizes download error envelopes with status and detail", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({error: {code: "E_RATE_LIMITED", message: "later", detail: {retry_after: 8}}}), {status: 429})));
  await expect(downloadBlob("/projects/p/template.pdf", "p")).rejects.toMatchObject({code:"E_RATE_LIMITED", status:429, detail:{retry_after:8}});
});
it("normalizes network failures but preserves AbortError", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
  await expect(apiFetch("/meta")).rejects.toMatchObject({code:"E_INTERNAL",status:0});
  const abort = new DOMException("aborted", "AbortError");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
  await expect(apiFetch("/meta")).rejects.toBe(abort);
});
it("rejects malformed error envelopes with a stable internal error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"error":"bad"}', {status:502})));
  await expect(apiFetch("/meta")).rejects.toMatchObject({code:"E_INTERNAL",status:502});
});
it("does not use corrupted stored tokens and always scrubs token fragments", () => {
  localStorage.setItem("glyphlab:token:p", "broken");
  expect(getToken("p")).toBeNull();
  window.history.replaceState({}, "", "/p/p?view=1#t=invalid");
  consumeFragmentToken("p");
  expect(window.location.href).toBe("http://localhost/p/p?view=1");
});
it("saves valid fragment without putting it into history state", () => {
  window.history.replaceState({idx:2}, "", `/p/p#t=${token}`);
  expect(consumeFragmentToken("p")).toBe(token);
  expect(window.location.hash).toBe("");
  expect(window.history.state).toEqual({idx:2});
});

it("clears failed credentials on 401 but preserves a valid token on a missing subresource", async () => {
  saveToken("p", token);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"error":{"code":"E_NOT_FOUND","message":"missing"}}', {status:404})));
  await expect(apiFetch("/projects/p/jobs/missing",{projectId:"p"})).rejects.toMatchObject({status:404,code:"E_NOT_FOUND"});expect(getToken("p")).toBe(token);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", {status:401})));
  await expect(apiFetch("/projects/p",{projectId:"p"})).rejects.toMatchObject({status:401});expect(getToken("p")).toBeNull();
});

it("retains Retry-After for callers to schedule safe retries", async () => {
 vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response('{"error":{"code":"E_RATE_LIMITED","message":"later"}}',{status:429,headers:{"Retry-After":"12"}})));
 await expect(apiFetch("/meta")).rejects.toMatchObject({code:"E_RATE_LIMITED",retryAfter:12});
});
