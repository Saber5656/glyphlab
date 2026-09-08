import { expect, it } from "vitest";

it("serializes browser-style multipart files through the native request transport", async () => {
  const body = new FormData();
  body.append("file", new File(["fixture-content"], "page.jpg", { type: "image/jpeg" }));
  const request = new Request("http://localhost/api/upload", { method: "POST", body });
  const serialized = await request.text();
  expect(serialized).toContain('filename="page.jpg"');
  expect(serialized).toContain("fixture-content");
});

it("accepts abort signals from the configured test environment", () => {
  const controller = new AbortController();
  const request = new Request("http://localhost/api/upload", { signal: controller.signal });
  controller.abort();
  expect(request.signal.aborted).toBe(true);
});
