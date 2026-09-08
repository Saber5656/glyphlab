const keyFor = (projectId: string) => `glyphlab:token:${projectId}`;
const tokenPattern = /^glp_[A-Za-z0-9_-]{43}$/;

export function saveToken(projectId: string, token: string): void {
  if (!tokenPattern.test(token)) throw new Error("トークンの形式が正しくありません");
  window.localStorage.setItem(keyFor(projectId), token);
}

export function getToken(projectId: string): string | null {
  return window.localStorage.getItem(keyFor(projectId));
}

export function clearToken(projectId: string): void {
  window.localStorage.removeItem(keyFor(projectId));
}

export function consumeFragmentToken(projectId: string, location = window.location): string | null {
  const match = new URLSearchParams(location.hash.replace(/^#/, "")).get("t");
  if (!match || !tokenPattern.test(match)) return getToken(projectId);
  saveToken(projectId, match);
  window.history.replaceState({}, document.title, `${location.pathname}${location.search}`);
  return match;
}

export function isToken(value: string): boolean { return tokenPattern.test(value); }
