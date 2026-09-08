import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const input = "../packages/service/openapi.json";
const output = "src/generated/api.d.ts";
if (existsSync(input)) {
  execFileSync("npx", ["openapi-typescript", input, "-o", output], { stdio: "inherit" });
} else {
  writeFileSync(output, `// Fallback generated contract; replaced when service/openapi.json is present.\nexport interface paths {}\n`);
}
if (!existsSync("src/generated/error-codes.json")) {
  writeFileSync("src/generated/error-codes.json", JSON.stringify([
    "E_IMG_FORMAT", "E_IMG_TOO_LARGE", "E_REQUEST_TOO_LARGE", "E_IMG_DECODE",
    "E_PAGE_NO_MARKERS", "E_PAGE_AMBIGUOUS", "E_PAGE_UNKNOWN", "E_PAGE_WARPED",
    "E_PAGE_BLURRY", "E_TEMPLATE_MISMATCH", "E_TRACE_UNAVAILABLE", "E_TRACE_TIMEOUT",
    "E_GLYPH_SVG_INVALID", "E_QA_FAILED", "E_NOT_FOUND", "E_RATE_LIMITED",
    "E_QUOTA_EXCEEDED", "E_JOB_LOST", "E_BUILD_IN_PROGRESS", "E_VALIDATION", "E_INTERNAL"
  ], null, 2) + "\n");
}
