import { glyphSvgCache } from "../lib/svgCache";
import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { apiFetch, ApiError } from "../lib/api";
import {
    isToken,
    isProjectId,
    parseProjectLink,
    saveToken,
} from "../lib/token";
import { t, errorText } from "../i18n/ja";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Created, Meta } from "../generated/types";

const validName = (value: string) => {
    const n = value.normalize("NFC");
    return (
        Array.from(n).length >= 1 &&
        Array.from(n).length <= 64 &&
        n === n.trim() &&
        !/[\u0000-\u001f\u007f-\u009f]/.test(n)
    );
};
const validFamily = (value: string) =>
    /^[A-Za-z0-9][A-Za-z0-9 \-]{0,30}$/.test(value);

export function TokenPanel({
    created,
    onClose,
    persisted = true,
}: {
    created: Created;
    onClose: () => void;
    persisted?: boolean;
}) {
    const link = `${window.location.origin}/p/${created.project_id}#t=${created.token}`;
    const [copied, setCopied] = useState(false);
    const [copyError, setCopyError] = useState(false);
    const [canClose, setCanClose] = useState(false);
    useEffect(() => {
        const timer = window.setTimeout(() => setCanClose(true), 5000);
        return () => window.clearTimeout(timer);
    }, []);
    return (
        <div className="modal-backdrop">
            <section
                className="modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="save-link-title"
                onKeyDown={(event) => {
                    if (event.key !== "Tab") return;
                    const controls = Array.from(
                        event.currentTarget.querySelectorAll<HTMLElement>(
                            "input, button:not(:disabled)",
                        ),
                    );
                    const first = controls[0],
                        last = controls[controls.length - 1];
                    if (event.shiftKey && document.activeElement === first) {
                        event.preventDefault();
                        last.focus();
                    } else if (
                        !event.shiftKey &&
                        document.activeElement === last
                    ) {
                        event.preventDefault();
                        first.focus();
                    }
                }}
            >
                <p className="eyebrow">{t("saveToken")}</p>
                <h2 id="save-link-title">{t("tokenWarning")}</h2>
                <p>{t(persisted ? "tokenAutosaved" : "tokenSessionOnly")}</p>
                {copyError && <p role="alert">{t("copyFailed")}</p>}
                <input
                    autoFocus
                    readOnly
                    value={link}
                    aria-label={t("sharedLink")}
                />
                <div className="actions">
                    <button
                        className="button"
                        onClick={async () => {
                            setCopyError(false);
                            try {
                                await navigator.clipboard.writeText(link);
                                setCopied(true);
                            } catch {
                                setCopied(false);
                                setCopyError(true);
                            }
                        }}
                    >
                        {copied ? t("copied") : t("copyLink")}
                    </button>
                    <button
                        className="button secondary"
                        disabled={!canClose}
                        onClick={onClose}
                    >
                        {t("closeSaved")}
                    </button>
                </div>
            </section>
        </div>
    );
}

