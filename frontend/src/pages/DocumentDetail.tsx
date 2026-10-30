import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type DocumentItem } from "../lib/api";

export default function DocumentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [error, setError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    if (id) api<DocumentItem>(`/documents/${id}`).then(setDocument).catch((err) => setError((err as Error).message));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    api<{ url: string }>(`/documents/${id}/download`)
      .then((result) => {
        if (active) setPreviewUrl(result.url);
      })
      .catch((err) => {
        if (active) setPreviewError((err as Error).message);
      });
    return () => { active = false; };
  }, [id]);

  async function removeDocument() {
    if (!id || !window.confirm("Delete this document permanently?")) return;
    await api(`/documents/${id}`, { method: "DELETE" });
    navigate("/");
  }

  async function downloadDocument() {
    if (!id) return;
    const result = await api<{ url: string }>(`/documents/${id}/download`);
    window.location.assign(result.url);
  }

  if (error) return <main className="mx-auto max-w-3xl p-6"><p role="alert" className="text-danger">{error}</p></main>;
  if (!document) return <main className="mx-auto max-w-3xl p-6">Loading…</main>;

  return (
    <main className="mx-auto max-w-3xl p-6">
      <Link to="/" className="text-sm text-moss underline">← Back to vault</Link>
      <div className="mt-6 rounded-md border border-line bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="break-all font-display text-3xl">{document.original_filename}</h1>
            <p className="mt-2 text-sm text-ink/60">{document.category} · {(document.size_bytes / 1048576).toFixed(2)} MB · {document.page_count ?? 1} page(s)</p>
          </div>
          <span className="rounded-full bg-moss/10 px-3 py-1 text-xs text-moss">{document.status}</span>
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div><dt className="text-ink/60">Uploaded</dt><dd>{new Date(document.uploaded_at).toLocaleString()}</dd></div>
          <div><dt className="text-ink/60">File type</dt><dd>{document.mime_type}</dd></div>
        </dl>
        {previewUrl && (
          <section className="mt-6" aria-label="Document preview">
            <h2 className="mb-2 text-sm font-medium">Preview</h2>
            <div className="overflow-hidden rounded-md border border-line bg-ink/5">
              {document.mime_type === "application/pdf" ? (
                <iframe
                  src={previewUrl}
                  title={`Preview of ${document.original_filename}`}
                  className="pointer-events-none h-40 w-40 border-0"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <img
                  src={previewUrl}
                  alt={`Preview of ${document.original_filename}`}
                  className="pointer-events-none h-40 w-40 object-cover"
                  referrerPolicy="no-referrer"
                />
              )}
            </div>
          </section>
        )}
        {!previewUrl && previewError && (
          <p role="alert" className="mt-4 text-sm text-danger">Preview unavailable: {previewError}</p>
        )}
        <div className="mt-6 flex gap-3">
          <button className="btn" onClick={downloadDocument}>Download</button>
          <button className="rounded-md border border-danger px-4 py-2.5 text-danger" onClick={removeDocument}>Delete</button>
        </div>
      </div>
    </main>
  );
}
