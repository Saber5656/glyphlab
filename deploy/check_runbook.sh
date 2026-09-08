#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import ast,pathlib,re
settings=ast.parse(pathlib.Path('packages/service/src/glyphlab_service/settings.py').read_text())
fields={f'GLYPHLAB_{node.target.id.upper()}' for cls in settings.body if isinstance(cls,ast.ClassDef) and cls.name=='Settings' for node in cls.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name)}
runbook=pathlib.Path('deploy/RUNBOOK.md').read_text()
guide=pathlib.Path('docs/guide/self-host.md').read_text()
texts=runbook+pathlib.Path('deploy/fly.toml').read_text()+guide
documented=set(re.findall(r'`(GLYPHLAB_[A-Z0-9_]+)`',guide))
if documented != fields:raise SystemExit(f'Environment documentation drift: {sorted(documented ^ fields)}')
unknown=set(re.findall(r'GLYPHLAB_[A-Z0-9_]+',texts))-fields
if unknown:raise SystemExit(f'Unknown settings: {sorted(unknown)}')
for heading in ('First deploy','Custom domain','Upgrades','Storage growth','Backup & restore','Incident playbooks','Cost'):
    if f'## {heading}' not in runbook:raise SystemExit(f'Missing heading: {heading}')
if runbook.count('**[HUMAN]**')<6:raise SystemExit('Missing operator steps')
if len(re.findall(r'^### [1-4]\. ',runbook,re.M))!=4:raise SystemExit('Expected four incident playbooks')
if re.search(r'glp_[A-Za-z0-9_\-]{20,}|AKIA[0-9A-Z]{16}',texts):raise SystemExit('Potential secret in runbook')
print('Runbook checks passed')
PY
