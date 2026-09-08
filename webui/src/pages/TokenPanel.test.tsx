import {
    act,
    cleanup,
    fireEvent,
    render,
    screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TokenPanel } from "./Landing";
import type { Created } from "../generated/types";
import { t } from "../i18n/ja";
const created = {
    project_id: "00000000-0000-0000-0000-000000000001",
    token: `glp_${"a".repeat(43)}`,
} as Created;
afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
});
it("cannot dismiss before five seconds and clears its timer on unmount", async () => {
    vi.useFakeTimers();
    const close = vi.fn();
    const view = render(<TokenPanel created={created} onClose={close} />);
    const button = screen.getByRole("button", { name: t("closeSaved") });
    fireEvent.click(button);
    expect(close).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(4999));
    expect(button).toBeDisabled();
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(close).toHaveBeenCalledOnce();
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
});
it("shows copied only after the clipboard promise succeeds", async () => {
    let finish!: () => void;
    const writeText = vi.fn(
        () =>
            new Promise<void>((resolve) => {
                finish = resolve;
            }),
    );
    Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText },
    });
    render(<TokenPanel created={created} onClose={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: t("copyLink") }));
    expect(screen.queryByText(t("copied"))).not.toBeInTheDocument();
    await act(async () => finish());
    expect(screen.getByText(t("copied"))).toBeVisible();
    expect(writeText).toHaveBeenCalledWith(
        `http://localhost/p/${created.project_id}#t=${created.token}`,
    );
});
it("offers the selectable link when clipboard access is denied", async () => {
    Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    render(<TokenPanel created={created} onClose={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: t("copyLink") }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t("copyFailed"));
    expect(screen.queryByText(t("copied"))).not.toBeInTheDocument();
    expect(screen.getByLabelText(t("sharedLink"))).toHaveValue(
        `http://localhost/p/${created.project_id}#t=${created.token}`,
    );
});
