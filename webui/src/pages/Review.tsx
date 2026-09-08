import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "../lib/api";
import { errorText, t, warningText } from "../i18n/ja";
import type {
    GlyphList,
    GlyphResponse,
    ReviewRequest,
} from "../generated/types";

type Glyph = Omit<GlyphResponse, "codepoint" | "svg_url"> & {
    codepoint: number;
    svg_url?: string;
};
const section = (cp: number) =>
    cp <= 0x7e
        ? t("sectionLatin")
        : cp >= 0x3041 && cp <= 0x3096
          ? t("sectionHiragana")
          : cp >= 0x30a1 && cp <= 0x30fc
            ? t("sectionKatakana")
            : t("sectionSymbols");
const statusLabel: Record<Glyph["status"], string> = {
    missing: t("statusMissing"),
    auto: t("statusAuto"),
    accepted: t("statusAccepted"),
    rejected: t("statusRejected"),
};
const svgCache = new Map<string, string>();
function GlyphPreview({
    projectId,
    glyph,
}: {
    projectId: string;
    glyph: Glyph;
}) {
    const [src, setSrc] = useState<string>();
    const target = useRef<HTMLSpanElement>(null);
    const cacheKey = `${projectId}:${glyph.codepoint}:${glyph.updated_at ?? "latest"}`;
    useEffect(() => {
        const cached = svgCache.get(cacheKey);
        if (!glyph.svg_url) return;
        if (cached) {
            setSrc(cached);
            return;
        }
        let observer: IntersectionObserver | undefined;
        const load = () => {
            void apiFetch<Blob>(
                `/projects/${projectId}/glyphs/${glyph.codepoint}.svg`,
                { projectId, raw: true },
            )
                .then((value) => {
                    const objectUrl = URL.createObjectURL(value);
                    svgCache.set(cacheKey, objectUrl);
                    if (svgCache.size > 350) {
                        const oldest = svgCache.keys().next().value;
                        if (oldest) {
                            URL.revokeObjectURL(svgCache.get(oldest)!);
                            svgCache.delete(oldest);
                        }
                    }
                    setSrc(objectUrl);
                })
                .catch(() => undefined);
        };
        if (typeof IntersectionObserver === "undefined") load();
        else {
            observer = new IntersectionObserver(
                (entries) => {
                    if (!entries[0]?.isIntersecting) return;
                    observer?.disconnect();
                    load();
                },
                { rootMargin: "300px" },
            );
            if (target.current) observer.observe(target.current);
        }
        return () => observer?.disconnect();
    }, [cacheKey, glyph.codepoint, glyph.svg_url, projectId]);
    return (
        <span ref={target}>
            {src ? (
                <img src={src} alt={glyph.char} />
            ) : (
                <span className="missing-char">{glyph.char}</span>
            )}
        </span>
    );
}
export default function Review() {
    const { projectId = "" } = useParams();
    const client = useQueryClient();
    const [filter, setFilter] = useState("all");
    const [search, setSearch] = useState("");
    const [selected, setSelected] = useState<number[]>([]);
    const query = useQuery({
        queryKey: ["glyphs", projectId],
        queryFn: async () => {
            const value = await apiFetch<GlyphList>(
                `/projects/${projectId}/glyphs?limit=300`,
                { projectId },
            );
            return {
                glyphs: value.glyphs.map(
                    (glyph): Glyph => ({
                        ...glyph,
                        codepoint: Number(glyph.codepoint),
                        svg_url: glyph.svg_url ?? undefined,
                    }),
                ),
            };
        },
    });
    const review = useMutation({
        mutationFn: (payload: ReviewRequest) =>
            apiFetch(`/projects/${projectId}/glyphs:review`, {
                method: "POST",
                body: payload,
                projectId,
            }),
        onMutate: async (payload) => {
            await client.cancelQueries({ queryKey: ["glyphs", projectId] });
            const previous = query.data;
            client.setQueryData<{ glyphs: Glyph[] }>(
                ["glyphs", projectId],
                (old) =>
                    old && {
                        glyphs: old.glyphs.map((glyph) =>
                            payload.accept?.includes(String(glyph.codepoint))
                                ? { ...glyph, status: "accepted" }
                                : payload.reject?.includes(
                                        String(glyph.codepoint),
                                    )
                                  ? { ...glyph, status: "rejected" }
                                  : glyph,
                        ),
                    },
            );
            return { previous };
        },
        onError: (_error, _payload, context) =>
            client.setQueryData(["glyphs", projectId], context?.previous),
        onSettled: () => {
            void client.invalidateQueries({ queryKey: ["summary", projectId] });
        },
    });
    const glyphs = useMemo(
        () =>
            (query.data?.glyphs ?? []).filter(
                (glyph) =>
                    (filter === "all" ||
                        (filter === "warning"
                            ? glyph.warnings.length > 0
                            : glyph.status === filter)) &&
                    (!search ||
                        glyph.char.includes(search) ||
                        `U+${glyph.codepoint.toString(16).toUpperCase()}`.includes(
                            search.toUpperCase(),
                        )),
            ),
        [filter, search, query.data],
    );
    function act(codepoints: number[], action: "accept" | "reject") {
        if (codepoints.length)
            review.mutate(
                action === "accept"
                    ? { accept: codepoints.map(String), reject: [] }
                    : { accept: [], reject: codepoints.map(String) },
            );
        setSelected([]);
    }
    function keyboard(event: KeyboardEvent<HTMLButtonElement>, cp: number) {
        const target =
            event.key === "a"
                ? "accept"
                : event.key === "r"
                  ? "reject"
                  : undefined;
        const index = glyphs.findIndex((glyph) => glyph.codepoint === cp);
        if (
            target &&
            query.data?.glyphs.find((glyph) => glyph.codepoint === cp)
                ?.status !== "missing"
        ) {
            event.preventDefault();
            act([cp], target);
        } else if (["ArrowRight", "ArrowDown"].includes(event.key))
            document
                .querySelectorAll<HTMLButtonElement>(".glyph-cell")
                [index + 1]?.focus();
        else if (["ArrowLeft", "ArrowUp"].includes(event.key))
            document
                .querySelectorAll<HTMLButtonElement>(".glyph-cell")
                [Math.max(0, index - 1)]?.focus();
        else if (event.key === "Escape") setSelected([]);
    }
    return (
        <section>
            <div className="page-heading">
                <div>
                    <p className="eyebrow">03 / 04</p>
                    <h1>{t("review")}</h1>
                    <p>{t("reviewDescription")}</p>
                </div>
                <Link className="button" to={`/p/${projectId}/build`}>
                    {t("toBuild")}
                </Link>
            </div>
            <div className="review-toolbar">
                <input
                    placeholder={t("searchGlyph")}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                />
                {[
                    ["all", t("all")],
                    ["auto", t("unconfirmed")],
                    ["accepted", t("accepted")],
                    ["rejected", t("rejected")],
                    ["missing", t("missing")],
                    ["warning", t("warnings")],
                ].map(([value, label]) => (
                    <button
                        className={filter === value ? "active" : ""}
                        key={value}
                        onClick={() => setFilter(value)}
                    >
                        {label}
                    </button>
                ))}
                <button
                    onClick={() => {
                        if (window.confirm(t("acceptAutoConfirm")))
                            act(
                                (query.data?.glyphs ?? [])
                                    .filter((glyph) => glyph.status === "auto")
                                    .map((glyph) => glyph.codepoint),
                                "accept",
                            );
                    }}
                >
                    {t("acceptAuto")}
                </button>
            </div>
            {query.error && (
                <p className="notice error">
                    {errorText(
                        query.error instanceof ApiError
                            ? query.error.code
                            : "E_INTERNAL",
                    )}
                </p>
            )}
            {review.error && (
                <p className="notice error">
                    {errorText(
                        review.error instanceof ApiError
                            ? review.error.code
                            : "E_INTERNAL",
                    )}
                </p>
            )}
            <div className="review-grid">
                {[
                    t("sectionLatin"),
                    t("sectionHiragana"),
                    t("sectionKatakana"),
                    t("sectionSymbols"),
                ].map((name) => (
                    <div className="glyph-section" key={name}>
                        <h2>{name}</h2>
                        <div className="grid">
                            {glyphs
                                .filter(
                                    (glyph) =>
                                        section(glyph.codepoint) === name,
                                )
                                .map((glyph) => (
                                    <button
                                        disabled={glyph.status === "missing"}
                                        key={glyph.codepoint}
                                        className={`glyph-cell status-${glyph.status} ${selected.includes(glyph.codepoint) ? "selected" : ""}`}
                                        aria-label={`${glyph.char} ${statusLabel[glyph.status]}`}
                                        onKeyDown={(event) =>
                                            keyboard(event, glyph.codepoint)
                                        }
                                        onClick={() =>
                                            glyph.status !== "missing" &&
                                            setSelected((old) =>
                                                old.includes(glyph.codepoint)
                                                    ? old.filter(
                                                          (cp) =>
                                                              cp !==
                                                              glyph.codepoint,
                                                      )
                                                    : [...old, glyph.codepoint],
                                            )
                                        }
                                    >
                                        {glyph.status === "missing" ||
                                        !glyph.svg_url ? (
                                            <span className="missing-char">
                                                {glyph.char}
                                            </span>
                                        ) : (
                                            <GlyphPreview
                                                projectId={projectId}
                                                glyph={glyph}
                                            />
                                        )}
                                        <small>
                                            {glyph.char} ·{" "}
                                            {statusLabel[glyph.status]}
                                        </small>
                                        {glyph.warnings.length > 0 && (
                                            <i
                                                title={glyph.warnings
                                                    .map(warningText)
                                                    .join("、")}
                                            >
                                                !
                                            </i>
                                        )}
                                    </button>
                                ))}
                        </div>
                    </div>
                ))}
            </div>
            {selected.length > 0 && (
                <div className="selection-bar">
                    <span>
                        {t("selectedCount", { count: selected.length })}
                    </span>
                    <button
                        className="button"
                        onClick={() => act(selected, "accept")}
                    >
                        {t("accepted")}
                    </button>
                    <button
                        className="button secondary"
                        onClick={() => act(selected, "reject")}
                    >
                        {t("rejected")}
                    </button>
                </div>
            )}
        </section>
    );
}
