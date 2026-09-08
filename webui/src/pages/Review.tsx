import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "../lib/api";
import { glyphSvgCache } from "../lib/svgCache";
import { errorText, t, warningText } from "../i18n/ja";
import type { GlyphList, GlyphResponse, ReviewRequest } from "../generated/types";
import type { components } from "../generated/api";

const sections = ["sectionLatin", "sectionHiragana", "sectionKatakana", "sectionSymbols"] as const;
function section(codepoint: string) {
  const cp = parseInt(codepoint.slice(2), 16);
  return cp >= 0x20 && cp <= 0x7e ? 0 : cp >= 0x3041 && cp <= 0x3096 ? 1 : (cp >= 0x30a1 && cp <= 0x30fa) || cp === 0x30fc ? 2 : 3;
}
const statusLabel = { missing: t("statusMissing"), auto: t("statusAuto"), accepted: t("statusAccepted"), rejected: t("statusRejected") };
function GlyphPreview({ projectId, glyph }: { projectId: string; glyph: GlyphResponse }) {
  const [preview, setPreview] = useState<{ key: string; url: string }>();
  const target = useRef<HTMLSpanElement>(null);
  const revision = glyph.svg_url ? new URL(glyph.svg_url, window.location.origin).searchParams.get("v") : null;
  const cacheKey = `${projectId}:${glyph.codepoint}:${revision ?? glyph.updated_at}`;
  // Keep authenticated requests on the canonical API route. Only the geometry
  // revision is forwarded, so status updates reuse previews and new ink bypasses
  // the browser's previous SVG response cache.
  const svgPath = `/projects/${projectId}/glyphs/${glyph.codepoint}.svg${revision === null ? "" : `?v=${encodeURIComponent(revision)}`}`;
  useEffect(() => {
    let disposed = false;
    let observer: IntersectionObserver | undefined;
    const load = () => {
      observer?.disconnect();
      void glyphSvgCache.load(cacheKey, () => apiFetch<Blob>(svgPath, { projectId, raw: true }))
        .then(url => { if (!disposed && url) setPreview({ key: cacheKey, url }); })
        .catch(() => { /* The labeled character remains usable when its preview fails. */ });
    };
    if (glyph.svg_url) {
      if (typeof IntersectionObserver === "undefined") load();
      else {
        observer = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) load(); }, { rootMargin: "300px" });
        if (target.current) observer.observe(target.current);
      }
    }
    return () => { disposed = true; observer?.disconnect(); };
  }, [cacheKey, glyph.svg_url, projectId, svgPath]);
  return <span ref={target}>{preview?.key === cacheKey ? <img src={preview.url} alt={glyph.char} /> : <span className="missing-char">{glyph.char}</span>}</span>;
}

