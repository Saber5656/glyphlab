"""Self-contained, escaped proof sheets with no external assets."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from html import escape
from pathlib import Path

from glyphlab.charset.model import CharsetSpec
from glyphlab.model import GlyphStatus, GlyphWarning
from glyphlab.project.config import ProjectConfig
from glyphlab.qa.model import QAReport

IROHA = (
    "いろはにほへと ちりぬるを わかよたれそ つねならむ "
    "うゐのおくやま けふこえて あさきゆめみし ゑひもせす"
)
PANGRAM = "The quick brown fox jumps over the lazy dog 0123456789"
MIXED = "きょうは「Glyphlab」でフォントを作った。ローマ字とかなが、ひとつの文で・ながく・つづく！"


@dataclass(frozen=True)
class ProofMeta:
    charset_id: str
    charset_version: int
    version: int
    built_at_iso: str
    counts: dict[str, int]


def generate_proof(
    out_path: Path,
    *,
    woff2_bytes: bytes,
    project: ProjectConfig,
    charset: CharsetSpec,
    statuses: dict[int, tuple[GlyphStatus, list[GlyphWarning]]],
    qa: QAReport,
    meta: ProofMeta,
) -> Path:
    font = escape(base64.b64encode(woff2_bytes).decode("ascii"), quote=True)
    cells: list[str] = []
    missing: list[str] = []
    for char in charset.chars:
        status, warnings = statuses.get(char.codepoint, (GlyphStatus.MISSING, []))
        if not char.drawn:
            status = GlyphStatus.ACCEPTED
        state = escape(status.value, quote=True)
        label = f"U+{char.codepoint:04X}"
        badges = " ".join(
            f'<span title="{escape(w.value, quote=True)}">{escape(w.value, quote=True)}</span>'
            for w in warnings
        )
        glyph = f"&#x{char.codepoint:X};"
        if status in (GlyphStatus.MISSING, GlyphStatus.REJECTED):
            missing.append(f"{glyph} ({label})")
            glyph = "&#x25A1;"
        cells.append(
            f'<div class="glyph {state}"><div class="ink">{glyph}</div>'
            f"<code>{label}</code><small>{state}</small>{badges}</div>"
        )
    counts = ", ".join(f"{escape(k, quote=True)}: {v}" for k, v in sorted(meta.counts.items()))
    failures = ", ".join(
        escape(f.check_id, quote=True) for f in qa.findings if f.severity == "FAIL"
    )
    samples = "".join(
        f'<p class="sample" style="font-size:{size}px">{escape(sample, quote=True)}</p>'
        for sample in (IROHA, PANGRAM, MIXED)
        for size in (16, 24, 36)
    )
    document = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';
font-src data:; img-src data:">
<title>Glyphlab font proof</title><style>
@font-face {{font-family:"GlyphlabProof";src:url(data:font/woff2;base64,{font})}}
body {{margin:2rem auto;max-width:1100px;
padding:1rem;color:#253229;background:#fbfaf4;font-family:system-ui,sans-serif}}
h1 {{font-size:2rem}}
.grid {{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:10px}}
.glyph {{border:1px solid #ccc;border-radius:8px;padding:10px;overflow-wrap:anywhere}}
.ink {{font:42px GlyphlabProof}} small {{display:block}}
.sample {{font-family:GlyphlabProof;line-height:1.6}}
.accepted {{border-color:#52946d}} .auto {{border-color:#577eb8}}
.rejected {{border-color:#b85757;text-decoration:line-through}}
.missing {{color:#777}} span {{font-size:9px}}
</style></head><body>
<h1>{escape(project.project.name, quote=True)}</h1>
<p>{escape(project.project.family_name, quote=True)} ·
{escape(meta.charset_id, quote=True)}@{meta.charset_version} · v{meta.version} ·
{escape(meta.built_at_iso, quote=True)}</p>
<p>{counts}</p><p>QA: {"PASS" if qa.passed else "FAIL"} {failures}</p>
<section class="grid">{"".join(cells)}</section><h2>Samples</h2>
<p>Historical kana ゐ/ゑ in the iroha sample may be missing from the selected preset.</p>{samples}
<h2>Missing or rejected</h2><p>{", ".join(missing) or "None"}</p>
<footer>The font and handwriting belong to their author.
Glyphlab claims no rights over generated fonts.</footer>
</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")
    return out_path
