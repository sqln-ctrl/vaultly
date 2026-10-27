import { useAuth } from "../lib/auth";

export default function Dashboard() {
  const { user, logout } = useAuth();
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
          Verify your email to start uploading documents. Check your inbox for the link.
        </p>
      )}

      <section className="mt-16 text-center">
        <h1 className="font-display text-3xl">Welcome, {user?.full_name.split(" ")[0]}</h1>
        <p className="mx-auto mt-3 max-w-md text-ink/70">
          Your vault is empty. Document upload is the next thing we're building.
        </p>
      </section>
    </div>
  );
}
