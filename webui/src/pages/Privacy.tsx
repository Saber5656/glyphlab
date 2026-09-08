import { Link } from "react-router-dom";
import { t } from "../i18n/ja";
export default function Privacy() {
    return (
        <main className="shell">
            <Link to="/" className="brand">
                glyphlab
            </Link>
            <article className="card prose">
                <h1>{t("privacy")}</h1>
                <p>{t("privacyData")}</p>
                <h2>{t("privacyStoredTitle")}</h2>
                <p>{t("privacyStored")}</p>
                <h2>{t("privacyAccessTitle")}</h2>
                <p>{t("privacyAccess")}</p>
                <h2>{t("privacySelfHostTitle")}</h2>
                <p>{t("privacySelfHost")}</p>
                <Link to="/">{t("backTop")}</Link>
            </article>
        </main>
    );
}
