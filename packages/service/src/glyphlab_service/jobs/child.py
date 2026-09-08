"""Pure core processing in a killable spawned child; never import DB/store."""

from datetime import UTC
from pathlib import Path
from tempfile import TemporaryDirectory

from .ipc import BuildResult, IngestRequest, IngestResult


def run_job_payload(req, progress=lambda stage: None):
    if isinstance(req, IngestRequest):
        return run_ingest(req, progress)
    return run_build(req, progress)


def run_ingest(req, progress):
    from glyphlab.charset import get_preset
    from glyphlab.ingest import ingest_scan
    from glyphlab.model import GlyphStatus
    from glyphlab.template.sidecar import read_sidecar
    from glyphlab.vectorize import select_engine

    class Sink:
        def __init__(self):
            self.svgs = {}
            self.metadata = {}

        def get_status(self, cp):
            return GlyphStatus(req.status_snapshot.get(cp, "missing"))

        def put_glyph(self, glyph, svg_bytes):
            self.svgs[glyph.codepoint] = svg_bytes
            self.metadata[glyph.codepoint] = {
                "advance": glyph.advance,
                "warnings": [str(w) for w in glyph.warnings],
            }

    charset = get_preset(req.charset_id)
    sink = Sink()
    with TemporaryDirectory(prefix="glyphlab-child-ingest-") as tmp:
        path = Path(tmp) / "template.json"
        path.write_bytes(req.sidecar_json)
        sidecar = read_sidecar(path, expected_charset=charset)
        engine = select_engine("potrace")

        # Mark the actual first trace invocation, not the entire ingest operation.
        class ProgressEngine:
            def __getattr__(self, name):
                return getattr(engine, name)

            def trace(self, *args, **kwargs):
                progress("trace")
                return engine.trace(*args, **kwargs)

        report = ingest_scan(
            req.upload_bytes,
            sidecar=sidecar,
            charset=charset,
            store=sink,
            engine=ProgressEngine(),
            force=False,
        )
        return IngestResult(report.to_dict(), sink.svgs, sink.metadata)


def run_build(req, progress):
    from datetime import datetime

    from glyphlab.charset import get_preset
    from glyphlab.fontbuild.builder import build_font
    from glyphlab.model import GlyphStatus, GlyphWarning
    from glyphlab.project.config import ProjectConfig
    from glyphlab.project.glyph_svg import read_glyph_svg
    from glyphlab.qa import ExpectedBuild, run_qa
    from glyphlab.report.proof import ProofMeta, generate_proof

    charset = get_preset(req.charset_id)
    project = ProjectConfig.model_validate(
        {
            "project": {
                "name": req.project_name or req.family_name,
                "family_name": req.family_name,
                "charset": req.charset_id,
                "version": req.version,
            }
        }
    )
    glyphs = {}
    with TemporaryDirectory(prefix="glyphlab-parse-") as parsed:
        for cp, svg in req.svgs.items():
            path = Path(parsed) / f"{cp}.svg"
            path.write_bytes(svg)
            glyphs[cp] = read_glyph_svg(path)
    progress("build")
    with TemporaryDirectory(prefix="glyphlab-child-build-") as tmp:
        result = build_font(project, glyphs, charset, Path(tmp))
        expected = ExpectedBuild(
            codepoints=set(glyphs) | {c.codepoint for c in charset.chars if not c.drawn},
            advances={cp: value[1] for cp, value in glyphs.items()},
        )
        qa = run_qa(result.ttf_path, charset, expected, require_bakery=True)
        woff = result.woff2_path.read_bytes()
        statuses = {
            c.codepoint: (
                GlyphStatus(req.statuses.get(c.codepoint, "missing")),
                [GlyphWarning(w) for w in req.warnings.get(c.codepoint, [])],
            )
            for c in charset.chars
            if c.drawn
        }
        counts = {
            s: sum(status == s for status in req.statuses.values())
            for s in ["missing", "auto", "accepted", "rejected"]
        }
        proof = generate_proof(
            Path(tmp) / "proof.html",
            woff2_bytes=woff,
            project=project,
            charset=charset,
            statuses=statuses,
            qa=qa,
            meta=ProofMeta(
                charset_id=charset.charset_id,
                charset_version=charset.version,
                version=req.version,
                built_at_iso=datetime.now(UTC).isoformat(),
                counts=counts,
            ),
        )
        return BuildResult(
            result.ttf_path.read_bytes(),
            woff,
            proof.read_bytes(),
            (Path(tmp) / "qa-report.json").read_bytes(),
            qa.passed,
        )
