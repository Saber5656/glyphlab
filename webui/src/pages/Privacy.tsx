import { Link } from "react-router-dom";
import { t } from "../i18n/ja";
export default function Privacy() { return <main className="shell"><Link to="/" className="brand">glyphlab</Link><article className="card prose"><h1>{t("privacy")}</h1><p>glyphlabは、手書き文字をフォントに変換するために必要なデータだけを扱います。</p><h2>保存するデータ</h2><p>手書き画像は処理が終わるとすぐに削除します。抽出データとフォントは最終アクセスから14日で自動削除されます。</p><h2>アクセスと削除</h2><p>アカウント、アクセス解析、第三者への送信はありません。レート制限のためIPアドレスを最大7日間、 abuse logに保存します。プロジェクト画面の「今すぐ削除」からいつでも削除できます。</p><h2>セルフホスト</h2><p>自分で管理する場合は、保存先と保持期間を運用環境に合わせて設定できます。</p><Link to="/">トップに戻る</Link></article></main>; }
