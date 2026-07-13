# Research: Comparable Products

- Date: 2026-07-08
- Status: informs DESIGN.md §1–§2 (product definition, scope) and the template/review UX

## Question

What do existing handwriting-to-font products do, and where does glyphlab differentiate?

## Calligraphr (closest comparable, hosted SaaS)

Workflow: download PDF/PNG template → print → fill cells with pen → scan or photograph → upload
→ automatic extraction → adjust per-glyph size/baseline in web UI → export TTF/OTF.

Observed characteristics (docs/FAQ/tutorials, retrieved 2026-07-08):

| Aspect | Calligraphr behavior | glyphlab v1 response |
|---|---|---|
| Template | Grid with in-cell helper guides; cell size configurable; PDF or PNG | Same concept; fixed A4 geometry v1; **ArUco fiducial markers** for robust phone-photo rectification (Calligraphr relies on plain grid detection and struggles with skewed photos) |
| Account model | Account required; free tier capped at 75 glyphs, 2 variants | **No account**; anonymous token project; no glyph-count cap (charset preset defines size) |
| Glyph editing | No editing of extracted glyphs (delete + re-upload only) | Local CLI keeps **editable SVG intermediates** — users can fix a glyph in any SVG editor and rebuild |
| Variants/ligatures | Pro feature (randomized alternates, ligatures) | **v2 deferred** (OpenType `calt`/`rand`); v1 explicitly one glyph per codepoint |
| Japanese support | Latin-centric; kana possible via custom charsets but not first-class | **Kana first-class**: dedicated preset, square-guide cells for kana vs baseline cells for Latin, full-width advance rules |
| Smoothing/AI | No auto-smoothing, no AI completion | Same posture in v1 (deterministic); AI completion is an explicit v2 extension hook |
| Openness | Closed SaaS | MIT OSS, local-first CLI + self-hostable + hosted |

## Other tools (brief)

- **FontForge autotrace flow**: powerful but expert-oriented; no template/scan workflow; GUI
  desktop app. Not a workflow competitor, but its existence justifies exporting clean TTFs that
  remain editable in FontForge.
- **FontCraft and similar newer web tools**: AI-assisted cleanup, browser drawing input.
  Confirms browser-canvas input (our v2) is a market expectation, not a v1 requirement.
- **iPad handwriting apps** (e.g. iFontMaker): direct stylus input, no paper. Covered by our v2
  digital-input adapter.

## Implications for glyphlab

1. The paper template with printed fiducials is the single biggest robustness differentiator we
   can ship in v1 — phone-photo rectification must be a first-class requirement, not an
   afterthought (DESIGN §8).
2. "No account, auto-expiring project" is both a privacy feature and a scope reducer vs
   Calligraphr's account system.
3. Editable SVG intermediates in the local project directory are a real differentiator for the
   CLI persona; the storage layout must treat `glyphs/*.svg` as user-editable canonical inputs
   (DESIGN §12).
4. A per-glyph review step (accept/reject) is table stakes; per-glyph *editing* in the web UI is
   not (v2).

## Sources

- https://www.calligraphr.com/en/docs/faq/ and https://www.calligraphr.com/en/docs/tutorial1/
- https://fontcraft.app/blog/calligraphr-alternative
- https://www.podfeet.com/blog/2022/06/calligrapher/ (workflow walk-through)
