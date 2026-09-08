import { existsSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const input =
    process.env.GLYPHLAB_OPENAPI ?? "../packages/service/openapi.json";
const output = "src/generated/api.d.ts";
if (!existsSync(input)) {
    throw new Error(
        `OpenAPI schema not found: ${input}. Set GLYPHLAB_OPENAPI or prepare the service workspace.`,
    );
}
execFileSync("npx", ["openapi-typescript", input, "-o", output], {
    stdio: "inherit",
});

const serviceDir = process.env.GLYPHLAB_SERVICE_DIR ?? "../packages/service";
const errorCodes = execFileSync(
    "uv",
    [
        "run",
        "--directory",
        serviceDir,
        "python",
        "-m",
        "glyphlab_service.export_openapi",
        "--error-codes",
    ],
    { encoding: "utf8" },
).trim();
JSON.parse(errorCodes);
writeFileSync("src/generated/error-codes.json", `${errorCodes}\n`);
