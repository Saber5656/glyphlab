import { builtinEnvironments, type Environment } from "vitest/environments";

// Native fetch and Request require signals from Node's realm (strict in Node 26).
// Capture these before jsdom installs its DOM globals; production still uses browsers.
export default {
  ...builtinEnvironments.jsdom,
  async setup(global, options) {
    const native = { AbortController: global.AbortController, AbortSignal: global.AbortSignal };
    const environment = await builtinEnvironments.jsdom.setup(global, options);
    Object.assign(global, native);
    return environment;
  },
} satisfies Environment;
