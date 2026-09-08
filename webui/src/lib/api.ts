export type ApiErrorShape = { code: string; message: string; detail?: Record<string, unknown> };
export class ApiError extends Error {
  readonly code: string;
  readonly detail: Record<string, unknown> | undefined;
  readonly status: number;
  constructor(code: string, message: string, status: number, detail?: Record<string, unknown>) {
    super(message); this.name = "ApiError"; this.code = code; this.status = status; this.detail = detail;
  }
}

type ApiOptions = {
  method?: string;
  body?: BodyInit | object | null;
  projectId?: string;
  raw?: boolean;
  signal?: AbortSignal;
};

export async function apiFetch<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers();
  let body: BodyInit | undefined;
  if (options.body instanceof FormData || options.body instanceof Blob || typeof options.body === "string") {
    body = options.body;
  } else if (options.body !== undefined && options.body !== null) {
    headers.set("Content-Type", "application/json"); body = JSON.stringify(options.body);
  }
  if (options.projectId) {
    const token = window.localStorage.getItem(`glyphlab:token:${options.projectId}`);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`/api${path}`, { method: options.method ?? "GET", headers, body, signal: options.signal });
  if (!response.ok) {
    let envelope: { error?: ApiErrorShape } = {};
    try { envelope = await response.json() as typeof envelope; } catch { /* server may return an empty body */ }
    const error = envelope.error ?? { code: "E_INTERNAL", message: "request failed" };
    throw new ApiError(error.code, error.message, response.status, error.detail);
  }
  if (options.raw) return await response.blob() as T;
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export async function downloadBlob(path: string, projectId: string): Promise<{ blob: Blob; filename?: string }> {
  const token = window.localStorage.getItem(`glyphlab:token:${projectId}`);
  const response = await fetch(`/api${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new ApiError("E_INTERNAL", "download failed", response.status);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return { blob: await response.blob(), filename };
}

export function uploadWithProgress<T>(path: string, projectId: string, file: File, onProgress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest(); request.open("POST", `/api${path}`);
    const token = window.localStorage.getItem(`glyphlab:token:${projectId}`); if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);
    request.upload.onprogress = (event) => { if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100)); };
    request.onerror = () => reject(new ApiError("E_INTERNAL", "upload failed", 0));
    request.onload = () => { let payload: unknown; try { payload = JSON.parse(request.responseText); } catch { payload = undefined; } if (request.status < 200 || request.status >= 300) { const error = (payload as { error?: ApiErrorShape } | undefined)?.error; reject(new ApiError(error?.code ?? "E_INTERNAL", error?.message ?? "upload failed", request.status, error?.detail)); return; } resolve(payload as T); };
    const body = new FormData(); body.append("file", file); request.send(body);
  });
}
