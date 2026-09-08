import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./api";

export type Job = { status: "queued" | "running" | "succeeded" | "failed" | "canceled"; error_code?: string; result?: unknown };
const terminal = new Set<Job["status"]>(["succeeded", "failed", "canceled"]);

export function usePollJob(projectId: string, jobId: string | undefined) {
  return useQuery<Job>({
    queryKey: ["job", projectId, jobId],
    queryFn: () => apiFetch<Job>(`/projects/${projectId}/jobs/${jobId}`, { projectId }),
    enabled: Boolean(jobId), refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminal.has(status) ? false : 1000;
    }, refetchOnWindowFocus: false, retry: 1,
  });
}

export function useObjectUrl(blob: Blob | undefined): string | undefined {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    if (!blob) { setUrl(undefined); return; }
    const next = URL.createObjectURL(blob); setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [blob]);
  return url;
}

