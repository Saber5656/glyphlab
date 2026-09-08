import { expect, test } from "@playwright/test";

// Opt-in diagnostics exercise; deliberately fails without creating project data.
test("failure artifacts are retained", async ({ page }) => {
    await page.goto("/");
    await expect(
        page.getByRole("button", { name: "作成する", exact: true }),
    ).toBeVisible();
    expect(
        false,
        "Intentional E2E_FAILURE_PROBE to verify trace/video retention",
    ).toBe(true);
});
