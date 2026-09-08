from glyphlab.qa.bakery import parse_bakery_report, run_fontbakery


def test_parse_real_schema():
    report = {
        "sections": [
            {
                "checks": [
                    {
                        "key": {"check": "test/check"},
                        "logs": [{"status": "FAIL", "message": "bad shape"}],
                    }
                ]
            }
        ]
    }
    findings = parse_bakery_report(report, {})
    assert findings[0].severity == "FAIL"
    assert findings[0].check_id == "test/check"
    assert (
        parse_bakery_report(report, {"test/check": "Test justification"})[0].severity == "ALLOWED"
    )


def test_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("glyphlab.qa.bakery.shutil.which", lambda _: None)
    assert run_fontbakery(tmp_path / "a.ttf", require_bakery=False)[0].severity == "SKIPPED"
    f = run_fontbakery(tmp_path / "a.ttf", require_bakery=True)[0]
    assert f.severity == "FAIL"
    assert "glyphlab[qa]" in f.message


def test_fontbakery_110_serialized_key_and_message():
    data = {
        "sections": [
            {
                "key": ["Universal", None, None],
                "checks": [
                    {
                        "key": ["Universal", "<FontBakeryCheck:contour_count>", [["font", 0]]],
                        "result": "FAIL",
                        "logs": [
                            {
                                "status": "FAIL",
                                "message": {"code": "empty", "message": "Empty contour"},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    findings = parse_bakery_report(data, {})
    assert findings[0].check_id == "contour_count"
    assert findings[0].message == "Empty contour"


def test_real_bakery_gate_and_report_schema(golden_font, golden_inputs):
    import json
    from pathlib import Path

    import jsonschema
    from glyphlab.qa import ExpectedBuild, run_qa

    _, glyphs, charset = golden_inputs
    advances = {cp: advance for cp, (_, advance) in glyphs.items()} | {32: 500, 0x3000: 1000}
    report = run_qa(
        golden_font.ttf_path, charset, ExpectedBuild(set(advances), advances), require_bakery=True
    )
    assert report.passed, [(f.check_id, f.message) for f in report.findings if f.severity == "FAIL"]
    schema = Path(__file__).parents[2] / "src/glyphlab/qa/report.schema.json"
    data = json.loads((golden_font.ttf_path.parent / "qa-report.json").read_text())
    jsonschema.validate(data, json.loads(schema.read_text()))
    assert [f.check_id for f in report.findings] == sorted(f.check_id for f in report.findings)
