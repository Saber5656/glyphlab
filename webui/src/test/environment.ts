import { builtinEnvironments, type Environment } from "vitest/environments";

// Native fetch/Request require consistent signals and multipart objects. Mixing
// jsdom files with Node 22 FormData hangs body serialization; Node 26 is stricter
// about signal identity. Capture one realm before jsdom installs its DOM globals.
// This affects the test transport only; production uses the browser constructors.
export default {
  ...builtinEnvironments.jsdom,
  async setup(global, options) {
    const native = { AbortController: global.AbortController, AbortSignal: global.AbortSignal, Blob: global.Blob, File: global.File, FormData: global.FormData };
    const environment = await builtinEnvironments.jsdom.setup(global, options);
    Object.assign(global, native);
    return environment;
  },
} satisfies Environment;
