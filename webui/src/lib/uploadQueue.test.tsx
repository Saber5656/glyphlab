import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterAll, afterEach, beforeAll, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ReactNode } from "react";
import { useUploadQueue, validateImage } from "./hooks";
import { uploadWithProgress, ApiError } from "./api";
vi.mock("./api", async (original) => ({
    ...(await original<typeof import("./api")>()),
    uploadWithProgress: vi.fn(),
}));
const upload = vi.mocked(uploadWithProgress);
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => {
    cleanup();
    server.resetHandlers();
    vi.resetAllMocks();
});
function file(name = "page.jpg", bytes = [255, 216, 255, 217]) {
    return new File([new Uint8Array(bytes)], name);
}
function mount(
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
    const wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    return { ...renderHook(() => useUploadQueue("p"), { wrapper }), client };
}
const result = {
    page_index: 0,
    counts: { extracted: 4, empty: 2, skipped_accepted: 1, failed: 0 },
    cells: [{ warnings: ["LOW_INK"] }],
};
it("validates magic independently of MIME and rejects forged HEIC, zip and oversize", async () => {
    expect(await validateImage(file())).toBeNull();
    expect(
        await validateImage(file("x.png", [137, 80, 78, 71, 13, 10, 26, 10])),
    ).toBeNull();
    expect(
        await validateImage(
            file("x.heic", [
                0,
                0,
                0,
                24,
                ...Array.from("ftypheic").map((x) => x.charCodeAt(0)),
            ]),
        ),
    ).toBeNull();
    expect(
        await validateImage(
            file("x.heic", [
                ...Array.from("ftypheic").map((x) => x.charCodeAt(0)),
            ]),
        ),
    ).toBe("E_IMG_FORMAT");
    expect(await validateImage(file("x.zip", [80, 75, 3, 4]))).toBe(
        "E_IMG_FORMAT",
    );
    expect(
        await validateImage(
            new File([new Uint8Array(13 * 1024 * 1024)], "x.jpg"),
        ),
    ).toBe("E_IMG_TOO_LARGE");
});
it("sequences upload, progress, processing, success and preserves results after navigation", async () => {
    let finish!: (value: unknown) => void;
    let progress!: (value: number) => void;
    upload
        .mockImplementationOnce((_path, _id, _file, onProgress) => {
            progress = onProgress;
            return new Promise((resolve) => {
                finish = resolve;
            });
        })
        .mockResolvedValueOnce({ job_id: "second" });
    server.use(
        http.get("http://localhost/api/projects/p/jobs/first", () =>
            HttpResponse.json({ status: "succeeded", result }),
        ),
        http.get("http://localhost/api/projects/p/jobs/second", () =>
            HttpResponse.json({ status: "running" }),
        ),
    );
    const view = mount();
    await act(() => view.result.current.addFiles([file(), file("second.jpg")]));
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(1));
    act(() => progress(38));
    await waitFor(() => expect(view.result.current.items[0].progress).toBe(38));
    expect(view.result.current.items[1].state).toBe("waiting");
    await act(async () => finish({ job_id: "first", deduplicated: true }));
    await waitFor(() =>
        expect(view.result.current.items[0].state).toBe("done"),
    );
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
    expect(view.result.current.items[0].deduplicated).toBe(true);
    view.unmount();
    const next = mount(view.client);
    expect(next.result.current.items[0].result).toEqual(result);
});
it.each([
    [429, "E_RATE_LIMITED"],
    [409, "E_QUOTA_EXCEEDED"],
])("keeps %i failures distinct and retry posts again", async (status, code) => {
    upload
        .mockRejectedValueOnce(new ApiError(code, "failed", status))
        .mockResolvedValueOnce({ job_id: "job" });
    server.use(
        http.get("http://localhost/api/projects/p/jobs/job", () =>
            HttpResponse.json({ status: "running" }),
        ),
    );
    const view = mount();
    await act(() => view.result.current.addFiles([file()]));
    await waitFor(() => expect(view.result.current.items[0].error).toBe(code));
    await act(() => view.result.current.retry(view.result.current.items[0].id));
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
});
it("does not bypass a failed precheck on retry or exceed six pending files", async () => {
    const view = mount();
    await act(() => view.result.current.addFiles([file("bad.zip", [80, 75])]));
    await waitFor(() => expect(view.result.current.items).toHaveLength(1));
    await act(() => view.result.current.retry(view.result.current.items[0].id));
    expect(upload).not.toHaveBeenCalled();
    upload.mockImplementation(() => new Promise(() => undefined));
    await act(() =>
        view.result.current.addFiles(Array.from({ length: 6 }, () => file())),
    );
    await act(() => view.result.current.addFiles([file()]));
    await waitFor(() => expect(view.result.current.queueFull).toBe(true));
    await waitFor(() => expect(view.result.current.items).toHaveLength(7));
});
it("aborts an inflight upload when leaving and resets it for a future visit", async () => {
    let signal: AbortSignal | undefined;
    upload.mockImplementation((_p, _id, _f, _progress, s) => {
        signal = s;
        return new Promise(() => undefined);
    });
    const view = mount();
    await act(() => view.result.current.addFiles([file()]));
    await waitFor(() => expect(upload).toHaveBeenCalledOnce());
    view.unmount();
    expect(signal?.aborted).toBe(true);
    expect(
        view.client.getQueryData<Array<{ state: string }>>([
            "upload-queue",
            "p",
        ])?.[0].state,
    ).toBe("waiting");
});
it("recovers a failed poll without re-uploading the file", async () => {
    upload.mockResolvedValue({ job_id: "recover" });
    let polls = 0;
    server.use(
        http.get("http://localhost/api/projects/p/jobs/recover", () => {
            polls++;
            return polls <= 2
                ? HttpResponse.json(
                      { error: { code: "E_INTERNAL", message: "temporary" } },
                      { status: 503 },
                  )
                : HttpResponse.json({ status: "succeeded", result });
        }),
    );
    const view = mount();
    await act(() => view.result.current.addFiles([file()]));
    await waitFor(() => expect(view.result.current.pollError).toBeTruthy(), {
        timeout: 3000,
    });
    await act(() => view.result.current.retryPoll());
    await waitFor(() =>
        expect(view.result.current.items[0].state).toBe("done"),
    );
    expect(upload).toHaveBeenCalledOnce();
});

