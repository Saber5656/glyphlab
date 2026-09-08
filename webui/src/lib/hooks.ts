import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError, uploadWithProgress } from "./api";
import type { components } from "../generated/api";
import type { UploadResponse } from "../generated/types";
export type Job = components["schemas"]["JobResponse"];
const terminal = new Set<Job["status"]>(["succeeded", "failed", "canceled"]);
export function usePollJob(projectId: string, jobId: string | undefined) {
    return useQuery<Job>({
        queryKey: ["job", projectId, jobId],
        queryFn: ({ signal }) =>
            apiFetch<Job>(`/projects/${projectId}/jobs/${jobId}`, {
                projectId,
                signal,
            }),
        enabled: Boolean(jobId),
        refetchInterval: (query) => {
            const status = query.state.data?.status;
            return status && terminal.has(status) ? false : 1000;
        },
        refetchOnWindowFocus: false,
        retry: 1,
    });
}
export function useObjectUrl(blob: Blob | undefined): string | undefined {
    const [url, setUrl] = useState<string>();
    useEffect(() => {
        if (!blob) {
            setUrl(undefined);
            return;
        }
        const next = URL.createObjectURL(blob);
        setUrl(next);
        return () => URL.revokeObjectURL(next);
    }, [blob]);
    return url;
}
export type IngestResult = {
    page_index: number;
    counts: {
        extracted: number;
        empty: number;
        skipped_accepted: number;
        failed: number;
    };
    cells: { warnings?: string[] }[];
};
function ingestResult(value: unknown): IngestResult | undefined {
    if (!value || typeof value !== "object") return;
    const result = value as Partial<IngestResult>;
    if (
        !Number.isInteger(result.page_index) ||
        (result.page_index ?? -1) < 0 ||
        !result.counts ||
        !["extracted", "empty", "skipped_accepted", "failed"].every((key) => {
            const count = result.counts?.[key as keyof IngestResult["counts"]];
            return (
                typeof count === "number" &&
                Number.isInteger(count) &&
                count >= 0
            );
        }) ||
        !Array.isArray(result.cells) ||
        !result.cells.every(
            (cell) =>
                cell &&
                typeof cell === "object" &&
                (!cell.warnings ||
                    (Array.isArray(cell.warnings) &&
                        cell.warnings.every(
                            (warning) => typeof warning === "string",
                        ))),
        )
    )
        return;
    return result as IngestResult;
}
export type UploadItem = {
    id: string;
    file: File;
    state: "waiting" | "uploading" | "processing" | "done" | "error";
    progress: number;
    jobId?: string;
    error?: string;
    deduplicated?: boolean;
    result?: IngestResult;
};
async function readHeader(file: File): Promise<ArrayBuffer> {
    const blob = file.slice(0, 32);
    if (blob.arrayBuffer) return blob.arrayBuffer();
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as ArrayBuffer);
        reader.onerror = () => reject(reader.error);
        reader.readAsArrayBuffer(blob);
    });
}
export async function validateImage(file: File): Promise<string | null> {
    if (file.size > 12 * 1024 * 1024) return "E_IMG_TOO_LARGE";
    try {
        const bytes = new Uint8Array(await readHeader(file));
        const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
        const png = [137, 80, 78, 71, 13, 10, 26, 10].every(
            (byte, index) => bytes[index] === byte,
        );
        const text = String.fromCharCode(...bytes);
        const heic =
            text.slice(4, 8) === "ftyp" &&
            ["heic", "heix", "mif1", "msf1"].includes(text.slice(8, 12));
        return jpeg || png || heic ? null : "E_IMG_FORMAT";
    } catch {
        return "E_IMG_DECODE";
    }
}
const pending = (item: UploadItem) =>
    ["waiting", "uploading", "processing"].includes(item.state);
