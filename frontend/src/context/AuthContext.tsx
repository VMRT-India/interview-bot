import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../lib/apiClient";
import { clearToken, getToken, isTokenExpired, setToken } from "../lib/auth";
import type { TokenResponse, User } from "../lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signup: (email: string, phone_number: string, password: string) => Promise<void>;
  login: (identifier: string, password: string) => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  continueAsGuest: () => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    const token = getToken();
    if (!token || isTokenExpired(token)) {
      clearToken();
      setUser(null);
      return;
    }
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
      }
      setUser(null);
    }
  }

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, []);

  async function signup(email: string, phone_number: string, password: string) {
    const res = await api.post<TokenResponse>(
      "/auth/signup",
      { email, phone_number, password },
      false
    );
    setToken(res.access_token);
    await refreshUser();
  }

  async function login(identifier: string, password: string) {
    const res = await api.post<TokenResponse>(
      "/auth/login",
      { identifier, password },
      false
    );
    setToken(res.access_token);
    await refreshUser();
  }

  async function loginWithToken(token: string) {
    setToken(token);
    await refreshUser();
  }

  async function continueAsGuest() {
    const res = await api.post<TokenResponse>("/auth/guest", undefined, false);
    setToken(res.access_token);
    await refreshUser();
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, signup, login, loginWithToken, continueAsGuest, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
