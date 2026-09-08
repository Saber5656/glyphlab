import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "../lib/api";
import { useUploadQueue } from "../lib/hooks";
import { errorText, t, warningText } from "../i18n/ja";
import type { Summary } from "../generated/types";
export default function Upload() {
    const { projectId = "" } = useParams();
    const queue = useUploadQueue(projectId);
    const [drag, setDrag] = useState(false);
    const input = useRef<HTMLInputElement>(null);
    const summary = useQuery({
        queryKey: ["summary", projectId],
        queryFn: ({ signal }) =>
            apiFetch<Summary>(`/projects/${projectId}`, { projectId, signal }),
    });
    const data = summary.data;
    const done = data
        ? data.counts.auto + data.counts.accepted + data.counts.rejected
        : 0;
    const drop = (event: DragEvent) => {
        event.preventDefault();
        setDrag(false);
        void queue.addFiles(event.dataTransfer.files);
    };
    return (
        <section>
            <div className="page-heading">
                <div>
                    <p className="eyebrow">02 / 04</p>
                    <h1>{t("upload")}</h1>
                    <p>{t("uploadDescription")}</p>
                </div>
            </div>
            {data && (
                <>
                    <p>{t("uploadTotal", { count: data.charset.drawn })}</p>
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
                </>
            )}
            {summary.error && !summary.data && (
                <p role="alert">
                    {errorText(
                        summary.error instanceof ApiError
                            ? summary.error.code
                            : "E_INTERNAL",
                    )}
                </p>
            )}
            <div
                className={`dropzone ${drag ? "active" : ""}`}
                onDragOver={(event) => {
                    event.preventDefault();
                    setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={drop}
            >
                <input
                    ref={input}
                    data-testid="upload-input"
                    aria-label={t("chooseImage")}
                    hidden
                    type="file"
                    multiple
                    accept="image/jpeg,image/png,image/heic"
                    onChange={(event: ChangeEvent<HTMLInputElement>) => {
                        if (event.target.files)
                            void queue.addFiles(event.target.files);
                        event.target.value = "";
                    }}
                />
                <strong>{t("dropImage")}</strong>
                <button
                    className="text-button"
                    onClick={() => input.current?.click()}
                >
                    {t("chooseImage")}
                </button>
            </div>
            {queue.queueFull && (
                <p role="alert" className="notice error">
                    {t("queueFull")}
                </p>
            )}
            {queue.pollError && (
                <p role="alert" className="notice error">
                    {errorText(
                        queue.pollError instanceof ApiError
                            ? queue.pollError.code
                            : "E_INTERNAL",
                    )}{" "}
                    <button onClick={() => void queue.retryPoll()}>
                        {t("pollRetry")}
                    </button>
                </p>
            )}
            <div className="upload-list">
                {queue.items.map((item) => (
                    <article className="card upload-item" key={item.id}>
                        <div>
                            <strong>{item.file.name}</strong>
                            <small aria-live="polite">
                                {item.state === "processing"
                                    ? t("processing")
                                    : item.state === "uploading"
                                      ? t("uploadProgress", {
                                            percent: item.progress,
                                        })
                                      : item.state === "done"
                                        ? t("complete")
                                        : item.state === "error"
                                          ? errorText(
                                                item.error ?? "E_INTERNAL",
                                            )
                                          : t("waiting")}
                            </small>
                            {item.deduplicated && (
                                <p className="notice">{t("deduplicated")}</p>
                            )}
                            {item.state === "error" && (
                                <>
                                    <details>
                                        <summary>{t("technicalCode")}</summary>
                                        <code>{item.error}</code>
                                    </details>
                                    <button
                                        className="text-button"
                                        onClick={() =>
                                            void queue.retry(item.id)
                                        }
                                    >
                                        {t("retry")}
                                    </button>
                                </>
                            )}
                        </div>
                        {item.state === "done" && item.result && (
                            <div className="result">
                                <span>
                                    {t("page", {
                                        number: item.result.page_index + 1,
                                    })}
                                </span>
                                <span>
                                    {t("uploadCounts", {
                                        extracted: item.result.counts.extracted,
                                        empty: item.result.counts.empty,
                                        skipped:
                                            item.result.counts.skipped_accepted,
                                        failed: item.result.counts.failed,
                                    })}
                                </span>
                                {Array.from(
                                    new Set(
                                        item.result.cells.flatMap(
                                            (cell) => cell.warnings ?? [],
                                        ),
                                    ),
                                ).map((code) => (
                                    <span
                                        className="chip"
                                        title={warningText(code)}
                                        key={code}
                                    >
                                        {warningText(code)}
                                    </span>
                                ))}
                                <Link to={`/p/${projectId}/review`}>
                                    {t("openReview")}
                                </Link>
                            </div>
                        )}
                    </article>
                ))}
            </div>
        </section>
    );
}
