import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { Shell } from "./components/Shell";
import { ChatPage } from "./pages/Chat";
import { DocumentsPage } from "./pages/Documents";
import { LoginPage } from "./pages/Login";
import { SystemPage } from "./pages/System";

function Private({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/entrar" replace state={{ from: location.pathname }} />;
  return <Shell>{children}</Shell>;
}

export function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/entrar" element={user ? <Navigate to="/conversas" replace /> : <LoginPage />} />
      <Route path="/conversas" element={<Private><ChatPage /></Private>} />
      <Route path="/conversas/:id" element={<Private><ChatPage /></Private>} />
      <Route path="/documentos" element={<Private><DocumentsPage /></Private>} />
      <Route path="/sistema" element={<Private><SystemPage /></Private>} />
      <Route path="*" element={<Navigate to={user ? "/conversas" : "/entrar"} replace />} />
    </Routes>
  );
}
