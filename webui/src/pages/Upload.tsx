import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, uploadWithProgress } from "../lib/api";
import { usePollJob } from "../lib/hooks";
import { errorText, t, warningText } from "../i18n/ja";

type Item = {
    id: string;
    file: File;
    state: "waiting" | "uploading" | "processing" | "done" | "error";
    progress: number;
    jobId?: string;
    error?: string;
    result?: {
        page_index: number;
        counts?: Record<string, number>;
        cells?: { warnings?: string[] }[];
    };
};
const ACCEPT = ["image/jpeg", "image/png", "image/heic"];
async function validImage(file: File): Promise<string | null> {
    if (file.size > 12 * 1024 * 1024) return t("imageTooLarge");
    const bytes = new Uint8Array(await file.slice(0, 32).arrayBuffer());
    const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
    const png = [137, 80, 78, 71, 13, 10, 26, 10].every(
        (value, index) => bytes[index] === value,
    );
    const text = new TextDecoder().decode(bytes);
    if (!jpeg && !png && !text.includes("ftyp")) return t("invalidImage");
    return null;
}
export default function Upload() {
    const { projectId = "" } = useParams();
    const [items, setItems] = useState<Item[]>([]);
    const [drag, setDrag] = useState(false);
    const running = useRef(false);
    const input = useRef<HTMLInputElement>(null);
    const [active, setActive] = useState<string>();
    const job = usePollJob(projectId, active);
    useEffect(() => {
        if (!active || !job.data) return;
        if (job.data.status === "succeeded") {
            setItems((old) =>
                old.map((item) =>
                    item.jobId === active
                        ? {
                              ...item,
                              state: "done",
                              result: job.data?.result as Item["result"],
                          }
                        : item,
                ),
            );
            setActive(undefined);
            running.current = false;
        } else if (["failed", "canceled"].includes(job.data.status)) {
            setItems((old) =>
                old.map((item) =>
                    item.jobId === active
                        ? {
                              ...item,
                              state: "error",
                              error: job.data?.error_code,
                          }
                        : item,
                ),
            );
            setActive(undefined);
            running.current = false;
        }
    }, [active, job.data]);
    useEffect(() => {
        const before = (event: BeforeUnloadEvent) => {
            if (running.current) {
                event.preventDefault();
                event.returnValue = "";
            }
        };
        window.addEventListener("beforeunload", before);
        return () => window.removeEventListener("beforeunload", before);
    }, []);
    async function add(files: FileList | File[]) {
        const incoming = Array.from(files).slice(0, 6);
        const next: Item[] = [];
        for (const file of incoming) {
            const error = !ACCEPT.includes(file.type)
                ? t("invalidImage")
                : await validImage(file);
            next.push({
                id: `${file.name}-${file.lastModified}-${Math.random()}`,
                file,
                state: error ? "error" : "waiting",
                progress: 0,
                error: error ?? undefined,
            });
        }
        setItems((old) => [...old, ...next]);
    }
    async function processQueue() {
        if (running.current) return;
        const item = items.find((candidate) => candidate.state === "waiting");
        if (!item) return;
        running.current = true;
        setItems((old) =>
            old.map((candidate) =>
                candidate.id === item.id
                    ? { ...candidate, state: "uploading" }
                    : candidate,
            ),
        );
        try {
            const response = await uploadWithProgress<{ job_id: string }>(
                `/projects/${projectId}/uploads`,
                projectId,
                item.file,
                (progress) =>
                    setItems((old) =>
                        old.map((candidate) =>
                            candidate.id === item.id
                                ? { ...candidate, progress }
                                : candidate,
                        ),
                    ),
            );
            setItems((old) =>
                old.map((candidate) =>
                    candidate.id === item.id
                        ? {
                              ...candidate,
                              state: "processing",
                              jobId: response.job_id,
                              progress: 100,
                          }
                        : candidate,
                ),
            );
            setActive(response.job_id);
        } catch (cause) {
            setItems((old) =>
                old.map((candidate) =>
                    candidate.id === item.id
                        ? {
                              ...candidate,
                              state: "error",
                              error:
                                  cause instanceof ApiError
                                      ? cause.code
                                      : "E_INTERNAL",
                          }
                        : candidate,
                ),
            );
            running.current = false;
        }
    }
    useEffect(() => {
        void processQueue();
    }, [items]);
    const drop = (event: DragEvent) => {
        event.preventDefault();
        setDrag(false);
        if (event.dataTransfer.files.length) void add(event.dataTransfer.files);
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
            <div
                className={`dropzone ${drag ? "active" : ""}`}
                onDragOver={(event) => {
                    event.preventDefault();
                    setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={drop}
                onClick={() => input.current?.click()}
            >
                <input
                    ref={input}
                    data-testid="upload-input"
                    hidden
                    type="file"
                    multiple
                    accept={ACCEPT.join(",")}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                        event.target.files && void add(event.target.files)
                    }
                />
                <strong>{t("dropImage")}</strong>
                <span>{t("chooseImage")}</span>
            </div>
            <div className="upload-list">
                {items.map((item) => (
                    <article className="card upload-item" key={item.id}>
                        <div>
                            <strong>{item.file.name}</strong>
                            <small>
                                {item.state === "processing"
                                    ? t("processing")
                                    : item.state === "uploading"
                                      ? `${item.progress}%`
                                      : item.state === "done"
                                        ? t("complete")
                                        : item.state === "error"
                                          ? item.error?.startsWith("E_")
                                              ? errorText(item.error)
                                              : item.error
                                          : t("waiting")}
                            </small>
                            {item.state === "error" && (
                                <button
                                    className="text-button"
                                    onClick={() =>
                                        setItems((old) =>
                                            old.map((candidate) =>
                                                candidate.id === item.id
                                                    ? {
                                                          ...candidate,
                                                          state: "waiting",
                                                          error: undefined,
                                                      }
                                                    : candidate,
                                            ),
                                        )
                                    }
                                >
                                    {t("retry")}
                                </button>
                            )}
                        </div>
                        {item.state === "done" && item.result && (
                            <div className="result">
                                <span>
                                    {t("page", {
                                        number:
                                            (item.result.page_index ?? 0) + 1,
                                    })}
                                </span>
                                {Object.entries(item.result.counts ?? {}).map(
                                    ([key, value]) => (
                                        <span key={key}>
                                            {key}: {value}
                                        </span>
                                    ),
                                )}
                                {Array.from(
                                    new Set(
                                        (item.result.cells ?? []).flatMap(
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