export default function Landing() {
    const navigate = useNavigate();
    const client = useQueryClient();
    const location = useLocation();
    const [deleted] = useState(
        Boolean((location.state as { deleted?: boolean } | null)?.deleted),
    );
    const [pending, setPending] = useState(false);
    const metaQuery = useQuery({
        queryKey: ["meta"],
        queryFn: ({ signal }) => apiFetch<Meta>("/meta", { signal }),
        retry: false,
    });
    const meta = metaQuery.data;
    const [created, setCreated] = useState<Created>();
    const [persisted, setPersisted] = useState(true);
    const [name, setName] = useState("");
    const [familyName, setFamilyName] = useState("");
    const [nameEdited, setNameEdited] = useState(false);
    const [familyEdited, setFamilyEdited] = useState(false);
    const nameValid = validName(name);
    const familyValid = validFamily(familyName);
    const [charset, setCharset] = useState("ja-basic-v1");
    const [openValue, setOpenValue] = useState("");
    const [openId, setOpenId] = useState("");
    const [openToken, setOpenToken] = useState("");
    const [error, setError] = useState("");
    useEffect(() => {
        if (
            meta?.charsets.length &&
            !meta.charsets.some((item) => item.id === charset)
        )
            setCharset(meta.charsets[0].id);
    }, [meta, charset]);
    useEffect(() => {
        if (deleted)
            navigate(location.pathname, { replace: true, state: null });
    }, [deleted, location.pathname, navigate]);
    async function create(event: FormEvent) {
        event.preventDefault();
        setError("");
        if (pending || !meta) return;
        if (!validName(name) || !validFamily(familyName)) {
            setError(t("inputInvalid"));
            return;
        }
        setPending(true);
        try {
            const result = await apiFetch<Created>("/projects", {
                method: "POST",
                body: {
                    name: name.normalize("NFC"),
                    family_name: familyName,
                    charset_id: charset,
                },
            });
            setPersisted(saveToken(result.project_id, result.token));
            setCreated(result);
        } catch (cause) {
            setError(
                cause instanceof ApiError
                    ? errorText(cause.code)
                    : errorText("E_INTERNAL"),
            );
        } finally {
            setPending(false);
        }
    }
    function open(event: FormEvent) {
        event.preventDefault();
        setError("");
        const parsed = openValue.trim()
            ? parseProjectLink(openValue.trim())
            : null;
        const projectId = parsed?.projectId ?? openId.trim().toLowerCase();
        const token = parsed?.token ?? openToken.trim();
        if (
            (openValue.trim() && !parsed) ||
            !isProjectId(projectId) ||
            !isToken(token)
        ) {
            setError(t("linkInvalid"));
            return;
        }
        client.removeQueries({
            predicate: (query) => query.queryKey.includes(projectId),
        });
        glyphSvgCache.clear(`${projectId}:`);
        saveToken(projectId, token);
        navigate(`/p/${projectId}`);
    }
    return (
        <>
            <header className="topbar">
                <Link to="/" className="brand">
                    {t("brand")}
                </Link>
                <Link to="/privacy">{t("privacy")}</Link>
            </header>
            <main
                className="shell landing"
                ref={(node) => {
                    if (created) node?.setAttribute("inert", "");
                    else node?.removeAttribute("inert");
                }}
            >
                <section className="hero">
                    <p className="eyebrow">{t("heroEyebrow")}</p>
                    <h1>{t("tagline")}</h1>
                    <p>{t("heroDescription")}</p>
                    <div className="steps">
                        <span>{t("stepPrint")}</span>
                        <span>{t("stepCapture")}</span>
                        <span>{t("stepReceive")}</span>
                    </div>
                    <small>
                        {meta && t("retention", { days: meta.retention_days })}
                    </small>
                </section>
                <div className="columns">
                    <section className="card">
                        <h2>{t("create")}</h2>
                        <form onSubmit={create}>
                            <label>
                                {t("name")}
                                <input
                                    value={name}
                                    onChange={(e) => {
                                        setName(e.target.value);
                                        setNameEdited(true);
                                    }}
                                    aria-invalid={
                                        nameEdited ? !nameValid : undefined
                                    }
                                    aria-describedby={
                                        nameEdited && !nameValid
                                            ? "name-error"
                                            : undefined
                                    }
                                    required
                                />
                            </label>
                            {nameEdited && !nameValid && (
                                <p
                                    id="name-error"
                                    role="alert"
                                    className="notice error"
                                >
                                    {t("nameInvalid")}
                                </p>
                            )}
                            <label>
                                {t("familyName")}
                                <input
                                    value={familyName}
                                    onChange={(e) => {
                                        setFamilyName(e.target.value);
                                        setFamilyEdited(true);
                                    }}
                                    aria-invalid={
                                        familyEdited ? !familyValid : undefined
                                    }
                                    aria-describedby="family-help"
                                    required
                                    maxLength={31}
                                />
                            </label>
                            <p
                                id="family-help"
                                role={
                                    familyEdited && !familyValid
                                        ? "alert"
                                        : undefined
                                }
                                className={
                                    familyEdited && !familyValid
                                        ? "notice error"
                                        : undefined
                                }
                            >
                                <small>{t("familyHelp")}</small>
                            </p>
                            <label>
                                {t("charset")}
                                <select
                                    value={charset}
                                    onChange={(e) => setCharset(e.target.value)}
                                >
                                    {(meta?.charsets ?? []).map((item) => (
                                        <option key={item.id} value={item.id}>
                                            {t("charsetOption", {
                                                id: item.id,
                                                count: item.drawn,
                                                pages: item.pages,
                                            })}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <button
                                className="button"
                                type="submit"
                                disabled={
                                    pending ||
                                    !meta ||
                                    !nameValid ||
                                    !familyValid
                                }
                            >
                                {t("submit")}
                            </button>
                        </form>
                    </section>
                    <section className="card">
                        <h2>{t("open")}</h2>
                        <form onSubmit={open}>
                            <label>
                                {t("sharedLink")}
                                <input
                                    value={openValue}
                                    onChange={(e) =>
                                        setOpenValue(e.target.value)
                                    }
                                    placeholder={t("linkPlaceholder")}
                                />
                            </label>
                            <div className="open-fields">
                                <label>
                                    {t("separateProjectId")}
                                    <input
                                        value={openId}
                                        onChange={(e) =>
                                            setOpenId(e.target.value)
                                        }
                                    />
                                </label>
                                <label>
                                    {t("separateToken")}
                                    <input
                                        value={openToken}
                                        onChange={(e) =>
                                            setOpenToken(e.target.value)
                                        }
                                        placeholder={t("tokenPlaceholder")}
                                    />
                                </label>
                            </div>
                            <button className="button secondary" type="submit">
                                {t("openButton")}
                            </button>
                        </form>
                    </section>
                </div>
                {deleted && (
                    <p role="status" className="notice">
                        {t("deleted")}
                    </p>
                )}
                {metaQuery.error && (
                    <div className="notice error" role="alert">
                        {errorText(
                            metaQuery.error instanceof ApiError
                                ? metaQuery.error.code
                                : "E_INTERNAL",
                        )}{" "}
                        <button onClick={() => void metaQuery.refetch()}>
                            {t("retry")}
                        </button>
                    </div>
                )}
                {error && (
                    <p className="notice error" role="alert">
                        {error}
                    </p>
                )}
                <footer>
                    <Link to="/privacy">{t("privacy")}</Link>
                </footer>
            </main>
            {created && (
                <TokenPanel
                    created={created}
                    persisted={persisted}
                    onClose={() => navigate(`/p/${created.project_id}`)}
                />
            )}
        </>
    );
}