it("clears a full-queue warning only after pending capacity is actually freed", async () => {
    let finish!: (value: unknown) => void;
    upload
        .mockImplementationOnce(
            () =>
                new Promise((resolve) => {
                    finish = resolve;
                }),
        )
        .mockImplementation(() => new Promise(() => undefined));
    server.use(
        http.get("http://localhost/api/projects/p/jobs/completed", () =>
            HttpResponse.json({ status: "succeeded", result }),
        ),
    );
    const view = mount();
    await act(() =>
        view.result.current.addFiles(Array.from({ length: 6 }, () => file())),
    );
    await waitFor(() => expect(upload).toHaveBeenCalledOnce());
    await act(() => view.result.current.addFiles([file("seventh.jpg")]));
    expect(view.result.current.queueFull).toBe(true);
    await act(async () => finish({ job_id: "completed" }));
    await waitFor(() =>
        expect(view.result.current.items[0].state).toBe("done"),
    );
    await waitFor(() => expect(view.result.current.queueFull).toBe(false));
});
it("keeps a rejected seven-file batch visible on an empty queue until a valid add", async () => {
    const view = mount();
    await act(() =>
        view.result.current.addFiles(Array.from({ length: 7 }, () => file())),
    );
    expect(view.result.current.queueFull).toBe(true);
    expect(view.result.current.items).toHaveLength(0);
    view.rerender();
    expect(view.result.current.queueFull).toBe(true);
    upload.mockImplementation(() => new Promise(() => undefined));
    await act(() => view.result.current.addFiles([file()]));
    await waitFor(() => expect(view.result.current.queueFull).toBe(false));
});
