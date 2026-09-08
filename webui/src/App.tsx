import {
    Navigate,
    Outlet,
    Route,
    Routes,
    Link,
    useParams,
} from "react-router-dom";
import { useEffect, useState } from "react";
import Landing from "./pages/Landing";
import ProjectHome from "./pages/ProjectHome";
import Upload from "./pages/Upload";
import Review from "./pages/Review";
import Build from "./pages/Build";
import Privacy from "./pages/Privacy";
import { consumeFragmentToken, getToken } from "./lib/token";
import { t } from "./i18n/ja";

function ProjectLayout() {
    const { projectId = "" } = useParams();
    const [hasToken, setHasToken] = useState(false);
    useEffect(() => {
        consumeFragmentToken(projectId);
        setHasToken(Boolean(getToken(projectId)));
    }, [projectId]);
    if (!hasToken)
        return (
            <main className="shell">
                <section className="card">
                    <h1>{t("open")}</h1>
                    <p>{t("tokenWarning")}</p>
                    <Link className="button" to="/">
                        {t("cancel")}
                    </Link>
                </section>
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
                <Outlet />
            </main>
        </>
    );
}

export default function App() {
    return (
        <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/p/:projectId" element={<ProjectLayout />}>
                <Route index element={<ProjectHome />} />
                <Route path="upload" element={<Upload />} />
                <Route path="review" element={<Review />} />
                <Route path="build" element={<Build />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
