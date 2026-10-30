import { useAuth } from "../lib/auth";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DocumentItem, type Usage } from "../lib/api";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [verificationMessage, setVerificationMessage] = useState("");

  async function load() {
    const [items, limits] = await Promise.all([
      api<DocumentItem[]>("/documents"),
      api<Usage>("/documents/usage"),
    ]);
    setDocuments(items);
    setUsage(limits);
  }

  useEffect(() => { if (user?.email_verified) load().catch((err) => setError((err as Error).message)); }, [user?.email_verified]);

  async function resendVerification() {
    if (!user?.email) return;
    try {
      await api("/auth/resend-verification", { method: "POST", json: { email: user.email } });
      setVerificationMessage("Email delivery is disabled in development. Use the server verification link.");
    } catch (err) {
      setVerificationMessage((err as Error).message);
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true); setError("");
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        await api<DocumentItem>("/documents", { method: "POST", body: form });
      }

      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally { setUploading(false); }
  }
  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="flex items-center justify-between border-b border-line pb-4">
        <span className="font-display text-2xl">Vaultly</span>
        <div className="flex items-center gap-4 text-sm">
          <span>{user?.email}</span>
          <button onClick={logout} className="font-medium text-moss underline">Sign out</button>
        </div>
      </header>

      {!user?.email_verified && (
        <p role="status" className="mt-6 rounded-md border border-brass/50 bg-brass/10 px-4 py-3 text-sm">
          Verify your email to start uploading documents.
          <button type="button" className="ml-2 font-medium text-moss underline" onClick={resendVerification}>
            Resend verification link
          </button>
          {verificationMessage && <span className="mt-1 block text-ink/70">{verificationMessage}</span>}
        </p>
      )}

      {user?.email_verified && (
        <section className="mt-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-3xl">Welcome, {user.full_name.split(" ")[0]}</h1>
              {usage && <p className="mt-1 text-sm text-ink/60">{usage.documents} / {usage.document_limit} documents · {(usage.bytes / 1048576).toFixed(1)} / 200 MB used</p>}
            </div>
            <button className="btn" disabled={uploading} onClick={() => inputRef.current?.click()}>
              {uploading ? "Uploading…" : "Upload documents"}
            </button>
          </div>
          <input ref={inputRef} className="hidden" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" multiple
            onChange={(event) => upload(event.target.files)} />
          <button className="mt-4 w-full rounded-md border border-dashed border-moss/50 px-5 py-8 text-sm text-ink/70"
            disabled={uploading} onClick={() => inputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => { event.preventDefault(); upload(event.dataTransfer.files); }}>
            Drop documents here or choose PDF, JPG, PNG, or WEBP files (15 MB each)
          </button>
          {error && <p role="alert" className="mt-4 rounded-md bg-danger/10 px-4 py-3 text-sm text-danger">{error}</p>}
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {documents.map((document) => (
              <Link key={document.id} to={`/documents/${document.id}`}
                className="rounded-md border border-line bg-white p-4 transition hover:border-moss">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{document.original_filename}</p>
                    <p className="mt-1 text-xs text-ink/60">{document.category} · {Math.max(document.size_bytes / 1048576, 0.01).toFixed(1)} MB</p>
                  </div>
                  <span className="rounded-full bg-moss/10 px-2 py-1 text-xs text-moss">{document.status}</span>
                </div>
              </Link>
            ))}
          </div>
          {documents.length === 0 && !error && <p className="mt-10 text-center text-sm text-ink/60">Your vault is empty. Upload your first document.</p>}
        </section>
      )}
    </div>
  );
}
