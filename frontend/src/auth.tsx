import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { loadSession, saveSession, setUnauthorizedHandler, type Session, type User } from "./api";

interface AuthValue {
  user: User | null;
  signIn: (session: Session) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => loadSession());

  const signIn = useCallback((value: Session) => {
    saveSession(value);
    setSession(value);
  }, []);

  const signOut = useCallback(() => {
    saveSession(null);
    setSession(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
  }, [signOut]);

  useEffect(() => {
    if (!session) return;
    const left = new Date(session.expires_at).getTime() - Date.now();
    const timer = window.setTimeout(signOut, Math.max(left, 0));
    return () => window.clearTimeout(timer);
  }, [session, signOut]);

  const value = useMemo(() => ({ user: session?.user ?? null, signIn, signOut }), [session, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth fora do AuthProvider");
  return value;
}
