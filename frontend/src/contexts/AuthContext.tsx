import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { User } from "../types";

const TOKEN_KEY = "finmonitor_token";
const SESSION_KEY = "finmonitor_session_id";

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credential: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function getOrCreateSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const apiUrl = process.env.REACT_APP_API_URL || "https://localhost:3443/api";

  const buildHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = {
      "X-Session-ID": getOrCreateSessionId(),
    };
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  };

  const fetchMe = useCallback(async (): Promise<User | null> => {
    try {
      const resp = await fetch(`${apiUrl}/auth/me`, { headers: buildHeaders() });
      if (!resp.ok) return null;
      return resp.json();
    } catch {
      return null;
    }
  }, [apiUrl]);

  const refreshUser = useCallback(async () => {
    const u = await fetchMe();
    setUser(u);
  }, [fetchMe]);

  useEffect(() => {
    (async () => {
      const u = await fetchMe();
      setUser(u);
      setIsLoading(false);
    })();
  }, [fetchMe]);

  const login = useCallback(
    async (credential: string) => {
      const sessionId = getOrCreateSessionId();
      const resp = await fetch(`${apiUrl}/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential, session_id: sessionId }),
      });
      if (!resp.ok) throw new Error("Google login failed");
      const data = await resp.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      // session_id is now detached from the anonymous user — keep it as a fresh anon id next logout
      setUser(data.user);
    },
    [apiUrl]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    // Generate a new session ID so the next anonymous session starts fresh
    localStorage.removeItem(SESSION_KEY);
    getOrCreateSessionId();
    setUser(null);
    // Reload so the dashboard re-fetches as anonymous
    window.location.reload();
  }, []);

  const isAuthenticated = user !== null && !user.is_anonymous;

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export { getOrCreateSessionId };
