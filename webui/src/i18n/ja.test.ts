import codes from "../generated/error-codes.json";
import { errorMessages, errorText, t } from "./ja";
import { expect, it } from "vitest";

it("contains every canonical error code", () => { for (const code of codes) expect(errorMessages[code as keyof typeof errorMessages]).toBeTruthy(); });
it("falls back with the code", () => { expect(errorText("E_UNKNOWN")).toContain("E_UNKNOWN"); expect(t("errorFallback", { code: "E_X" })).toContain("E_X"); });
