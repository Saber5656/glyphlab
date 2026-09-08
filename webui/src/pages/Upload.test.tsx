import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Upload from "./Upload";

const { uploadWithProgress } = vi.hoisted(() => ({
    uploadWithProgress: vi.fn(),
}));
vi.mock("../lib/api", () => ({
    ApiError: class ApiError extends Error {
        code = "E_INTERNAL";
    },
    uploadWithProgress,
}));
vi.mock("../lib/hooks", () => ({
    usePollJob: () => ({ data: undefined }),
}));

describe("Upload queue", () => {
    beforeEach(() => {
        uploadWithProgress.mockReset();
        uploadWithProgress.mockResolvedValue({ job_id: "job-1" });
    });

    it("keeps the queued item addressable after the upload state transition", async () => {
        const user = userEvent.setup();
        render(
            <MemoryRouter initialEntries={["/p/project/upload"]}>
                <Routes>
                    <Route path="/p/:projectId/upload" element={<Upload />} />
                </Routes>
            </MemoryRouter>,
        );
        const file = new File(
            [new Uint8Array([0xff, 0xd8, 0xff, 0xd9])],
            "page.jpg",
            { type: "image/jpeg" },
        );
        Object.defineProperty(file, "slice", {
            value: () => ({
                arrayBuffer: async () =>
                    new Uint8Array([0xff, 0xd8, 0xff, 0xd9]).buffer,
            }),
        });
        await user.upload(screen.getByTestId("upload-input"), file);
        await waitFor(() => expect(uploadWithProgress).toHaveBeenCalledOnce());
        expect(await screen.findByText("処理中…")).toBeVisible();
    });
});
