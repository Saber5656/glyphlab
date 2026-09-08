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
    const [deleted, setDeleted] = useState(false);
    const summary = useQuery({
        queryKey: ["summary", projectId],
        queryFn: () =>
            apiFetch<Summary>(`/projects/${projectId}`, { projectId }),
    });
    const deletion = useMutation({
        mutationFn: () =>
            apiFetch<void>(`/projects/${projectId}`, {
                method: "DELETE",
                projectId,
            }),
        onSuccess: () => {
            clearToken(projectId);
            setDeleted(true);
            client.clear();
            navigate("/");
        },
    });
    if (summary.isLoading) return <p className="loading">{t("loading")}</p>;
    if (summary.error)
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
                    className="text-button danger"
                    onClick={() => {
                        if (window.confirm(t("deleteConfirm")))
                            deletion.mutate();
                    }}
                >
                    {t("deleteNow")}
                </button>
            </div>
            <div className="coverage">
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
                    className={`card checklist-item ${data.counts.accepted + data.counts.auto ? "complete" : ""}`}
                    to={`/p/${projectId}/build`}
                >
                    <span>04</span>
                    <div>
                        <h2>{t("build")}</h2>
                        <p>{t("buildPrompt")}</p>
                    </div>
                </Link>
            </div>
            {deleted && <p className="notice">{t("deleted")}</p>}
        </section>
    );
}
