import { beforeEach, expect, it } from "vitest";
import { consumeFragmentToken, getToken } from "./token";

beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState(
        {},
        "",
        "/p/abc#t=glp_1234567890123456789012345678901234567890123",
    );
});
it("moves a fragment token into storage and cleans the URL", () => {
    expect(consumeFragmentToken("abc")).toMatch(/^glp_/);
    expect(getToken("abc")).toMatch(/^glp_/);
    expect(window.location.hash).toBe("");
});

it("keeps a newly created token usable in memory when browser storage is unavailable", async () => {
    const { saveToken, clearToken } = await import("./token");
    const { vi } = await import("vitest");
    const token = `glp_${"z".repeat(43)}`;
    const write = vi
        .spyOn(window.localStorage, "setItem")
        .mockImplementation(() => {
            throw new Error("storage blocked");
        });
    expect(saveToken("no-storage", token)).toBe(false);
    expect(getToken("no-storage")).toBe(token);
    clearToken("no-storage");
    expect(getToken("no-storage")).toBeNull();
    write.mockRestore();
});
