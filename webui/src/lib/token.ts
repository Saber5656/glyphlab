const keyFor = (projectId: string) => `glyphlab:token:${projectId}`;
const transientTokens = new Map<string, string | null>();
const tokenPattern = /^glp_[A-Za-z0-9_-]{43}$/;
export const TOKEN_CHANGED = "glyphlab:token-changed";
const notify = (projectId: string) =>
    window.dispatchEvent(new CustomEvent(TOKEN_CHANGED, { detail: projectId }));
export function saveToken(projectId: string, token: string): boolean {
    if (!isToken(token)) throw new Error("Invalid access token");
    let persisted = true;
    try {
        window.localStorage.setItem(keyFor(projectId), token);
        transientTokens.delete(projectId);
    } catch {
        transientTokens.set(projectId, token);
        persisted = false;
    }
    notify(projectId);
    return persisted;
}
export function getToken(projectId: string): string | null {
    if (transientTokens.has(projectId))
        return transientTokens.get(projectId) ?? null;
    try {
        const value = window.localStorage.getItem(keyFor(projectId));
        return value && isToken(value) ? value : null;
    } catch {
        return null;
    }
}
export function clearToken(projectId: string): void {
    try {
        window.localStorage.removeItem(keyFor(projectId));
        transientTokens.delete(projectId);
    } catch {
        transientTokens.set(projectId, null);
    }
    notify(projectId);
}
export function consumeFragmentToken(
    projectId: string,
    location = window.location,
): string | null {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    const token = params.get("t");
    if (params.has("t")) {
        // Preserve the router's history index, but never retain an access token in the URL.
        window.history.replaceState(
            window.history.state,
            document.title,
            `${location.pathname}${location.search}`,
        );
    }
    if (token && isToken(token)) saveToken(projectId, token);
    return getToken(projectId);
}
export function isToken(value: string): boolean {
    return tokenPattern.test(value);
}
export function isProjectId(value: string): boolean {
    return /^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i.test(
        value,
    );
}
export function parseProjectLink(
    value: string,
): { projectId: string; token: string } | null {
    try {
        const url = new URL(value, window.location.origin);
        const match = url.pathname.match(/^\/p\/([^/]+)\/?$/);
        const token = new URLSearchParams(url.hash.slice(1)).get("t");
        if (
            !/^https?:$/.test(url.protocol) ||
            !match ||
            !isProjectId(match[1]) ||
            !token ||
            !isToken(token)
        )
            return null;
        return { projectId: match[1].toLowerCase(), token };
    } catch {
        return null;
    }
}
