import { useAuth } from "../lib/auth";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  type ChatConversationItem,
  type ChatMessageItem,
  type DocumentItem,
  type Usage,
} from "../lib/api";

function plainChatContent(content: string) {
  return content.replace(/\*/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [verificationMessage, setVerificationMessage] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessageItem[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatting, setChatting] = useState(false);
  const [conversations, setConversations] = useState<ChatConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  async function load() {
    const [items, limits] = await Promise.all([
      api<DocumentItem[]>("/documents"),
      api<Usage>("/documents/usage"),
    ]);
    setDocuments(items);
    setUsage(limits);
  }

  useEffect(() => { if (user?.email_verified) load().catch((err) => setError((err as Error).message)); }, [user?.email_verified]);
  useEffect(() => {
    if (user?.email_verified) {
      loadChats();
    }
  }, [user?.email_verified]);

  async function loadChats() {
    try {
      const chats = await api<ChatConversationItem[]>("/documents/chats");
      setConversations(chats);
      if (!activeConversationId && chats.length > 0) {
        await openChat(chats[0].id);
      }
    } catch {
      setConversations([]);
    }
  }

  async function openChat(conversationId: string) {
    setActiveConversationId(conversationId);
    try {
      const messages = await api<ChatMessageItem[]>(`/documents/chat?conversation_id=${conversationId}`);
      setChatMessages(messages);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createChat() {
    try {
      const chat = await api<ChatConversationItem>("/documents/chats", {
        method: "POST",
        json: { title: "New chat" },
      });
      setConversations((current) => [chat, ...current]);
      setActiveConversationId(chat.id);
      setChatMessages([]);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteChat(conversationId: string) {
    if (!window.confirm("Delete this chat permanently?")) return;
    try {
      await api(`/documents/chats/${conversationId}`, { method: "DELETE" });
      setConversations((current) => {
        const remaining = current.filter((chat) => chat.id !== conversationId);
        if (activeConversationId === conversationId) {
          setActiveConversationId(remaining[0]?.id ?? null);
          if (remaining[0]) void openChat(remaining[0].id);
          else setChatMessages([]);
        }
        return remaining;
      });
    } catch (err) {
      setError((err as Error).message);
    }
  }

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

  async function sendVaultChat(event: React.FormEvent) {
    event.preventDefault();
    if (!chatInput.trim()) return;
    setChatting(true);
    const message = chatInput.trim();
    try {
      const answer = await api<ChatMessageItem>("/documents/chat", {
        method: "POST",
        json: { message, conversation_id: activeConversationId },
      });
      setChatMessages((current) => [
        ...current,
        { id: `pending-${current.length}`, role: "user", content: message, created_at: new Date().toISOString() },
        answer,
      ]);
      setChatInput("");
      if (answer.conversation_id && answer.conversation_id !== activeConversationId) {
        setActiveConversationId(answer.conversation_id);
      }
      await loadChats();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setChatting(false);
    }
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

      {user?.email_verified && (
        <>
          {!chatOpen && (
            <button
              type="button"
              className="fixed bottom-6 right-6 rounded-full bg-moss px-5 py-3 text-sm font-medium text-white shadow-lg"
              onClick={() => setChatOpen(true)}
            >
              Ask Vaultly
            </button>
          )}
          {chatOpen && (
            <aside className="fixed bottom-6 right-6 flex h-[min(620px,calc(100vh-3rem))] w-[min(620px,calc(100vw-3rem))] flex-col rounded-md border border-line bg-white shadow-xl">
              <header className="flex items-center justify-between border-b border-line px-4 py-3">
                <div>
                  <h2 className="font-display text-lg">Ask your vault</h2>
                  <p className="text-xs text-ink/60">Answers across all documents</p>
                </div>
                <button type="button" className="text-xl text-ink/60" onClick={() => setChatOpen(false)} aria-label="Close vault chat">×</button>
              </header>
              <div className="flex min-h-0 flex-1">
                <nav className="w-44 shrink-0 border-r border-line p-2">
                  <button type="button" className="btn mb-2 w-full text-xs" onClick={createChat}>+ New chat</button>
                  <div className="space-y-1">
                    {conversations.map((chat) => (
                      <div key={chat.id} className={`group flex items-center rounded-md ${chat.id === activeConversationId ? "bg-moss/10" : ""}`}>
                        <button type="button" className="min-w-0 flex-1 truncate px-2 py-2 text-left text-xs" onClick={() => openChat(chat.id)}>
                          {chat.title}
                        </button>
                        <button
                          type="button"
                          className="p-2 text-danger opacity-60 hover:opacity-100"
                          onClick={() => deleteChat(chat.id)}
                          aria-label={`Delete ${chat.title}`}
                          title="Delete chat"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <path d="M3 6h18" />
                            <path d="M8 6V4h8v2" />
                            <path d="M19 6l-1 14H6L5 6" />
                            <path d="M10 11v5M14 11v5" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                </nav>
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="flex-1 space-y-2 overflow-y-auto p-3">
                    {chatMessages.length === 0 && <p className="text-sm text-ink/60">Ask a question about your documents.</p>}
                    {chatMessages.map((message) => (
                      <p key={message.id} className={message.role === "user" ? "text-right text-sm" : "text-sm text-moss"}>
                        <span className="inline-block max-w-[85%] whitespace-pre-wrap rounded-md bg-ink/5 px-3 py-2 text-left">{plainChatContent(message.content)}</span>
                      </p>
                    ))}
                  </div>
                  <form className="flex gap-2 border-t border-line p-3" onSubmit={sendVaultChat}>
                    <input
                      className="field"
                      value={chatInput}
                      onChange={(event) => setChatInput(event.target.value)}
                      placeholder="Ask across all documents..."
                      maxLength={4000}
                    />
                    <button className="btn shrink-0" disabled={chatting || !chatInput.trim()}>
                      {chatting ? "..." : "Send"}
                    </button>
                  </form>
                </div>
              </div>
            </aside>
          )}
        </>
      )}
    </div>
  );
}
