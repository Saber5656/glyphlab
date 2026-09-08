import sys
from pathlib import Path
from uuid import UUID

import pytest
from glyphlab.charset import get_preset
from glyphlab.template import generate_template
from glyphlab.template.sidecar import read_sidecar

# The corpus is test-only and intentionally not part of the installed wheel.
sys.path.insert(0, str(Path(__file__).parents[1]))
from corpus.generate import generate_corpus


@pytest.fixture(scope="session")
def template_fixture(tmp_path_factory):
    charset = get_preset("ja-basic-v1")
    artifacts = generate_template(
        tmp_path_factory.mktemp("template"), charset, UUID(int=42), "Corpus validation"
    )
    return charset, artifacts, read_sidecar(artifacts.sidecar_path)


@pytest.fixture(scope="session")
def corpus_page(template_fixture, tmp_path_factory):
    cache = {}

    def make(profile="clean-scan", page=0, fill_fraction=1.0):
        key = (profile, page, fill_fraction)
        if key not in cache:
            _, artifacts, sidecar = template_fixture
            directory = tmp_path_factory.mktemp(profile)
            manifests = generate_corpus(
                artifacts.pdf_path,
                sidecar,
                profile,
                [page],
                42,
                directory,
                fill_fraction,
            )
            image = directory / f"page-{page}.{'png' if profile == 'clean-scan' else 'jpg'}"
            import json

            cache[key] = (image.read_bytes(), json.loads(manifests[0].read_text()))
        return cache[key]

    return make
