# glyphlab
[![CI](https://github.com/Saber5656/glyphlab/actions/workflows/ci.yml/badge.svg)](https://github.com/Saber5656/glyphlab/actions/workflows/ci.yml)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Create your own handwriting font from paper templates. Local CLI and self-hosted web app.

手書き文字から自分のフォントを作るパイプライン。

1. **印刷して書く** — PDFの見本用紙を100%倍率で印刷し、マスに文字を書く。
2. **撮って送る** — スキャンや写真から文字を抽出し、一覧で採用・却下する。
3. **フォントを受け取る** — 品質検査を通したTTF・WOFF2と見本HTMLを保存する。

| できること | v1の範囲 |
| --- | --- |
| 文字セット | 英数字95文字、かな183文字、組み合わせ278文字（手書き276文字・6枚） |
| 入力 | JPEG・PNG・HEIC、1枚12 MiB/36 MPまで |
| 出力 | TTF、WOFF2、自己完結したHTML見本、品質レポート |
| 利用方法 | ローカルCLI、日本語Web UI、Docker自己ホスト |
| 今後の対象 | 漢字セット、ブラウザ手書き、AI補完、縦書き、字形編集、アカウント |

実際の手書き品質はペンや撮影条件で変わります。[印刷・撮影ガイド](docs/guide/printing.md)を参照してください。
自動検証は合成スキャンで行い、実際の手書き一式での確認は初回利用時に行ってください。

## Webで使う

公開サービスのURLは運営者が案内します。このリポジトリから本番サービスは自動公開されません。
自己ホストの場合は `http://localhost:8080` を開きます。

1. プロジェクトを作成し、表示された秘密リンクを保存する。
2. テンプレートをダウンロードし、印刷・記入する。
3. 写真をアップロードし、抽出結果を確認する。
4. フォントを生成し、TTFをダウンロードする。

アカウントは不要です。秘密リンクを失うと復旧できません。手書き画像は処理後に削除し、
抽出データとフォントは最終アクセスから標準14日で削除します。設定は運営者が変更できます。

## CLI quickstart

Python 3.11以降を使用します。macOSでネイティブトレースを使う場合は先に
`brew install potrace` を実行してください。`trace` extraはPython版の代替です。

初回PyPI公開前は `uv build --package glyphlab` でwheelを作り、そのwheelをインストールしてください。
以下のPyPIコマンドはリリース後の形です。

<!-- quickstart-start: validation substitutes the PyPI install with dist/glyphlab-*.whl[trace,qa]
and supplies synthetic scans after the template step; all glyphlab commands run from that installed wheel. -->
```bash
pip install 'glyphlab[trace,qa]'
glyphlab new MyHand --family-name MyHand --charset ascii --dir myhand
glyphlab --project myhand template
# Print at 100%, write, and place JPEG/PNG/HEIC files in myhand/scans/.
glyphlab --project myhand ingest
glyphlab --project myhand status
glyphlab --project myhand accept --all-auto
glyphlab --project myhand build
```
<!-- quickstart-end -->

成果物は `myhand/build/MyHand-v1.ttf`、`.woff2`、`proof.html`、`qa-report.json` です。
検証用スキャンでは取り込みに `coverage: 92/94 drawn glyphs have sources`、生成に `QA: PASS`
と表示されます。手書きの場合は空欄や却下に応じて文字数が変わります。

通常の生成ではFont Bakeryも必須です。`--skip-bakery` はローカル確認用で、構造検査は省略しません。
詳しいオプションは [CLIガイド](docs/guide/cli.md) を参照してください。

## 自己ホスト

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

`http://localhost:8080` にアクセスします。停止・更新・バックアップは
[自己ホストガイド](docs/guide/self-host.md)、Fly.ioの準備は [運用手順](deploy/RUNBOOK.md) を参照してください。

## 開発と検証

[CONTRIBUTING.md](CONTRIBUTING.md)、[設計](docs/DESIGN.md)、[実装計画](docs/ISSUE_PLAN.md)、
[受入結果](docs/ACCEPTANCE.md) を参照してください。

## ライセンス

コードは [MIT](LICENSE) です。**生成したフォントと手書き文字の権利はあなたのものです。**
glyphlabは生成フォントの権利を主張しません。

potraceはGPL-2ライセンスの独立した実行プログラムとして呼び出します。Python代替実装を含む
境界は [ADR-004](docs/decisions/ADR-004-vectorization-potrace-subprocess.md) に記載しています。
テスト用Klee Oneフォントは同梱のSIL OFL 1.1に従い、生成物やwheelには含めません。
