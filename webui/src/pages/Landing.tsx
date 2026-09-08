import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch, ApiError } from "../lib/api";
import { isToken, saveToken } from "../lib/token";
import { t, errorText } from "../i18n/ja";
import type { Created, Meta } from "../generated/types";

const validName = (value: string) => {
    const n = value.normalize("NFC");
    return (
        n.length >= 1 &&
        n.length <= 64 &&
        n === n.trim() &&
        !/[\u0000-\u001f\u007f-\u009f]/.test(n)
    );
};
const validFamily = (value: string) =>
    /^[A-Za-z0-9][A-Za-z0-9 \-]{0,30}$/.test(value);

function TokenPanel({
    created,
    onClose,
}: {
    created: Created;
    onClose: () => void;
}) {
    const link = `${window.location.origin}/p/${created.project_id}#t=${created.token}`;
    const [copied, setCopied] = useState(false);
    const [canClose, setCanClose] = useState(false);
    useEffect(() => {
        const timer = window.setTimeout(() => setCanClose(true), 5000);
        return () => window.clearTimeout(timer);
    }, []);
    return (
        <div className="modal-backdrop">
            <section className="modal" role="dialog" aria-modal="true">
                <p className="eyebrow">{t("saveToken")}</p>
                <h2>{t("tokenWarning")}</h2>
                <input readOnly value={link} aria-label={t("sharedLink")} />
                <div className="actions">
                    <button
                        className="button"
                        onClick={() => {
                            void navigator.clipboard.writeText(link);
                            setCopied(true);
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
    const [meta, setMeta] = useState<Meta>();
    const [created, setCreated] = useState<Created>();
    const [name, setName] = useState("");
    const [familyName, setFamilyName] = useState("");
    const [charset, setCharset] = useState("ja-basic-v1");
    const [openValue, setOpenValue] = useState("");
    const [openId, setOpenId] = useState("");
    const [openToken, setOpenToken] = useState("");
    const [error, setError] = useState("");
    useEffect(() => {
        void apiFetch<Meta>("/meta")
            .then(setMeta)
            .catch(() => undefined);
    }, []);
    async function create(event: FormEvent) {
        event.preventDefault();
        setError("");
        if (!validName(name) || !validFamily(familyName)) {
            setError(t("inputInvalid"));
            return;
        }
        try {
            const result = await apiFetch<Created>("/projects", {
                method: "POST",
                body: {
                    name: name.normalize("NFC"),
                    family_name: familyName,
                    charset_id: charset,
                },
            });
            saveToken(result.project_id, result.token);
            setCreated(result);
        } catch (cause) {
            setError(
                cause instanceof ApiError
                    ? errorText(cause.code)
                    : errorText("E_INTERNAL"),
            );
        }
    }
    function open(event: FormEvent) {
        event.preventDefault();
        const match = openValue.match(
            /\/p\/([0-9a-fA-F-]{36})#t=(glp_[A-Za-z0-9_-]{43})$/,
        );
        const projectId = match?.[1] ?? openId.trim();
        const token = match?.[2] ?? openToken.trim();
        if (
            !projectId ||
            !/^[0-9a-fA-F-]{36}$/.test(projectId) ||
            !/^glp_[A-Za-z0-9_-]{43}$/.test(token)
        ) {
            setError(t("linkInvalid"));
            return;
        }
        saveToken(projectId, token);
        navigate(`/p/${projectId}`);
    }
    return (
        <>
            <header className="topbar">
                <Link to="/" className="brand">
                    glyphlab
                </Link>
                <Link to="/privacy">{t("privacy")}</Link>
            </header>
            <main className="shell landing">
                <section className="hero">
                    <p className="eyebrow">HANDWRITING → TYPEFACE</p>
                    <h1>{t("tagline")}</h1>
                    <p>{t("heroDescription")}</p>
                    <div className="steps">
                        <span>{t("stepPrint")}</span>
                        <span>{t("stepCapture")}</span>
                        <span>{t("stepReceive")}</span>
                    </div>
                    <small>
                        {t("retention", { days: meta?.retention_days ?? 14 })}
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
                                    onChange={(e) => setName(e.target.value)}
                                    required
                                    maxLength={64}
                                />
                            </label>
                            <label>
                                {t("familyName")}
                                <input
                                    value={familyName}
                                    onChange={(e) =>
                                        setFamilyName(e.target.value)
                                    }
                                    required
                                    maxLength={31}
                                />
                            </label>
                            <label>
                                {t("charset")}
                                <select
                                    value={charset}
                                    onChange={(e) => setCharset(e.target.value)}
                                >
                                    {(
                                        meta?.charsets ?? [
                                            {
                                                id: "ja-basic-v1",
                                                encoded: 278,
                                                drawn: 276,
                                                pages: 6,
                                            },
                                        ]
                                    ).map((item) => (
                                        <option key={item.id} value={item.id}>
                                            {item.id}（
                                            {t("pageCount", {
                                                count: item.drawn,
                                                pages: item.pages,
                                            })}
                                            ）
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <button className="button" type="submit">
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
                    onClose={() => navigate(`/p/${created.project_id}`)}
                />
            )}
        </>
    );
}
