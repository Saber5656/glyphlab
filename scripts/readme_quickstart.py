"""Execute README's CLI fence with the built wheel and generated scan inputs."""

# ruff: noqa: S603, S607
# argv contains only checked-in README commands or test-owned temporary paths, never a shell.
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/core/tests"))
from corpus.generate import generate_corpus  # noqa: E402
from glyphlab.template.sidecar import read_sidecar  # noqa: E402


def main() -> None:
    source = (root / "README.md").read_text()
    section = source.split("<!-- quickstart-start:", 1)[1].split("<!-- quickstart-end -->", 1)[0]
    block = section.split("```bash", 1)[1].split("```", 1)[0]
    commands = [
        shlex.split(line)
        for line in block.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    wheels = sorted((root / "dist").glob("glyphlab-*.whl"), key=lambda path: path.stat().st_mtime)
    if not wheels:
        raise SystemExit("Build the glyphlab wheel first")
    with tempfile.TemporaryDirectory(prefix="glyphlab-readme-") as temp:
        work = Path(temp)
        venv = work / "venv"
        subprocess.run(["uv", "venv", str(venv)], check=True)
        python = venv / "bin/python"
        env = dict(os.environ, PATH=f"{venv / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")
        for command in commands:
            if command[:2] == ["pip", "install"]:
                subprocess.run(
                    ["uv", "pip", "install", "--python", str(python), f"{wheels[-1]}[trace,qa]"],
                    check=True,
                )
                continue
            if command[0] != "glyphlab":
                raise SystemExit(f"Unexpected README command: {command[0]}")
            subprocess.run(
                [str(venv / "bin/glyphlab"), *command[1:]], cwd=work, env=env, check=True
            )
            if command[-1] == "template":
                project = work / "myhand"
                generate_corpus(
                    project / "template/ascii.pdf",
                    read_sidecar(project / "template/template.json"),
                    "clean-scan",
                    None,
                    42,
                    project / "scans",
                )
        subprocess.run(
            [str(python), "-c", "import glyphlab; assert 'site-packages' in glyphlab.__file__"],
            cwd=work,
            env=env,
            check=True,
        )
    print("README quickstart passed using the installed wheel")


if __name__ == "__main__":
    main()
