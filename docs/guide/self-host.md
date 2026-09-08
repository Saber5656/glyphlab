# セルフホスト

Docker Engine と Compose v2 が必要です。リポジトリのルートで実行します。

```bash
docker compose -f deploy/docker-compose.yml up -d --build --wait
```

`http://localhost:8080` を開きます。`/healthz` は DB とストアを確認します。
データは named volume に保持されます。アプリは非 root・読み取り専用ルートで動作し、
一時処理には `/tmp`、永続データには `/data` を使います。外部公開時は TLS を終端する
リバースプロキシを用意し、アプリポートへの直接アクセスを制限してください。

## 環境変数

設定値は Compose の `environment` か Git 管理外の環境ファイルから渡します。
`.env` を置くだけでは任意の変数がコンテナへ転送されるわけではありません。
以下は `Settings` の既定値です。ストレージや認証情報はログへ出さないでください。

| 変数 | 既定値 | 意味 |
|---|---|---|
| `GLYPHLAB_DATA_DIR` | `/data` | DB・ローカルストアの親 |
| `GLYPHLAB_DATABASE_URL` | `""` | 空欄なら DATA_DIR/glyphlab.db の SQLite。PostgreSQL URL も使用可能 |
| `GLYPHLAB_OBJECT_STORE` | `local` | `local` または `s3` |
| `GLYPHLAB_S3_ENDPOINT_URL` | `""` | S3互換エンドポイント |
| `GLYPHLAB_S3_BUCKET` | `""` | 保存バケット |
| `GLYPHLAB_S3_REGION` | `""` | S3リージョン |
| `GLYPHLAB_S3_ACCESS_KEY_ID` | `""` | S3アクセスキー（秘密情報） |
| `GLYPHLAB_S3_SECRET_ACCESS_KEY` | `""` | S3シークレット（秘密情報） |
| `GLYPHLAB_RETENTION_DAYS` | `14.0` | 最終アクセスからの保存日数。正の小数も可 |
| `GLYPHLAB_PUBLIC_BASE_URL` | `""` | 公開ベースURL |
| `GLYPHLAB_ENVIRONMENT` | `prod` | `dev` のみ開発用 CORS を許可 |
| `GLYPHLAB_TRUST_PROXY_HEADERS` | `false` | 信頼できるプロキシのみが直接接続する場合に有効化 |
| `GLYPHLAB_CORS_DEV_ORIGIN` | `http://localhost:5173` | 開発SPAの origin |
| `GLYPHLAB_MAX_UPLOAD_BYTES` | `12582912` | ファイル上限12 MiB |
| `GLYPHLAB_MAX_UPLOAD_REQUEST_BYTES` | `13631488` | multipartリクエスト全体上限13 MiB |
| `GLYPHLAB_MAX_JSON_BODY_BYTES` | `65536` | JSONリクエスト上限 |
| `GLYPHLAB_MAX_UPLOADS_PER_PROJECT` | `40` | プロジェクト内アップロード数上限 |
| `GLYPHLAB_MAX_PROJECT_STORAGE_BYTES` | `104857600` | プロジェクト保存量上限100 MiB |
| `GLYPHLAB_MAX_QUEUED_JOBS_PER_PROJECT` | `5` | プロジェクトの待機ジョブ上限 |
| `GLYPHLAB_MAX_STORE_BYTES` | `5368709120` | 全ストア上限5 GiB |
| `GLYPHLAB_JOB_CONCURRENCY` | `1` | 同時処理数（1–16） |
| `GLYPHLAB_JOB_TIMEOUT_S` | `150` | ジョブ処理時間上限（秒） |
| `GLYPHLAB_SWEEP_INTERVAL_S` | `3600` | 期限切れ削除の走査間隔（秒） |
| `GLYPHLAB_RL_CREATE_PER_MINUTE` | `3` | IP別作成回数/分 |
| `GLYPHLAB_RL_CREATE_PER_DAY` | `10` | IP別作成回数/日 |
| `GLYPHLAB_RL_UPLOADS_PER_HOUR_IP` | `40` | IP別アップロード回数/時 |
| `GLYPHLAB_RL_UPLOADS_PER_HOUR_PROJECT` | `20` | プロジェクト別アップロード回数/時 |
| `GLYPHLAB_RL_BUILDS_PER_HOUR_PROJECT` | `10` | プロジェクト別ビルド回数/時 |
| `GLYPHLAB_RL_DEFAULT_PER_MINUTE` | `120` | 認証APIのIP別回数/分 |
| `GLYPHLAB_WEBUI_DIST` | `/app/webui-dist` | 配信するSPAビルド |

ストアの読み書きと DB 接続に必要な最小権限を与えてください。S3は既定で非公開とし、
API経由で認証して配信します。小規模運用は単一インスタンス、SQLite、ローカルストアが基本です。

## バックアップと更新

SQLite運用ではアプリを停止して DB とストアを同時にバックアップします。
バックアップにも手書きデータが含まれるので、アクセス制限と削除期限を運用者が管理します。

```bash
docker compose -f deploy/docker-compose.yml stop
# ボリューム全体をバックアップ（環境のバックアップツールを使用）
docker compose -f deploy/docker-compose.yml up -d --build --wait
```

復元時は停止中に同じ組の DB とストアを戻し、コンテナ uid 10001 が読書きできる状態にします。
更新前にバックアップを取り、起動時の Alembic migration と `/healthz` を確認します。
スキーマが変わった更新を戻す際は、旧イメージと対応するバックアップを一緒に復元してください。
`down -v` は永続データを削除するため、通常停止には使用しません。

Fly.io の初回設定、TLS、障害対応、費用確認は [RUNBOOK](../../deploy/RUNBOOK.md) を参照してください。
公開URL、契約、秘密値の投入、本番公開は運用者の判断と操作が必要です。
