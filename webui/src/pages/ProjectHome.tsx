import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError, downloadBlob } from "../lib/api";
import { clearToken } from "../lib/token";
import { errorText, t } from "../i18n/ja";

type Summary = { name: string; family_name: string; charset: { id: string; drawn: number }; counts: { missing: number; auto: number; accepted: number; rejected: number }; expires_at: string };
export default function ProjectHome() {
  const { projectId = "" } = useParams(); const navigate = useNavigate(); const client = useQueryClient(); const [deleted, setDeleted] = useState(false);
  const summary = useQuery({ queryKey: ["summary", projectId], queryFn: () => apiFetch<Summary>(`/projects/${projectId}`, { projectId }) });
  const deletion = useMutation({ mutationFn: () => apiFetch<void>(`/projects/${projectId}`, { method: "DELETE", projectId }), onSuccess: () => { clearToken(projectId); setDeleted(true); client.clear(); navigate("/"); } });
  if (summary.isLoading) return <p className="loading">{t("loading")}</p>;
  if (summary.error) return <section className="card"><h1>{errorText(summary.error instanceof ApiError ? summary.error.code : "E_INTERNAL")}</h1><Link className="button" to="/">{t("open")}</Link></section>;
  const data = summary.data!; const done = data.counts.auto + data.counts.accepted + data.counts.rejected;
  async function template() { const result = await downloadBlob(`/projects/${projectId}/template.pdf`, projectId); const url = URL.createObjectURL(result.blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.filename ?? "template.pdf"; anchor.click(); URL.revokeObjectURL(url); }
  return <section><div className="page-heading"><div><p className="eyebrow">{data.charset.id}</p><h1>{data.name}</h1><p>{data.family_name}</p></div><button className="text-button danger" onClick={() => { if (window.confirm("このプロジェクトを削除しますか？")) deletion.mutate(); }}>今すぐ削除</button></div><div className="coverage"><strong>{done} / {data.charset.drawn}</strong><span style={{ width: `${Math.min(100, (done / Math.max(1, data.charset.drawn)) * 100)}%` }} /></div><div className="checklist"><div className="card checklist-item"><span>01</span><div><h2>{t("template")}</h2><p>テンプレートPDFをダウンロードして、100%で印刷します。</p></div><button className="button secondary" onClick={() => void template()}>ダウンロード</button></div><Link className={`card checklist-item ${done ? "complete" : ""}`} to={`/p/${projectId}/upload`}><span>02</span><div><h2>{t("upload")}</h2><p>{done ? `${done}字を取り込み済み` : "書いたページをアップロード"}</p></div></Link><Link className={`card checklist-item ${data.counts.accepted ? "complete" : ""}`} to={`/p/${projectId}/review`}><span>03</span><div><h2>{t("review")}</h2><p>採用 {data.counts.accepted}・自動 {data.counts.auto}・未取込 {data.counts.missing}</p></div></Link><Link className={`card checklist-item ${data.counts.accepted + data.counts.auto ? "complete" : ""}`} to={`/p/${projectId}/build`}><span>04</span><div><h2>{t("build")}</h2><p>採用した文字からフォントを生成</p></div></Link></div>{deleted && <p className="notice">削除しました。</p>}</section>;
}
