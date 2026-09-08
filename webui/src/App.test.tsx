import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", () => ({
    apiFetch: vi.fn(),
    ApiError: class ApiError extends Error {
        code = "E_INTERNAL";
    },
    downloadBlob: vi.fn(),
    uploadWithProgress: vi.fn(),
}));
vi.mock("./lib/hooks", () => ({
    usePollJob: () => ({ data: undefined }),
    useObjectUrl: () => undefined,
}));

describe("ProjectLayout token bootstrap", () => {
    beforeEach(() => {
        localStorage.clear();
        window.history.replaceState(
            {},
            "",
            "/#t=glp_1234567890123456789012345678901234567890123",
        );
    });

    it("consumes the fragment before showing the missing-token guard", async () => {
        render(
            <MemoryRouter
                initialEntries={[
                    "/p/00000000-0000-0000-0000-000000000001/upload",
                ]}
            >
                <App />
            </MemoryRouter>,
        );
        await waitFor(() =>
            expect(
                screen.getByRole("heading", { name: "書いてアップロード" }),
            ).toBeVisible(),
        );
        expect(
            screen.queryByText(
                "このリンクを失うとプロジェクトは開けません。ブックマークかメモに保存してください",
            ),
        ).not.toBeInTheDocument();
    });
});
