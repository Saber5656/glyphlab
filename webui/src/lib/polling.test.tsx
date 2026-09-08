import { act, cleanup, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { usePollJob } from "./hooks";
import { apiFetch } from "./api";
vi.mock("./api", () => ({
    apiFetch: vi.fn(),
    uploadWithProgress: vi.fn(),
    ApiError: class extends Error {},
}));
afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.resetAllMocks();
});
function mount() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    return renderHook(() => usePollJob("p", "job"), { wrapper });
}
it.each(["succeeded", "failed", "canceled"] as const)(
    "stops 1 Hz polling after %s",
    async (status) => {
        vi.useFakeTimers();
        vi.mocked(apiFetch)
            .mockResolvedValueOnce({ status: "running" })
            .mockResolvedValue({ status });
        const view = mount();
        await act(() => vi.advanceTimersByTimeAsync(10));
        expect(apiFetch).toHaveBeenCalledTimes(1);
        await act(() => vi.advanceTimersByTimeAsync(1000));
        expect(apiFetch).toHaveBeenCalledTimes(2);
        await act(() => vi.advanceTimersByTimeAsync(5000));
        expect(apiFetch).toHaveBeenCalledTimes(2);
        view.unmount();
        await act(() => vi.advanceTimersByTimeAsync(1));
        expect(vi.getTimerCount()).toBe(0);
    },
);
it("aborts a pending poll and leaves no interval after unmount", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.mocked(apiFetch).mockImplementation((_path, options) => {
        signal = options?.signal;
        return new Promise(() => undefined);
    });
    const view = mount();
    expect(signal?.aborted).toBe(false);
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(apiFetch).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
});
