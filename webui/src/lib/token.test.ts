import { beforeEach, expect, it } from "vitest";
import { consumeFragmentToken, getToken } from "./token";

beforeEach(() => { window.localStorage.clear(); window.history.replaceState({}, "", "/p/abc#t=glp_1234567890123456789012345678901234567890123"); });
it("moves a fragment token into storage and cleans the URL", () => {
  expect(consumeFragmentToken("abc")).toMatch(/^glp_/);
  expect(getToken("abc")).toMatch(/^glp_/);
  expect(window.location.hash).toBe("");
});
