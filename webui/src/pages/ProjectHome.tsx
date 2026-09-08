import { glyphSvgCache } from "../lib/svgCache";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError, downloadBlob } from "../lib/api";
import { clearToken } from "../lib/token";
import { errorText, t } from "../i18n/ja";
import type { Summary } from "../generated/types";

export default function ProjectHome() {
    const { projectId = "" } = useParams();
    const navigate = useNavigate();
    const client = useQueryClient();
    const [downloadError, setDownloadError] = useState<string>();
    const [downloading, setDownloading] = useState(false);
    const summary = useQuery({
        queryKey: ["summary", projectId],
        queryFn: ({ signal }) =>
            apiFetch<Summary>(`/projects/${projectId}`, { projectId, signal }),
    });
    const deletion = useMutation({
        mutationFn: () =>
            apiFetch<void>(`/projects/${projectId}`, {
                method: "DELETE",
                projectId,
            }),
        onSuccess: () => {
            clearToken(projectId);
            client.removeQueries({
                predicate: (query) => query.queryKey.includes(projectId),
            });
            glyphSvgCache.clear(`${projectId}:`);
            navigate("/", { state: { deleted: true } });
        },
    });
    if (summary.isLoading) return <p className="loading">{t("loading")}</p>;
    if (summary.error && !summary.data)
        return (
            <section className="card">
                <h1>
                    {errorText(
                        summary.error instanceof ApiError
                            ? summary.error.code
                            : "E_INTERNAL",
                    )}
                </h1>
                <Link className="button" to="/">
                    {t("open")}
                </Link>
            </section>
        );
    const data = summary.data!;
    const done = data.counts.auto + data.counts.accepted + data.counts.rejected;
    async function template() {
        setDownloading(true);
        setDownloadError(undefined);
        try {
            const result = await downloadBlob(
                `/projects/${projectId}/template.pdf`,
                projectId,
            );
            const url = URL.createObjectURL(result.blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = result.filename ?? "template.pdf";
            anchor.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            setDownloadError(
                errorText(
                    error instanceof ApiError ? error.code : "E_INTERNAL",
                ),
            );
        } finally {
            setDownloading(false);
        }
    }
    return (
        <section>
            <div className="page-heading">
                <div>
                    <p className="eyebrow">{data.charset.id}</p>
                    <h1>{data.name}</h1>
                    <p>{data.family_name}</p>
                </div>
                <button
                    disabled={deletion.isPending}
                    className="text-button danger"
                    onClick={() => {
                        if (window.confirm(t("deleteConfirm")))
                            deletion.mutate();
                    }}
                >
                    {t("deleteNow")}
                </button>
            </div>
            <p className="notice">
                {t("expires", {
                    date: new Date(data.expires_at).toLocaleString("ja-JP"),
                })}
            </p>
            <div
                className="coverage"
                role="progressbar"
                aria-label={t("upload")}
                aria-valuenow={done}
                aria-valuemin={0}
                aria-valuemax={data.charset.drawn}
            >
                <strong>
                    {done} / {data.charset.drawn}
                </strong>
                <span
                    style={{
                        width: `${Math.min(100, (done / Math.max(1, data.charset.drawn)) * 100)}%`,
                    }}
                />
            </div>
            <div className="checklist">
                <div className="card checklist-item">
                    <span>01</span>
                    <div>
                        <h2>{t("template")}</h2>
                        <p>{t("templateDescription")}</p>
                    </div>
                    <button
                        className="button secondary"
                        disabled={downloading}
                        onClick={() => void template()}
                    >
                        {t("download")}
                    </button>
                </div>
                <Link
                    className={`card checklist-item ${done ? "complete" : ""}`}
                    to={`/p/${projectId}/upload`}
                >
                    <span>02</span>
                    <div>
                        <h2>{t("upload")}</h2>
                        <p>
                            {done
                                ? t("uploadDone", { count: done })
                                : t("uploadPrompt")}
                        </p>
                    </div>
                </Link>
                <Link
                    className={`card checklist-item ${data.counts.accepted ? "complete" : ""}`}
                    to={`/p/${projectId}/review`}
                >
                    <span>03</span>
                    <div>
                        <h2>{t("review")}</h2>
                        <p>
                            {t("acceptedCount", {
                                accepted: data.counts.accepted,
                                auto: data.counts.auto,
                                missing: data.counts.missing,
                            })}
                        </p>
                    </div>
                </Link>
                <Link
                    className="card checklist-item"
                    to={`/p/${projectId}/build`}
                >
                    <span>04</span>
                    <div>
                        <h2>{t("build")}</h2>
                        <p>{t("buildPrompt")}</p>
                    </div>
                </Link>
            </div>
            {downloadError && (
                <p role="alert" className="notice error">
                    {downloadError}
                </p>
            )}
            {deletion.error && (
                <p role="alert" className="notice error">
                    {errorText(
                        deletion.error instanceof ApiError
                            ? deletion.error.code
                            : "E_INTERNAL",
                    )}
                </p>
            )}
        </section>
    );
}
