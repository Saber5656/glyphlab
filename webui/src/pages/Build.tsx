import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch, downloadBlob } from "../lib/api";
import { usePollJob } from "../lib/hooks";
import { useProjectFont } from "../lib/font";
import { errorText, t } from "../i18n/ja";
import type { GlyphList, Artifact } from "../generated/types";

type ArtifactGroup = {
    id: string;
    jobId: string | null;
    createdAt: string;
    artifacts: Artifact[];
};
type QaReport = {
    findings?: { check_id?: string; severity?: string }[];
};

async function readBlobText(blob: Blob): Promise<string> {
    if (typeof blob.text === "function") return blob.text();
    if (typeof blob.arrayBuffer === "function")
        return new TextDecoder().decode(await blob.arrayBuffer());
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result ?? ""));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(blob);
    });
}

function groupArtifacts(artifacts: Artifact[]): ArtifactGroup[] {
    const groups = new Map<string, ArtifactGroup>();
    for (const artifact of artifacts) {
        const id = artifact.job_id ?? `legacy:${artifact.id}`;
        const current = groups.get(id);
        if (current) {
            current.artifacts.push(artifact);
            if (artifact.created_at > current.createdAt)
                current.createdAt = artifact.created_at;
        } else {
            groups.set(id, {
                id,
                jobId: artifact.job_id,
                createdAt: artifact.created_at,
                artifacts: [artifact],
            });
        }
    }
    return [...groups.values()]
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .slice(0, 3);
}

function codepointFor(char: string): string {
    return `U+${char.codePointAt(0)?.toString(16).toUpperCase().padStart(4, "0")}`;
}

function extractDetail(error: unknown, key: string): string | undefined {
    if (!(error instanceof ApiError)) return undefined;
    const value = error.detail?.[key];
    return typeof value === "string" ? value : undefined;
}

