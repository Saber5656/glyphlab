import codes from "../generated/error-codes.json";
export const errorMessages = {
    E_IMG_FORMAT:
        "対応していない画像形式です。JPEG・PNG・HEICでアップロードしてください",
    E_IMG_TOO_LARGE: "画像が大きすぎます。12MB・3600万画素以内にしてください",
    E_REQUEST_TOO_LARGE: "リクエストが大きすぎます",
    E_IMG_DECODE: "画像を読み込めませんでした。別の写真で試してください",
    E_PAGE_NO_MARKERS:
        "四隅のマーカーが見つかりません。ページ全体が写るように撮り直してください",
    E_PAGE_AMBIGUOUS: "複数のページが写っています。1枚ずつ撮影してください",
    E_PAGE_UNKNOWN: "このプロジェクトのテンプレートではないページです",
    E_PAGE_WARPED:
        "用紙の歪みが大きすぎます。平らな場所で真上から撮り直してください",
    E_PAGE_BLURRY:
        "写真がぶれています。明るい場所で、ページ全体が入るように撮り直してください",
    E_TEMPLATE_MISMATCH: "テンプレートが現在の設定と一致しません",
    E_TRACE_UNAVAILABLE:
        "サーバー内部エラー（変換エンジン未設定）。時間をおいて再試行してください",
    E_TRACE_TIMEOUT:
        "処理が時間内に終わりませんでした。画像を確認して再試行してください",
    E_GLYPH_SVG_INVALID: "グリフデータが不正です",
    E_QA_FAILED:
        "フォントの品質チェックに失敗しました。レポートを確認してください",
    E_NOT_FOUND: "プロジェクトが見つからないか、リンクが無効・期限切れです",
    E_RATE_LIMITED:
        "アクセスが集中しています。しばらく待って再試行してください",
    E_QUOTA_EXCEEDED: "容量または回数の上限に達しました",
    E_JOB_LOST: "処理が中断されました。もう一度お試しください",
    E_BUILD_IN_PROGRESS: "フォント生成がすでに実行中です。完了をお待ちください",
    E_VALIDATION: "入力内容に誤りがあります",
    E_INTERNAL: "サーバーエラーが発生しました。時間をおいて再試行してください",
} as const satisfies Record<(typeof codes)[number], string>;
export const warnings = {
    LOW_INK: "インクが薄い",
    TOUCHES_BORDER: "枠に接触",
    TINY_CONTOURS_REMOVED: "微小なゴミを除去",
    LARGE_INK_BLOB: "インクが多すぎる可能性",
    OFF_GUIDE: "ガイド外（自動調整済み）",
} as const;
export const ja = {
    brand: "glyphlab",
    heroEyebrow: "手書きからフォントへ",
    charsetOption: "{id}（{count}字・{pages}ページ）",
    nameInvalid: "前後の空白・制御文字を含まない1〜64文字で入力してください",
    tokenSessionOnly: "このブラウザには保存できませんでした。閉じる前にリンクをコピーして保管してください",
    tokenAutosaved: "このブラウザにもアクセス情報を保存しました",
    tokenNeeded: "保存したリンク、またはアクセストークンを入力してください",
    familyHelp: "半角英数字・スペース・ハイフンで31文字以内。先頭は英数字にしてください",
    copyFailed: "コピーできませんでした。リンクを選択して保存してください",
    expires: "有効期限: {date}",
    uploadTotal: "すべてのページを取り込むと{count}字",
    uploadCounts: "抽出 {extracted} / 空欄 {empty} / スキップ {skipped} / 失敗 {failed}",
    deduplicated: "アップロード済みのページです",
    queueFull: "待機・処理中の画像は最大6ファイルです",
    technicalCode: "エラーコード",
    pollRetry: "処理状況を再取得",
    uploadProgress: "アップロード {percent}%",

    tagline: "手書き文字から、自分だけのフォントを作る",
    create: "プロジェクトを作る",
    open: "既存のプロジェクトを開く",
    name: "プロジェクト名",
    familyName: "フォント名",
    charset: "文字セット",
    submit: "作成する",
    cancel: "キャンセル",
    loading: "読み込み中…",
    privacy: "プライバシー",
    upload: "書いてアップロード",
    review: "文字を確認",
    build: "フォントを生成",
    template: "テンプレートを印刷",
    saveToken: "このリンクを保存してください",
    tokenWarning:
        "このリンクを失うとプロジェクトは開けません。ブックマークかメモに保存してください",
    copied: "コピーしました",
    errorFallback: "エラーが発生しました（{code}）",
    sample: "きょうは「Glyphlab」でフォントを作った。ローマ字とかなが、ひとつの文で・ながく・つづく！",
    copyLink: "リンクをコピー",
    closeSaved: "保存したので閉じる",
    inputInvalid: "入力内容を確認してください",
    linkInvalid: "プロジェクトURLまたはトークンを確認してください",
    sharedLink: "共有リンク",
    openButton: "開く",
    linkPlaceholder: "https://…/p/…#t=glp_…",
    heroDescription:
        "紙に書いた文字を撮影して、インストールできるフォントに変換します。",
    stepPrint: "01 印刷して書く",
    stepCapture: "02 撮って送る",
    stepReceive: "03 フォントを受け取る",
    retention: "アカウント不要・最終アクセスから{days}日で自動削除",
    separateProjectId: "プロジェクトID",
    separateToken: "アクセストークン",
    tokenPlaceholder: "glp_…",
    pageCount: "{count}字・{pages}ページ",
    sizeSmall: "小",
    sizeMedium: "中",
    sizeLarge: "大",
    uploadDescription:
        "テンプレートを書いたページを、1枚ずつアップロードしてください。",
    dropImage: "ここに画像をドロップ",
    chooseImage: "またはタップして選択（最大6ファイル）",
    retry: "再試行",
    openReview: "確認画面へ",
    page: "ページ {number}",
    waiting: "待機中",
    processing: "処理中…",
    complete: "完了",
    acceptedCount: "採用 {accepted}・自動 {auto}・未取込 {missing}",
    uploadDone: "{count}字を取り込み済み",
    uploadPrompt: "書いたページをアップロード",
    buildPrompt: "採用した文字からフォントを生成",
    deleteNow: "今すぐ削除",
    deleteConfirm: "このプロジェクトを削除しますか？",
    deleted: "削除しました。",
    download: "ダウンロード",
    templateDescription:
        "テンプレートPDFをダウンロードして、100%で印刷します。",
    buildDescription:
        "採用した文字から、インストールできるフォントを作ります。",
    generating: "生成中…",
    qaFailed: "生成されたフォントは品質チェックに失敗しました",
    qaFailedAdvice:
        "レポートを確認して、文字を見直してから作り直してください。",
    preview: "プレビュー",
    artifacts: "成果物",
    noArtifacts: "まだ成果物がありません。",
    installGuide: "インストール方法",
    installText:
        "TTFはデスクトップOSへインストールできます。WOFF2はWebサイトで使う形式です。iOSではフォント管理アプリまたは構成プロファイルを使用してください。",
    backReview: "文字の確認に戻る",
    reviewDescription: "文字を確認して、フォントに含める文字を選びます。",
    toBuild: "ビルドへ",
    searchGlyph: "文字・U+コードを検索",
    all: "すべて",
    unconfirmed: "未確認",
    accepted: "採用",
    rejected: "却下",
    missing: "未取込",
    warnings: "警告あり",
    acceptAutoConfirm: "AUTOの{count}字をすべて採用しますか？",
    acceptAuto: "AUTOをすべて採用",
    acceptGlyph: "{char} を採用",
    rejectGlyph: "{char} を却下",
    selectGlyph: "{char} を選択",
    multiSelect: "複数選択",
    focusedGlyph: "選択中の文字",
    bulkAccept: "選択した文字を採用",
    bulkReject: "選択した文字を却下",
    statusCounts: "文字の状態集計",
    selectedCount: "{count}字を選択中",
    invalidImage: "JPEG・PNG・HEICの画像を選んでください",
    imageTooLarge: "画像が大きすぎます。12MB以内にしてください",
    sectionLatin: "英数",
    sectionHiragana: "ひらがな",
    sectionKatakana: "カタカナ",
    sectionSymbols: "記号",
    statusMissing: "未取込",
    statusAuto: "未確認",
    statusAccepted: "採用",
    statusRejected: "却下",
    privacyData:
        "glyphlabは、手書き文字をフォントに変換するために必要なデータだけを扱います。",
    privacyStoredTitle: "保存するデータ",
    privacyStored:
        "手書き画像は処理が終わるとすぐに削除します。抽出データとフォントは最終アクセスから14日で自動削除されます。",
    privacyAccessTitle: "アクセスと削除",
    privacyAccess:
        "アカウント、アクセス解析、第三者への送信はありません。レート制限のためIPアドレスを最大7日間、abuse logに保存します。プロジェクト画面の「今すぐ削除」からいつでも削除できます。",
    privacySelfHostTitle: "セルフホスト",
    privacySelfHost:
        "自分で管理する場合は、保存先と保持期間を運用環境に合わせて設定できます。",
    backTop: "トップに戻る",
    buildInProgress:
        "別のフォント生成が進行中です。完了を待って結果を表示します。",
    nothingToBuild:
        "採用できる文字がありません。確認画面で文字を採用してから生成してください。",
    reviewMissing: "文字の確認へ",
    qaChecks: "失敗したチェック: {checks}",
    downloadFailed:
        "成果物をダウンロードできませんでした。もう一度お試しください。",
    missingGlyphs: "この文字はフォントに含まれません: {chars}",
    fontLoading: "フォントを読み込み中…",
    fontLoadFailed:
        "プレビュー用フォントを読み込めませんでした。ダウンロードは利用できます。",
    buildHistory: "生成履歴",
    currentBuild: "現在の生成",
} as const;
export type MsgKey = keyof typeof ja;
export function t(
    key: MsgKey,
    params: Record<string, string | number> = {},
): string {
    return ja[key].replace(/\{(\w+)\}/g, (_, name: string) =>
        String(params[name] ?? `{${name}}`),
    );
}
export function errorText(code: string): string {
    return (
        errorMessages[code as keyof typeof errorMessages] ??
        t("errorFallback", { code })
    );
}
export function warningText(code: string): string {
    return warnings[code as keyof typeof warnings] ?? code;
}
