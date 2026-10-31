import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (parent: HTMLElement, options: { theme?: string; size?: string; text?: string; width?: number }) => void;
        };
      };
    };
  }
}

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, login, loginWithGoogle, register } = useAuth();
  const navigate = useNavigate();
  const googleButton = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  if (user) return <Navigate to="/" replace />;

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
    if (!isLogin || !clientId || !googleButton.current) return;

    const initialize = () => {
      if (!window.google || !googleButton.current) return;
      googleButton.current.replaceChildren();
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async ({ credential }) => {
          setBusy(true);
          setError("");
          try {
            await loginWithGoogle(credential);
            navigate("/");
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        },
      });
      window.google.accounts.id.renderButton(googleButton.current, {
        theme: "outline",
        size: "large",
        text: "signin_with",
        width: 384,
      });
    };

    if (window.google) {
      initialize();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = initialize;
    document.head.appendChild(script);
  }, [isLogin, loginWithGoogle, navigate]);

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
          {isLogin && import.meta.env.VITE_GOOGLE_CLIENT_ID && (
            <div>
              <div className="my-1 flex items-center gap-3 text-sm text-ink/50" aria-hidden="true">
                <span className="h-px flex-1 bg-line" />
                <span>or</span>
                <span className="h-px flex-1 bg-line" />
              </div>
              <div ref={googleButton} className="flex justify-center" aria-label="Sign in with Google" />
            </div>
          )}
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
