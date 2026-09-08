import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest
from glyphlab.errors import GlyphlabError
from glyphlab.ingest import ingest_scan
from glyphlab.model import GlyphStatus
from glyphlab.vectorize import select_engine


class MemorySink:
    def __init__(self):
        self.glyphs = {}
        self.svgs = {}

    def get_status(self, cp):
        return self.glyphs[cp].status if cp in self.glyphs else GlyphStatus.MISSING

    def put_glyph(self, glyph, svg_bytes):
        self.glyphs[glyph.codepoint] = glyph
        self.svgs[glyph.codepoint] = svg_bytes


@pytest.mark.parametrize("profile", ["clean-scan", "phone-tilt"])
def test_real_pipeline_and_review_policy(corpus_page, template_fixture, profile):
    charset, _, sidecar = template_fixture
    data, manifest = corpus_page(profile)
    sink = MemorySink()
    engine = select_engine("potrace")
    report = ingest_scan(data, sidecar=sidecar, charset=charset, store=sink, engine=engine)
    assert report.counts == {
        "extracted": 48,
        "empty": 1,
        "skipped_accepted": 0,
        "failed": 0,
    }
    assert {f"U+{cp:04X}" for cp in sink.glyphs} == set(manifest["inked"])
    schema = json.loads(
        (Path(__file__).parents[2] / "src/glyphlab/ingest/report.schema.json").read_text()
    )
    jsonschema.validate(report.to_dict(), schema)
    cp = next(iter(sink.glyphs))
    sink.glyphs[cp] = replace(sink.glyphs[cp], status=GlyphStatus.ACCEPTED)

    class FailingEngine:
        name = "timeout"

        def trace(self, *_):
            raise GlyphlabError("E_TRACE_TIMEOUT", "Injected timeout")

    report = ingest_scan(data, sidecar=sidecar, charset=charset, store=sink, engine=FailingEngine())
    assert report.counts["skipped_accepted"] == 1 and report.counts["failed"] == 47
    report = ingest_scan(
        data, sidecar=sidecar, charset=charset, store=sink, engine=engine, force=True
    )
    assert report.counts["extracted"] == 48 and sink.get_status(cp) == GlyphStatus.AUTO
