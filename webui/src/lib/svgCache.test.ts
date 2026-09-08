import { it, expect, vi } from "vitest";
import { BlobUrlCache } from "./svgCache";
it("touches cache hits and revokes evicted URLs and all remaining URLs on clear", async () => {
  let id = 0;
  URL.createObjectURL = vi.fn(() => `blob:${++id}`);
  URL.revokeObjectURL = vi.fn();
  const cache = new BlobUrlCache(2);
  const fetchBlob = vi.fn(async () => new Blob(["svg"]));
  expect(await cache.load("a", fetchBlob)).toBe("blob:1");
  await cache.load("b", fetchBlob);
  await cache.load("a", fetchBlob);
  await cache.load("c", fetchBlob);
  expect(fetchBlob).toHaveBeenCalledTimes(3);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:2");
  cache.clear();
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(3);
});
it("deduplicates requests, caps concurrency and discards a load cleared before completion", async () => {
  URL.createObjectURL = vi.fn(() => "blob:new"); URL.revokeObjectURL = vi.fn();
  const cache = new BlobUrlCache(350, 1);
  let finish!: (blob: Blob) => void;
  const first = vi.fn(() => new Promise<Blob>(resolve => { finish = resolve; }));
  const next = vi.fn(async () => new Blob());
  const a = cache.load("p:a", first); const duplicate = cache.load("p:a", first);
  const b = cache.load("p:b", next);
  await Promise.resolve(); expect(next).not.toHaveBeenCalled();
  cache.clear("p:"); finish(new Blob());
  expect(await a).toBeUndefined(); expect(await duplicate).toBeUndefined(); expect(await b).toBeUndefined();
  expect(first).toHaveBeenCalledTimes(1); expect(URL.createObjectURL).not.toHaveBeenCalled();
});
it("enforces the production 350-entry limit and six active requests", async () => {
  let id = 0; URL.createObjectURL = vi.fn(() => `blob:${++id}`); URL.revokeObjectURL = vi.fn();
  const cache = new BlobUrlCache();
  for (let i = 0; i < 351; i++) await cache.load(String(i), async () => new Blob());
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1); expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  cache.clear(); expect(URL.revokeObjectURL).toHaveBeenCalledTimes(351);
  let active = 0; let maximum = 0;
  const pending: (() => void)[] = [];
  const promises = Array.from({ length: 12 }, (_, i) => cache.load(String(i), async () => {
    active++; maximum = Math.max(maximum, active);
    await new Promise<void>(resolve => pending.push(resolve)); active--; return new Blob();
  }));
  expect(active).toBe(6);
  for (let batch = 0; batch < 2; batch++) { pending.splice(0).forEach(resolve => resolve()); await new Promise(resolve => setTimeout(resolve, 0)); }
  await Promise.all(promises); expect(maximum).toBe(6); cache.clear();
});
