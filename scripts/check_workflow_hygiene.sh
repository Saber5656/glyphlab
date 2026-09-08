#!/usr/bin/env bash
set -euo pipefail
python3 - "$@" <<'PY'
import pathlib,re,sys
paths = [pathlib.Path(p) for p in sys.argv[1:]] or sorted(pathlib.Path('.github/workflows').glob('*.yml'))
errors = []
for path in paths:
    text=path.read_text()
    for action in re.findall(r'uses:\s*([^\s#]+)',text):
        if not re.fullmatch(r'[\w./-]+@[0-9a-f]{40}',action):
            errors.append(f'{path}: action must be SHA-pinned: {action}')
    if not re.search(r'^permissions:\n  contents: read\s*$',text,re.M):
        errors.append(f'{path}: top-level contents: read permission required')
    if 'secrets.' in text:
        errors.append(f'{path}: secret references are not permitted')
if errors:
    print('\n'.join(errors),file=sys.stderr)
    sys.exit(1)
print(f'Workflow hygiene passed ({len(paths)} files)')
PY
