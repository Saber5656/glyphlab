import { glyphSvgCache } from "./lib/svgCache";
import {
    Navigate,
    Outlet,
    Route,
    Routes,
    Link,
    useParams,
} from "react-router-dom";
import { FormEvent, useEffect, useState } from "react";
import Landing from "./pages/Landing";
import ProjectHome from "./pages/ProjectHome";
import Upload from "./pages/Upload";
import Review from "./pages/Review";
import Build from "./pages/Build";
import Privacy from "./pages/Privacy";
import {
    consumeFragmentToken,
    getToken,
    saveToken,
    clearToken,
    isToken,
    TOKEN_CHANGED,
} from "./lib/token";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "./lib/api";
import type { Summary } from "./generated/types";
import { t, errorText } from "./i18n/ja";

function ProjectLayout() {
    const { projectId = "" } = useParams();
    const client = useQueryClient();
    const [token, setToken] = useState(() => {
        const previous = getToken(projectId);
        const current = consumeFragmentToken(projectId);
        if (current !== previous) {
            client.removeQueries({
                predicate: (query) => query.queryKey.includes(projectId),
            });
            glyphSvgCache.clear(`${projectId}:`);
        }
        return current;
    });
    const [input, setInput] = useState("");
    const [invalid, setInvalid] = useState(false);
    useEffect(() => {
        setToken(consumeFragmentToken(projectId));
        const update = () => setToken(getToken(projectId));
        window.addEventListener(TOKEN_CHANGED, update);
        window.addEventListener("storage", update);
        return () => {
            window.removeEventListener(TOKEN_CHANGED, update);
            window.removeEventListener("storage", update);
        };
    }, [projectId]);
    const summary = useQuery({
        queryKey: ["summary", projectId],
        queryFn: ({ signal }) =>
            apiFetch<Summary>(`/projects/${projectId}`, { projectId, signal }),
        enabled: Boolean(token),
        retry: false,
    });
    const unavailable =
        summary.error instanceof ApiError &&
        [401, 404].includes(summary.error.status);
    useEffect(() => {
        if (unavailable) {
            clearToken(projectId);
            glyphSvgCache.clear(`${projectId}:`);
        }
    }, [unavailable, projectId]);
    function open(event: FormEvent) {
        event.preventDefault();
        if (!isToken(input.trim())) {
            setInvalid(true);
            return;
        }
        client.removeQueries({
            predicate: (query) => query.queryKey.includes(projectId),
        });
        glyphSvgCache.clear(`${projectId}:`);
        saveToken(projectId, input.trim());
        setInput("");
        setInvalid(false);
    }
    if (!token || unavailable)
        return (
            <main className="shell">
                <section className="card">
                    <h1>{t("open")}</h1>
                    <p>
                        {unavailable
                            ? errorText("E_NOT_FOUND")
                            : t("tokenNeeded")}
                    </p>
                    <form onSubmit={open}>
                        <label>
                            {t("separateToken")}
                            <input
                                value={input}
                                onChange={(event) =>
                                    setInput(event.target.value)
                                }
                                autoComplete="off"
                            />
                        </label>
                        {invalid && <p role="alert">{t("linkInvalid")}</p>}
                        <button className="button" type="submit">
                            {t("openButton")}
                        </button>
                        <Link className="button secondary" to="/">
                            {t("cancel")}
                        </Link>
                    </form>
                </section>
            </main>
        );
    if (summary.isPending)
        return (
            <main className="shell">
                <p>{t("loading")}</p>
            </main>
        );
    if (summary.error && !summary.data)
        return (
            <main className="shell">
                <p role="alert">
                    {errorText(
                        summary.error instanceof ApiError
                            ? summary.error.code
                            : "E_INTERNAL",
                    )}
                </p>
                <button onClick={() => void summary.refetch()}>
                    {t("retry")}
                </button>
            </main>
        );
    return (
        <>
            <header className="topbar">
                <Link to={`/p/${projectId}`} className="brand">
                    glyphlab
                </Link>
                <nav>
                    <Link to={`/p/${projectId}/upload`}>{t("upload")}</Link>
                    <Link to={`/p/${projectId}/review`}>{t("review")}</Link>
                    <Link to={`/p/${projectId}/build`}>{t("build")}</Link>
                </nav>
            </header>
            <main className="shell">
                {summary.error && (
                    <div role="alert" className="notice error">
                        <p>
                            {errorText(
                                summary.error instanceof ApiError
                                    ? summary.error.code
                                    : "E_INTERNAL",
                            )}
                        </p>
                        <button onClick={() => void summary.refetch()}>
                            {t("retry")}
                        </button>
                    </div>
                )}
                <Outlet key={projectId} />
            </main>
        </>
    );
}

function ProjectRoute() {
    const { projectId } = useParams();
    return <ProjectLayout key={projectId} />;
}

export default function App() {
    return (
        <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/p/:projectId" element={<ProjectRoute />}>
                <Route index element={<ProjectHome />} />
                <Route path="upload" element={<Upload />} />
                <Route path="review" element={<Review />} />
                <Route path="build" element={<Build />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
