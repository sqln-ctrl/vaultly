import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const password = String(new FormData(event.currentTarget).get("password"));
    setBusy(true); setError("");
    try {
      await api("/auth/reset-password", {
        method: "POST",
        json: { token: params.get("token") ?? "", password },
      });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      {done ? (
        <div className="max-w-sm text-center">
          <h1 className="font-display text-3xl">Password changed</h1>
          <p className="mt-3 text-sm text-ink/70">For security, all existing sessions were signed out.</p>
          <Link className="btn mt-5 inline-block" to="/login">Sign in</Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
          <h1 className="font-display text-3xl">Choose a new password</h1>
          <label className="block text-sm font-medium">New password
            <input name="password" type="password" required minLength={8} maxLength={128}
              autoComplete="new-password" className="field mt-1.5" />
            <span className="mt-1 block text-sm font-normal text-ink/60">At least 8 characters.</span>
          </label>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          <button className="btn w-full" disabled={busy}>{busy ? "Changing…" : "Change password"}</button>
        </form>
      )}
    </main>
  );
}
