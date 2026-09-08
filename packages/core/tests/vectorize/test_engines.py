import numpy as np
import pytest
from glyphlab.errors import GlyphlabError
from glyphlab.vectorize import TraceOpts, select_engine


@pytest.mark.parametrize("name", ["potrace", "potracer"])
def test_ring_has_closed_contours(name):
    yy, xx = np.mgrid[:80, :80]
    bitmap = ((xx - 40) ** 2 + (yy - 40) ** 2 < 30**2) & ((xx - 40) ** 2 + (yy - 40) ** 2 > 15**2)
    contours = select_engine(name).trace(bitmap, TraceOpts())
    assert len(contours) == 2
    assert all(c.segments[0].p1 == c.segments[-1].p2 for c in contours)


def test_missing_engines():
    def missing():
        raise ImportError

    with pytest.raises(GlyphlabError) as e:
        select_engine("auto", _which=lambda _: None, _import_potracer=missing)
    assert e.value.code == "E_TRACE_UNAVAILABLE"
    assert "brew install potrace" in str(e.value)
