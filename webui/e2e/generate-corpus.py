"""Generate scans from the sidecar of a project created through the public UI."""

import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--data", type=Path, required=True)
parser.add_argument("--project", required=True)
parser.add_argument("--pdf", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / "packages/core/tests"))
sys.path.insert(0, str(repo / "packages/core/src"))
from corpus.generate import generate_corpus  # noqa: E402
from glyphlab.template.sidecar import read_sidecar  # noqa: E402
from PIL import Image  # noqa: E402

artifacts = args.data / "store/projects" / args.project / "artifacts"
sidecars = []
for candidate in artifacts.iterdir():
    try:
        value = json.loads(candidate.read_bytes())
    except (ValueError, UnicodeDecodeError):
        continue
    if isinstance(value, dict) and value.get("schema") == "glyphlab.template/1":
        sidecars.append(candidate)
if len(sidecars) != 1:
    raise RuntimeError(f"Expected one internal template sidecar, found {len(sidecars)}")
sidecar = read_sidecar(sidecars[0])
if len(sidecar.pages) < 2:
    raise RuntimeError("The hosted journey needs a two-page charset")
generate_corpus(args.pdf, sidecar, "clean-scan", [0, 1], 42, args.out)
Image.new("RGB", (2480, 3508), "white").save(args.out / "blank.jpg", quality=90)
print(json.dumps({"pages": [str(args.out / f"page-{n}.png") for n in (0, 1)]}))
