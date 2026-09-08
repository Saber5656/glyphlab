import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError, downloadBlob } from "../lib/api";
import { useObjectUrl, usePollJob } from "../lib/hooks";
import { errorText, t } from "../i18n/ja";
import type { Artifact } from "../generated/types";

export default function Build() {
    const { projectId = "" } = useParams();
    const client = useQueryClient();
    const [jobId, setJobId] = useState<string>();
    const [fontBlob, setFontBlob] = useState<Blob>();
    const [sample, setSample] = useState(t("sample"));
    const job = usePollJob(projectId, jobId);
    const artifacts = useQuery({
        queryKey: ["artifacts", projectId],
        queryFn: () =>
            apiFetch<{ artifacts: Artifact[] }>(
                `/projects/${projectId}/artifacts`,
                { projectId },
            ),
    });
    const build = useMutation({
        mutationFn: () =>
            apiFetch<{ job_id: string }>(`/projects/${projectId}/builds`, {
                method: "POST",
                body: {},
                projectId,
            }),
        onSuccess: (result) => setJobId(result.job_id),
    });
    useEffect(() => {
        if (job.data?.status === "succeeded" || job.data?.status === "failed")
            void client.invalidateQueries({
                queryKey: ["artifacts", projectId],
            });
    }, [job.data?.status, projectId, client]);
    const latest = useMemo(
        () =>
            (artifacts.data?.artifacts ?? [])
                .filter(
                    (artifact) =>
                        artifact.kind === "woff2" &&
                        (!jobId || artifact.job_id === jobId),
                )
                .sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
        [artifacts.data, jobId],
    );
    useEffect(() => {
        if (!latest) return;
        void apiFetch<Blob>(`/projects/${projectId}/artifacts/${latest.id}`, {
            projectId,
            raw: true,
        })
            .then(setFontBlob)
            .catch(() => undefined);
    }, [latest, projectId]);
    const fontUrl = useObjectUrl(fontBlob);
    useEffect(() => {
        if (!fontUrl || typeof FontFace === "undefined" || !document.fonts)
            return;
        let installed = false;
        let disposed = false;
        const face = new FontFace("GlyphlabPreview", `url(${fontUrl})`);
        void face.load().then(() => {
            if (disposed) return;
            document.fonts.add(face);
            installed = true;
        });
        return () => {
            disposed = true;
            if (installed) document.fonts.delete(face);
        };
    }, [fontUrl]);
    async function download(artifact: Artifact) {
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
    }
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
                    disabled={
                        build.isPending ||
                        ["queued", "running"].includes(job.data?.status ?? "")
                    }
                    onClick={() => build.mutate()}
                >
                    {job.data?.status === "running"
                        ? t("generating")
                        : t("build")}
                </button>
            </div>
            {build.error && (
                <p className="notice error">
                    {errorText(
                        build.error instanceof ApiError
                            ? build.error.code
                            : "E_INTERNAL",
                    )}
                </p>
            )}
            {job.data?.status === "failed" && (
                <div className="notice error">
                    <strong>
                        {job.data.error_code === "E_QA_FAILED"
                            ? t("qaFailed")
                            : errorText(job.data.error_code ?? "E_INTERNAL")}
                    </strong>
                    <p>{t("qaFailedAdvice")}</p>
                </div>
            )}
            {latest && (
                <section className="preview card">
                    <h2>{t("preview")}</h2>
                    <textarea
                        value={sample}
                        onChange={(event) => setSample(event.target.value)}
                    />
                    <p
                        className="font-preview"
                        style={
                            fontUrl
                                ? { fontFamily: "GlyphlabPreview" }
                                : undefined
                        }
                    >
                        {sample}
                    </p>
                    <div className="preview-sizes">
                        <span>{t("sizeSmall")}</span>
                        <span>{t("sizeMedium")}</span>
                        <span>{t("sizeLarge")}</span>
                    </div>
                </section>
            )}
            <section className="card">
                <h2>{t("artifacts")}</h2>
                {(artifacts.data?.artifacts ?? []).map((artifact) => (
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
                {!artifacts.data?.artifacts.length && <p>{t("noArtifacts")}</p>}
            </section>
            <details className="card">
                <summary>{t("installGuide")}</summary>
                <p>{t("installText")}</p>
            </details>
            <Link to={`/p/${projectId}/review`}>{t("backReview")}</Link>
        </section>
    );
}
