import { clearToken, getToken } from "./token";
export type ApiErrorShape = { code: string; message: string; detail?: Record<string, unknown> };
export class ApiError extends Error {
  constructor(readonly code: string, message: string, readonly status: number, readonly detail?: Record<string, unknown>) {
    super(message); this.name = "ApiError";
  }
}
type ApiOptions = { method?: string; body?: BodyInit | object | null; projectId?: string; raw?: boolean; signal?: AbortSignal };
const apiUrl = (path: string) => new URL(`/api${path}`, window.location.origin).href;
function headersFor(projectId?: string): Headers {
  const headers = new Headers();
  const token = projectId && getToken(projectId);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}
function envelopeError(payload: unknown, status: number): ApiError {
  if (payload && typeof payload === "object" && "error" in payload) {
    const error = payload.error;
    if (error && typeof error === "object" && "code" in error && typeof error.code === "string" && "message" in error && typeof error.message === "string") {
      const detail = "detail" in error && error.detail && typeof error.detail === "object" && !Array.isArray(error.detail) ? error.detail as Record<string, unknown> : undefined;
      return new ApiError(error.code, error.message, status, detail);
    }
  }
  return new ApiError("E_INTERNAL", "Request failed", status);
}
function invalidateCredentials(status: number, projectId?: string): void {
  if (status === 401 && projectId) clearToken(projectId);
}
async function request(path: string, options: ApiOptions): Promise<Response> {
  const headers = headersFor(options.projectId);
  let body: BodyInit | undefined;
  if (options.body instanceof FormData || options.body instanceof Blob || typeof options.body === "string") body = options.body;
  else if (options.body != null) { headers.set("Content-Type", "application/json"); body = JSON.stringify(options.body); }
  let response: Response;
  try { response = await fetch(apiUrl(path), { method: options.method ?? "GET", headers, body, signal: options.signal }); }
  catch (error) {
    if (error && typeof error === "object" && "name" in error && error.name === "AbortError") throw error;
    throw new ApiError("E_INTERNAL", "Network request failed", 0);
  }
  if (!response.ok) {
    invalidateCredentials(response.status, options.projectId);
    const payload: unknown = await response.json().catch(() => undefined);
    throw envelopeError(payload, response.status);
  }
  return response;
}
export async function apiFetch<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  const response = await request(path, options);
  if (options.raw) return await response.blob() as T;
  if (response.status === 204) return undefined as T;
  try { return await response.json() as T; }
  catch { throw new ApiError("E_INTERNAL", "Invalid response", response.status); }
}
export async function downloadBlob(path: string, projectId: string): Promise<{ blob: Blob; filename?: string }> {
  const response = await request(path, { projectId });
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return { blob: await response.blob(), filename };
}
export function uploadWithProgress<T>(path: string, projectId: string, file: File, onProgress: (percent: number) => void, signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const abort = () => { request.abort(); reject(new DOMException("Upload aborted", "AbortError")); };
    if (signal?.aborted) { abort(); return; }
    request.open("POST", apiUrl(path));
    headersFor(projectId).forEach((value, key) => request.setRequestHeader(key, value));
    signal?.addEventListener("abort", abort, { once: true });
    request.onloadend = () => signal?.removeEventListener("abort", abort);
    request.upload.onprogress = (event) => { if (event.lengthComputable && event.total > 0) onProgress(Math.min(100, Math.round(event.loaded / event.total * 100))); };
    request.onerror = () => reject(new ApiError("E_INTERNAL", "Upload failed", 0));
    request.onabort = () => reject(new DOMException("Upload aborted", "AbortError"));
    request.ontimeout = () => reject(new ApiError("E_INTERNAL", "Upload timed out", 0));
    request.onload = () => {
      let payload: unknown;
      try { payload = JSON.parse(request.responseText); } catch { /* Normalize invalid payloads below. */ }
      if (request.status < 200 || request.status >= 300) {
        invalidateCredentials(request.status, projectId);
        reject(envelopeError(payload, request.status));
      } else if (payload === undefined) reject(new ApiError("E_INTERNAL", "Invalid upload response", request.status));
      else resolve(payload as T);
    };
    const body = new FormData(); body.append("file", file); request.send(body);
  });
}
