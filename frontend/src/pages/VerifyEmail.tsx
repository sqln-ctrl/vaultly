import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"working" | "done" | "failed">("working");

  useEffect(() => {
    api("/auth/verify-email", { method: "POST", json: { token: params.get("token") ?? "" } })
      .then(() => setState("done"))
      .catch(() => setState("failed"));
  }, [params]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="font-display text-3xl">
        {state === "working" ? "Verifying your email…" : state === "done" ? "Email verified" : "Link expired"}
      </h1>
      {state === "failed" && <p>This verification link is invalid or has expired. Sign in to request a new one.</p>}
      {state !== "working" && <Link className="btn" to="/">Go to Vaultly</Link>}
    </div>
  );
}