export function useUploadQueue(projectId: string) {
    const client = useQueryClient();
    const key = ["upload-queue", projectId];
    const queue = useQuery<UploadItem[]>({
        queryKey: key,
        queryFn: () => [],
        initialData: [],
        enabled: false,
        gcTime: 30 * 60 * 1000,
    });
    const items = queue.data;
    const [queueFull, setQueueFull] = useState(false);
    const fullAtPending = useRef<number>();
    const current = useRef<{ id: string; controller: AbortController }>();
    const mounted = useRef(true);
    const validating = useRef(0);
    const update = useCallback(
        (transform: (items: UploadItem[]) => UploadItem[]) =>
            client.setQueryData<UploadItem[]>(
                ["upload-queue", projectId],
                (old) => transform(old ?? []),
            ),
        [client, projectId],
    );
    const change = useCallback(
        (id: string, patch: Partial<UploadItem>) =>
            update((old) =>
                old.map((item) =>
                    item.id === id ? { ...item, ...patch } : item,
                ),
            ),
        [update],
    );
    const active = items.find((item) => item.state === "processing");
    const job = usePollJob(projectId, active?.jobId);
    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
            const request = current.current;
            current.current = undefined;
            request?.controller.abort();
            // A deletion may already have purged this project; do not recreate its cache.
            if (request && client.getQueryData(["upload-queue", projectId]))
                change(request.id, { state: "waiting", progress: 0 });
        };
    }, [change, client, projectId]);
    useEffect(() => {
        if (!active || !job.data || !terminal.has(job.data.status)) return;
        const result =
            job.data.status === "succeeded"
                ? ingestResult(job.data.result)
                : undefined;
        change(
            active.id,
            result
                ? { state: "done", result }
                : {
                      state: "error",
                      error:
                          job.data.error_code ??
                          (job.data.status === "succeeded"
                              ? "E_INTERNAL"
                              : "E_JOB_LOST"),
                  },
        );
        void client.invalidateQueries({ queryKey: ["summary", projectId] });
        void client.invalidateQueries({ queryKey: ["glyphs", projectId] });
    }, [active, job.data, change, client, projectId]);
    useEffect(() => {
        if (current.current || active) return;
        const item = items.find((candidate) => candidate.state === "waiting");
        if (!item) return;
        const controller = new AbortController();
        current.current = { id: item.id, controller };
        change(item.id, { state: "uploading", error: undefined, progress: 0 });
        const live = () =>
            mounted.current && current.current?.controller === controller;
        void uploadWithProgress<UploadResponse>(
            `/projects/${projectId}/uploads`,
            projectId,
            item.file,
            (progress) => {
                if (live()) change(item.id, { progress });
            },
            controller.signal,
        )
            .then((response) => {
                if (!live()) return;
                if (
                    !response ||
                    typeof response.job_id !== "string" ||
                    !response.job_id
                )
                    throw new ApiError(
                        "E_INTERNAL",
                        "Invalid upload response",
                        200,
                    );
                current.current = undefined;
                change(item.id, {
                    state: "processing",
                    jobId: response.job_id,
                    progress: 100,
                    deduplicated: response.deduplicated,
                });
            })
            .catch((error) => {
                if (!live()) return;
                current.current = undefined;
                change(item.id, {
                    state: "error",
                    error:
                        error instanceof ApiError ? error.code : "E_INTERNAL",
                });
            });
    }, [items, active, projectId, change]);
    const busy = items.some(pending);
    useEffect(() => {
        // Keep an oversized-batch warning even if the queue was empty when rejected.
        // Dismiss it only when previously occupied capacity has actually been released.
        const occupied = items.filter(pending).length + validating.current;
        if (
            queueFull &&
            fullAtPending.current !== undefined &&
            occupied < fullAtPending.current
        ) {
            setQueueFull(false);
            fullAtPending.current = undefined;
        }
    }, [items, queueFull]);
    useEffect(() => {
        if (!busy) return;
        const before = (event: BeforeUnloadEvent) => {
            event.preventDefault();
            event.returnValue = "";
        };
        window.addEventListener("beforeunload", before);
        return () => window.removeEventListener("beforeunload", before);
    }, [busy]);
    async function addFiles(files: FileList | File[]) {
        const incoming = Array.from(files);
        if (!incoming.length) return;
        const old = client.getQueryData<UploadItem[]>(key) ?? [];
        if (
            old.filter(pending).length + validating.current + incoming.length >
            6
        ) {
            fullAtPending.current =
                old.filter(pending).length + validating.current;
            setQueueFull(true);
            return;
        }
        setQueueFull(false);
        fullAtPending.current = undefined;
        validating.current += incoming.length;
        const next = await Promise.all(
            incoming.map(async (file) => {
                const error = await validateImage(file);
                return {
                    id: crypto.randomUUID(),
                    file,
                    state: error ? "error" : "waiting",
                    progress: 0,
                    error: error ?? undefined,
                } as UploadItem;
            }),
        );
        validating.current -= incoming.length;
        if (mounted.current) update((old) => [...old, ...next]);
    }
    async function retry(id: string) {
        const old = client.getQueryData<UploadItem[]>(key) ?? [];
        const item = old.find((candidate) => candidate.id === id);
        if (!item || item.state !== "error") return;
        if (old.filter(pending).length + validating.current >= 6) {
            fullAtPending.current =
                old.filter(pending).length + validating.current;
            setQueueFull(true);
            return;
        }
        validating.current++;
        const error = await validateImage(item.file);
        validating.current--;
        if (mounted.current && !error) {
            setQueueFull(false);
            fullAtPending.current = undefined;
        }
        if (mounted.current)
            change(id, {
                state: error ? "error" : "waiting",
                error: error ?? undefined,
                jobId: undefined,
                result: undefined,
                progress: 0,
                deduplicated: false,
            });
    }
    return {
        items,
        addFiles,
        retry,
        busy,
        queueFull,
        pollError: active ? job.error : null,
        retryPoll: job.refetch,
    };
}
