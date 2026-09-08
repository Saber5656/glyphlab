from html.parser import HTMLParser

from glyphlab.charset.model import CharDef, CharsetSpec
from glyphlab.model import GlyphStatus, GlyphWarning
from glyphlab.project.config import ProjectConfig
from glyphlab.qa.model import QAReport
from glyphlab.report.proof import ProofMeta, generate_proof


def test_escaped_self_contained_grid(tmp_path):
    project = ProjectConfig.model_validate(
        {
            "project": {
                "name": '<script>alert(1)</script>"',
                "family_name": "Proof",
                "charset": "ascii",
            }
        }
    )
    charset = CharsetSpec("tiny", 1, (CharDef(65, "latin", True), CharDef(66, "latin", True)))
    path = generate_proof(
        tmp_path / "proof.html",
        woff2_bytes=b"font",
        project=project,
        charset=charset,
        statuses={65: (GlyphStatus.ACCEPTED, [GlyphWarning.LOW_INK])},
        qa=QAReport(True, []),
        meta=ProofMeta("tiny", 1, 1, "2026-01-01T00:00:00Z", {"accepted": 1, "missing": 1}),
    )
    text = path.read_text()
    assert "<script" not in text.lower()
    assert text.count("&lt;script&gt;alert(1)&lt;/script&gt;&quot;") == 1
    assert "Content-Security-Policy" in text
    assert text.count('class="glyph ') == 2
    assert "LOW_INK" in text
    assert "U+0042" in text

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert all(v.startswith("data:") for k, v in attrs if k in ("src", "href"))

    Links().feed(text)
