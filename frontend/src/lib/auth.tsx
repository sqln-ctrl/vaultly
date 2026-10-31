import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken, type User } from "./api";

type Ctx = {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  register: (full_name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<Ctx>(null!);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    refreshSession().then(setUser).finally(() => setLoading(false));
  }, []);

  const login: Ctx["login"] = async (email, password) => {
    const data = await api<{ access_token: string; user: User }>("/auth/login", { method: "POST", json: { email, password } });
    setAccessToken(data.access_token);
    setUser(data.user);
  };
  const loginWithGoogle: Ctx["loginWithGoogle"] = async (credential) => {
    const data = await api<{ access_token: string; user: User }>("/auth/google", {
      method: "POST",
      json: { credential },
    });
    setAccessToken(data.access_token);
    setUser(data.user);
  };
  const register: Ctx["register"] = async (full_name, email, password) => {
    await api("/auth/register", { method: "POST", json: { full_name, email, password } });
    await login(email, password);
  };
  const logout = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setAccessToken(null);
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, login, loginWithGoogle, register, logout }}>{children}</AuthContext.Provider>;
}
