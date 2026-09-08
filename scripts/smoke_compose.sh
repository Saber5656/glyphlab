#!/usr/bin/env bash
set -euo pipefail
CID=$(docker compose -f deploy/docker-compose.yml ps -q)
docker inspect "$CID" --format '{{.Config.User}}' | grep -q 10001
docker inspect "$CID" --format '{{.HostConfig.ReadonlyRootfs}}' | grep -q true
docker inspect "$CID" --format '{{.HostConfig.CapDrop}}' | grep -qi all
docker compose -f deploy/docker-compose.yml exec -T app potrace --version
python3 - <<'PY'
import json,urllib.request
base='http://localhost:8080'
assert urllib.request.urlopen(base+'/healthz',timeout=10).status==200
assert b'<html' in urllib.request.urlopen(base+'/',timeout=10).read().lower()
req=urllib.request.Request(base+'/api/projects',data=json.dumps({'name':'Smoke','family_name':'Smoke','charset_id':'ascii'}).encode(),headers={'Content-Type':'application/json'})
project=json.load(urllib.request.urlopen(req,timeout=10))
url=base+'/api/projects/'+project['project_id']
headers={'Authorization':'Bearer '+project['token']}
pdf=urllib.request.urlopen(urllib.request.Request(url+'/template.pdf',headers=headers),timeout=30).read()
assert pdf.startswith(b'%PDF')
assert urllib.request.urlopen(urllib.request.Request(url,headers=headers,method='DELETE'),timeout=10).status in (200,204)
print('Compose smoke passed: health, SPA, project, authenticated template, deletion')
PY
