import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get("email")), password = String(f.get("password"));
    setBusy(true); setError("");
    try {
      if (isLogin) await login(email, password);
      else await register(String(f.get("name")), email, password);
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    } finally { setBusy(false); }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-ink p-14 text-paper lg:flex lg:flex-col lg:justify-between">
        <span className="font-display text-2xl">Vaultly</span>
        <div aria-hidden className="absolute -right-24 top-1/2 size-[34rem] -translate-y-1/2 rounded-full border border-brass/40">
          <div className="absolute inset-10 rounded-full border border-brass/30" />
          <div className="absolute inset-20 rounded-full border-2 border-brass/60" />
          <div className="absolute inset-[11.5rem] rounded-full bg-brass/90" />
        </div>
        <p className="relative max-w-md font-display text-4xl leading-tight">
          Every bill and invoice, kept safe and ready to answer your questions.
        </p>
      </aside>

      <main className="flex items-center justify-center p-6">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
          <h1 className="font-display text-3xl">{isLogin ? "Sign in to Vaultly" : "Create your vault"}</h1>
          {!isLogin && (
            <label className="block text-sm font-medium">Full name
              <input name="name" required autoComplete="name" className="field mt-1.5" />
            </label>
          )}
          <label className="block text-sm font-medium">Email
            <input name="email" type="email" required autoComplete="email" className="field mt-1.5" />
          </label>
          <label className="block text-sm font-medium">Password
            <input name="password" type="password" required minLength={8}
              autoComplete={isLogin ? "current-password" : "new-password"} className="field mt-1.5" />
            {!isLogin && <span className="mt-1 block text-sm font-normal text-ink/60">At least 8 characters.</span>}
          </label>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          <button className="btn w-full" disabled={busy}>
            {busy ? "One moment…" : isLogin ? "Sign in" : "Create account"}
          </button>
          {isLogin && (
            <p className="text-center text-sm">
              <Link className="font-medium text-moss underline" to="/forgot-password">Forgot password?</Link>
            </p>
          )}
          <p className="text-sm text-ink/70">
            {isLogin ? "New to Vaultly? " : "Already have an account? "}
            <Link className="font-medium text-moss underline" to={isLogin ? "/register" : "/login"}>
              {isLogin ? "Create an account" : "Sign in"}
            </Link>
          </p>
        </form>
      </main>
    </div>
  );
}
