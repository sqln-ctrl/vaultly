import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function ForgotPassword() {
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email"));
    setBusy(true); setError("");
    try {
      await api("/auth/forgot-password", { method: "POST", json: { email } });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {done ? (
          <div className="text-center">
            <h1 className="font-display text-3xl">Check your email</h1>
            <p className="mt-3 text-sm text-ink/70">If an account exists, a reset link has been sent. It expires shortly.</p>
            <Link className="btn mt-5 inline-block" to="/login">Back to sign in</Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-5">
            <h1 className="font-display text-3xl">Reset your password</h1>
            <label className="block text-sm font-medium">Email
              <input name="email" type="email" required autoComplete="email" className="field mt-1.5" />
            </label>
            {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            <button className="btn w-full" disabled={busy}>{busy ? "Sending…" : "Send reset link"}</button>
            <p className="text-center"><Link className="text-sm underline" to="/login">Back to sign in</Link></p>
          </form>
        )}
      </div>
    </main>
  );
}