export default function Build() {
    const { projectId = "" } = useParams();
    const client = useQueryClient();
    const [activeGroupId, setActiveGroupId] = useState<string>();
    const [sample, setSample] = useState(t("sample"));
    const [info, setInfo] = useState<string>();
    const [downloadError, setDownloadError] = useState(false);
    const artifacts = useQuery({
        queryKey: ["artifacts", projectId],
        queryFn: () =>
            apiFetch<{ artifacts: Artifact[] }>(
                `/projects/${projectId}/artifacts`,
                { projectId },
            ),
    });
    const groups = useMemo(
        () => groupArtifacts(artifacts.data?.artifacts ?? []),
        [artifacts.data?.artifacts],
    );
    useEffect(() => {
        if (!activeGroupId && groups[0]) setActiveGroupId(groups[0].id);
    }, [activeGroupId, groups]);
    const activeGroup = activeGroupId
        ? groups.find((group) => group.id === activeGroupId)
        : groups[0];
    const activeJobId =
        activeGroup?.jobId ?? (activeGroup ? undefined : activeGroupId);
    const job = usePollJob(projectId, activeJobId);
    const selectedWoff2 = activeGroup?.artifacts
        .filter((artifact) => artifact.kind === "woff2")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
    const font = useProjectFont(projectId, selectedWoff2);
    const glyphs = useQuery({
        queryKey: ["glyphs", projectId],
        queryFn: () =>
            apiFetch<GlyphList>(`/projects/${projectId}/glyphs?limit=300`, {
                projectId,
            }),
    });
    const missingChars = useMemo(() => {
        const statusByCodepoint = new Map(
            (glyphs.data?.glyphs ?? []).map((glyph) => [
                String(glyph.codepoint),
                glyph.status,
            ]),
        );
        return [...new Set([...sample])].filter((char) => {
            if (!char.trim()) return false;
            const status = statusByCodepoint.get(codepointFor(char));
            return !status || status === "missing" || status === "rejected";
        });
    }, [glyphs.data?.glyphs, sample]);
    const build = useMutation({
        mutationFn: () =>
            apiFetch<{ job_id: string }>(`/projects/${projectId}/builds`, {
                method: "POST",
                body: {},
                projectId,
            }),
        onMutate: () => setInfo(undefined),
        onSuccess: (result) => {
            setActiveGroupId(result.job_id);
            setInfo(undefined);
        },
        onError: (error) => {
            const runningJob = extractDetail(error, "job_id");
            if (
                error instanceof ApiError &&
                error.code === "E_BUILD_IN_PROGRESS" &&
                runningJob
            ) {
                setActiveGroupId(runningJob);
                setInfo(t("buildInProgress"));
            } else if (extractDetail(error, "reason") === "nothing_to_build") {
                setInfo(t("nothingToBuild"));
            }
        },
    });
    useEffect(() => {
        if (job.data?.status === "succeeded" || job.data?.status === "failed")
            void client.invalidateQueries({
                queryKey: ["artifacts", projectId],
            });
    }, [client, job.data?.status, projectId]);
    const qaArtifact = activeGroup?.artifacts.find(
        (artifact) => artifact.kind === "qa_json",
    );
    const qaReport = useQuery({
        queryKey: ["qa-report", projectId, qaArtifact?.id],
        enabled:
            job.data?.status === "failed" &&
            job.data.error_code === "E_QA_FAILED" &&
            Boolean(qaArtifact),
        queryFn: async () => {
            const result = await downloadBlob(
                `/projects/${projectId}/artifacts/${qaArtifact!.id}`,
                projectId,
            );
            return JSON.parse(await readBlobText(result.blob)) as QaReport;
        },
    });
    const failedChecks = (qaReport.data?.findings ?? [])
        .filter((finding) => finding.severity === "FAIL")
        .map((finding) => finding.check_id)
        .filter((checkId): checkId is string => Boolean(checkId));
    async function download(artifact: Artifact) {
        setDownloadError(false);
        try {
            const result = await downloadBlob(
                `/projects/${projectId}/artifacts/${artifact.id}`,
                projectId,
            );
            const url = URL.createObjectURL(result.blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = result.filename ?? `${artifact.kind}`;
            anchor.click();
            URL.revokeObjectURL(url);
        } catch {
            setDownloadError(true);
        }
    }
    const busy =
        build.isPending ||
        ["queued", "running"].includes(job.data?.status ?? "");
    return (
        <section>
            <div className="page-heading">
                <div>
                    <p className="eyebrow">04 / 04</p>
                    <h1>{t("build")}</h1>
                    <p>{t("buildDescription")}</p>
                </div>
                <button
                    className="button"
                    disabled={busy}
                    onClick={() => build.mutate()}
                >
                    {job.data?.status === "running"
                        ? t("generating")
                        : t("build")}
                </button>
            </div>
            {(artifacts.error || glyphs.error || job.error || qaReport.error) && <p role="alert" className="notice error">{errorText((artifacts.error || glyphs.error || job.error || qaReport.error) instanceof ApiError ? ((artifacts.error || glyphs.error || job.error || qaReport.error) as ApiError).code : "E_INTERNAL")}</p>}
            {info && <div className="notice">{info}</div>}
            {build.error && !info && (
                <p className="notice error">
                    {errorText(
                        build.error instanceof ApiError
                            ? build.error.code
                            : "E_INTERNAL",
                    )}
                </p>
            )}
            {job.data?.status === "failed" &&
                job.data.error_code === "E_QA_FAILED" && (
                    <div className="notice error">
                        <strong>{t("qaFailed")}</strong>
                        {failedChecks.length > 0 && (
                            <p>
                                {t("qaChecks", {
                                    checks: failedChecks.join(", "),
                                })}
                            </p>
                        )}
                        <p>{t("qaFailedAdvice")}</p>
                    </div>
                )}
            {job.data?.status === "failed" &&
                job.data.error_code !== "E_QA_FAILED" && (
                    <p className="notice error">
                        {errorText(job.data.error_code ?? "E_INTERNAL")}
                    </p>
                )}
            {activeGroup && (
                <section className="preview card">
                    <h2>{t("preview")}</h2>
                    <textarea
                        aria-label={t("preview")}
                        value={sample}
                        onChange={(event) => setSample(event.target.value)}
                    />
                    {missingChars.length > 0 && (
                        <p className="notice">
                            {t("missingGlyphs", {
                                chars: missingChars.join(" "),
                            })}
                        </p>
                    )}
                    {font.loading && <p>{t("fontLoading")}</p>}
                    {font.error && (
                        <p className="notice">{t("fontLoadFailed")}</p>
                    )}
                    {[16, 24, 36].map((size) => (
                        <p
                            key={size}
                            className="font-preview"
                            style={{
                                fontSize: `${size}px`,
                                ...(font.ready
                                    ? { fontFamily: "GlyphlabPreview" }
                                    : {}),
                            }}
                        >
                            {sample}
                        </p>
                    ))}
                </section>
            )}
            <section className="card">
                <h2>{t("artifacts")}</h2>
                {downloadError && (
                    <p className="notice error">{t("downloadFailed")}</p>
                )}
                {(activeGroup?.artifacts ?? []).map((artifact) => (
                    <div className="artifact" key={artifact.id}>
                        <span>{artifact.kind}</span>
                        <small>
                            {new Date(artifact.created_at).toLocaleString(
                                "ja-JP",
                            )}
                        </small>
                        <button
                            className="text-button"
                            onClick={() => void download(artifact)}
                        >
                            {t("download")}
                        </button>
                    </div>
                ))}
                {!activeGroup?.artifacts.length && <p>{t("noArtifacts")}</p>}
            </section>
            {groups.length > 0 && (
                <section className="card">
                    <h2>{t("buildHistory")}</h2>
                    {groups.map((group, index) => (
                        <button
                            className={`text-button ${group.id === activeGroup?.id ? "active" : ""}`}
                            key={group.id}
                            onClick={() => setActiveGroupId(group.id)}
                        >
                            {index === 0
                                ? t("currentBuild")
                                : new Date(group.createdAt).toLocaleString(
                                      "ja-JP",
                                  )}{" "}
                            · {group.artifacts.length}
                        </button>
                    ))}
                </section>
            )}
            <details className="card">
                <summary>{t("installGuide")}</summary>
                <p>{t("installText")}</p>
            </details>
            {info === t("nothingToBuild") && (
                <Link
                    to={`/p/${projectId}/review`}
                    className="button secondary"
                >
                    {t("reviewMissing")}
                </Link>
            )}
            <Link to={`/p/${projectId}/review`}>{t("backReview")}</Link>
        </section>
    );
}