export default function Review() {
  const { projectId = "" } = useParams();
  const client = useQueryClient();
  const grid = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [multi, setMulti] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [focused, setFocused] = useState<string>();
  const [partialError, setPartialError] = useState(false);
  const query = useQuery({
    queryKey: ["glyphs", projectId],
    queryFn: () => apiFetch<GlyphList>(`/projects/${projectId}/glyphs?limit=300`, { projectId }),
    retry: (failureCount, error) => !(error instanceof ApiError && error.status === 429) && failureCount < 1,
  });
  const review = useMutation({
    mutationFn: (body: ReviewRequest) => apiFetch<components["schemas"]["ReviewResponse"]>(`/projects/${projectId}/glyphs:review`, { method: "POST", body, projectId }),
    onMutate: async payload => {
      setPartialError(false);
      await client.cancelQueries({ queryKey: ["glyphs", projectId] });
      const previous = client.getQueryData<GlyphList>(["glyphs", projectId]);
      client.setQueryData<GlyphList>(["glyphs", projectId], old => old && ({ ...old, glyphs: old.glyphs.map(glyph => ({ ...glyph, status: payload.accept?.includes(glyph.codepoint) ? "accepted" : payload.reject?.includes(glyph.codepoint) ? "rejected" : glyph.status })) }));
      return { previous };
    },
    onSuccess: response => setPartialError(response.errors.length > 0),
    onError: (_error, _payload, context) => client.setQueryData(["glyphs", projectId], context?.previous),
    onSettled: async () => {
      await Promise.all([client.invalidateQueries({ queryKey: ["summary", projectId] }), client.invalidateQueries({ queryKey: ["glyphs", projectId] })]);
    },
  });
  const allGlyphs = query.data?.glyphs ?? [];
  const glyphs = useMemo(() => (query.data?.glyphs ?? []).filter(glyph => (filter === "all" || (filter === "warning" ? glyph.warnings.length > 0 : glyph.status === filter)) && (!search || glyph.char.includes(search) || glyph.codepoint.includes(search.toUpperCase()))), [filter, search, query.data]);
  const counts = { missing: 0, auto: 0, accepted: 0, rejected: 0 };
  for (const glyph of allGlyphs) counts[glyph.status]++;
  const current = glyphs.find(glyph => glyph.codepoint === focused);
  function act(codepoints: string[], action: "accept" | "reject") {
    const eligible = codepoints.filter(cp => allGlyphs.some(g => g.codepoint === cp && g.status !== "missing"));
    if (eligible.length && !review.isPending) review.mutate(action === "accept" ? { accept: eligible.slice(0, 400), reject: [] } : { accept: [], reject: eligible.slice(0, 400) });
    setSelected([]);
  }
  function keyboard(event: KeyboardEvent<HTMLButtonElement>, cp: string) {
    if (event.key.toLowerCase() === "a" || event.key.toLowerCase() === "r") { event.preventDefault(); act([cp], event.key.toLowerCase() === "a" ? "accept" : "reject"); }
    else if (event.key.startsWith("Arrow")) {
      event.preventDefault();
      const cells = Array.from(grid.current?.querySelectorAll<HTMLButtonElement>(".glyph-cell") ?? []);
      const index = cells.indexOf(event.currentTarget);
      const direction = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1;
      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        const origin = event.currentTarget.getBoundingClientRect();
        const center = origin.left + origin.width / 2;
        const candidates = cells.map(cell => ({ cell, rect: cell.getBoundingClientRect() }))
          .filter(({ rect }) => (rect.top - origin.top) * direction > 1)
          .sort((a, b) => Math.abs(a.rect.top - origin.top) - Math.abs(b.rect.top - origin.top) || Math.abs(a.rect.left + a.rect.width / 2 - center) - Math.abs(b.rect.left + b.rect.width / 2 - center));
        candidates[0]?.cell.focus();
      } else cells[Math.max(0, Math.min(cells.length - 1, index + direction))]?.focus();
    } else if (event.key === "Escape") { setSelected([]); setMulti(false); }
  }
  const buildCta = counts.accepted + counts.auto > 0 ? <Link className="button" to={`/p/${projectId}/build`}>{t("toBuild")}</Link> : <button className="button" disabled>{t("toBuild")}</button>;
  return <section>
    <div className="page-heading"><div><p className="eyebrow">03 / 04</p><h1>{t("review")}</h1><p>{t("reviewDescription")}</p></div></div>
    <div className="review-toolbar">
      <input aria-label={t("searchGlyph")} placeholder={t("searchGlyph")} value={search} onChange={event => setSearch(event.target.value)} />
      {[["all", t("all")], ["auto", t("unconfirmed")], ["accepted", t("accepted")], ["rejected", t("rejected")], ["missing", t("missing")], ["warning", t("warnings")]].map(([value, label]) => <button aria-pressed={filter === value} className={filter === value ? "active" : ""} key={value} onClick={() => setFilter(value)}>{label}</button>)}
      <button disabled={!counts.auto || review.isPending} onClick={() => { if (window.confirm(t("acceptAutoConfirm", { count: counts.auto }))) act(allGlyphs.filter(g => g.status === "auto").map(g => g.codepoint), "accept"); }}>{t("acceptAuto")}</button>
      <label><input type="checkbox" checked={multi} onChange={event => { setMulti(event.target.checked); setSelected([]); }} />{t("multiSelect")}</label>
    </div>
    {query.isPending && <p role="status">{t("loading")}</p>}
    {(query.error || review.error || partialError) && <p role="alert" className="notice error">{errorText((query.error || review.error) instanceof ApiError ? ((query.error || review.error) as ApiError).code : partialError ? "E_VALIDATION" : "E_INTERNAL")}</p>}
    {query.error && <button disabled={query.isFetching} onClick={() => void query.refetch()}>{t("reloadGlyphs")}</button>}
    {current && !multi && <div className="review-actions" aria-label={t("focusedGlyph")}><span>{current.char} · {current.codepoint}</span><button disabled={current.status === "missing" || review.isPending} aria-label={t("acceptGlyph", { char: current.char })} onClick={() => act([current.codepoint], "accept")}>{t("accepted")}</button><button disabled={current.status === "missing" || review.isPending} aria-label={t("rejectGlyph", { char: current.char })} onClick={() => act([current.codepoint], "reject")}>{t("rejected")}</button></div>}
    {/* v1: at most 276 drawn cells. D2 kanji in v2 requires pagination and virtualization. */}
    <div className="review-grid" ref={grid}>
      {sections.map((name, index) => <div className="glyph-section" key={name}><h2>{t(name)}</h2><div className="grid">
        {glyphs.filter(g => section(g.codepoint) === index).map(glyph => <div className="glyph-item" key={glyph.codepoint}>
          <button className={`glyph-cell status-${glyph.status} ${selected.includes(glyph.codepoint) ? "selected" : ""}`} aria-label={`${glyph.char} ${statusLabel[glyph.status]}`} onFocus={() => setFocused(glyph.codepoint)} onKeyDown={event => keyboard(event, glyph.codepoint)} onClick={() => setFocused(glyph.codepoint)}>
            {glyph.status === "missing" ? <span className="missing-char">{glyph.char}</span> : <GlyphPreview projectId={projectId} glyph={glyph} />}
            <small>{glyph.char} · {statusLabel[glyph.status]}</small>{glyph.warnings.length > 0 && <i title={glyph.warnings.map(warningText).join("、")}>!</i>}
          </button>
          {multi && <label className="glyph-select"><input type="checkbox" aria-label={t("selectGlyph", { char: glyph.char })} disabled={glyph.status === "missing" || review.isPending} checked={selected.includes(glyph.codepoint)} onChange={event => setSelected(old => event.target.checked ? [...old, glyph.codepoint] : old.filter(cp => cp !== glyph.codepoint))} /></label>}
        </div>)}
      </div></div>)}
    </div>
    {selected.length > 0 && <div className="selection-bar"><span>{t("selectedCount", { count: selected.length })}</span><button disabled={review.isPending} aria-label={t("bulkAccept")} onClick={() => act(selected, "accept")}>{t("accepted")}</button><button disabled={review.isPending} aria-label={t("bulkReject")} onClick={() => act(selected, "reject")}>{t("rejected")}</button></div>}
    <footer className="review-footer"><p aria-label={t("statusCounts")}>{Object.entries(counts).map(([status, count]) => `${statusLabel[status as keyof typeof counts]} ${count}`).join(" · ")}</p>{buildCta}</footer>
  </section>;
}
