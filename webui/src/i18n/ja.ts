import codes from "../generated/error-codes.json";
export const errorMessages = {
  E_IMG_FORMAT: "対応していない画像形式です。JPEG・PNG・HEICでアップロードしてください", E_IMG_TOO_LARGE: "画像が大きすぎます。12MB・3600万画素以内にしてください", E_REQUEST_TOO_LARGE: "リクエストが大きすぎます", E_IMG_DECODE: "画像を読み込めませんでした。別の写真で試してください", E_PAGE_NO_MARKERS: "四隅のマーカーが見つかりません。ページ全体が写るように撮り直してください", E_PAGE_AMBIGUOUS: "複数のページが写っています。1枚ずつ撮影してください", E_PAGE_UNKNOWN: "このプロジェクトのテンプレートではないページです", E_PAGE_WARPED: "用紙の歪みが大きすぎます。平らな場所で真上から撮り直してください", E_PAGE_BLURRY: "写真がぶれています。明るい場所で、ページ全体が入るように撮り直してください", E_TEMPLATE_MISMATCH: "テンプレートが現在の設定と一致しません", E_TRACE_UNAVAILABLE: "サーバー内部エラー（変換エンジン未設定）。時間をおいて再試行してください", E_TRACE_TIMEOUT: "処理が時間内に終わりませんでした。画像を確認して再試行してください", E_GLYPH_SVG_INVALID: "グリフデータが不正です", E_QA_FAILED: "フォントの品質チェックに失敗しました。レポートを確認してください", E_NOT_FOUND: "プロジェクトが見つからないか、リンクが無効・期限切れです", E_RATE_LIMITED: "アクセスが集中しています。しばらく待って再試行してください", E_QUOTA_EXCEEDED: "容量または回数の上限に達しました", E_JOB_LOST: "処理が中断されました。もう一度お試しください", E_BUILD_IN_PROGRESS: "フォント生成がすでに実行中です。完了をお待ちください", E_VALIDATION: "入力内容に誤りがあります", E_INTERNAL: "サーバーエラーが発生しました。時間をおいて再試行してください",
} as const satisfies Record<(typeof codes)[number], string>;
export const warnings = { LOW_INK: "インクが薄い", TOUCHES_BORDER: "枠に接触", TINY_CONTOURS_REMOVED: "微小なゴミを除去", LARGE_INK_BLOB: "インクが多すぎる可能性", OFF_GUIDE: "ガイド外（自動調整済み）" } as const;
export const ja = {
  brand: "glyphlab", tagline: "手書き文字から、自分だけのフォントを作る", create: "プロジェクトを作る", open: "既存のプロジェクトを開く", name: "プロジェクト名", familyName: "フォント名", charset: "文字セット", submit: "作成する", cancel: "キャンセル", loading: "読み込み中…", privacy: "プライバシー", upload: "書いてアップロード", review: "文字を確認", build: "フォントを生成", template: "テンプレートを印刷", saveToken: "このリンクを保存してください", tokenWarning: "このリンクを失うとプロジェクトは開けません。ブックマークかメモに保存してください", copied: "コピーしました", errorFallback: "エラーが発生しました（{code}）", sample: "きょうは「Glyphlab」でフォントを作った。手書きの文字が、そのまま自分のフォントになる。",
} as const;
export type MsgKey = keyof typeof ja;
export function t(key: MsgKey, params: Record<string, string | number> = {}): string { return ja[key].replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`)); }
export function errorText(code: string): string { return errorMessages[code as keyof typeof errorMessages] ?? t("errorFallback", { code }); }
export function warningText(code: string): string { return warnings[code as keyof typeof warnings] ?? code; }
