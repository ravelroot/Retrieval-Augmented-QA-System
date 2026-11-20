import { lazy, Suspense, useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import { Shell } from "./components/Shell";
import { ChatPage } from "./pages/Chat";
import { LoginPage } from "./pages/Login";
import { StoreProvider } from "./store";

const AgentsPage = lazy(() => import("./pages/Agents").then((m) => ({ default: m.AgentsPage })));
const BasesPage = lazy(() => import("./pages/Bases").then((m) => ({ default: m.BasesPage })));
const ChatsPage = lazy(() => import("./pages/Chats").then((m) => ({ default: m.ChatsPage })));
const DocumentsPage = lazy(() => import("./pages/Documents").then((m) => ({ default: m.DocumentsPage })));
const IntegrationsPage = lazy(() => import("./pages/Integrations").then((m) => ({ default: m.IntegrationsPage })));
const MetricsPage = lazy(() => import("./pages/Metrics").then((m) => ({ default: m.MetricsPage })));
const SearchPage = lazy(() => import("./pages/Search").then((m) => ({ default: m.SearchPage })));
const SetupPage = lazy(() => import("./pages/Setup").then((m) => ({ default: m.SetupPage })));
const SystemPage = lazy(() => import("./pages/System").then((m) => ({ default: m.SystemPage })));
const WhatsAppPage = lazy(() => import("./pages/WhatsApp").then((m) => ({ default: m.WhatsAppPage })));

function seenSetup(): boolean {
  try {
    return sessionStorage.getItem("nexo.assistente") === "visto";
  } catch {
    return true;
  }
}

function useSetupGate(admin: boolean) {
  const navigate = useNavigate();
  useEffect(() => {
    if (!admin || seenSetup()) return;
    api.setup().then((state) => { if (!state.done) navigate("/configurar", { replace: true }); }).catch(() => undefined);
  }, [admin, navigate]);
}

function PrivateLayout() {
  const { user } = useAuth();
  const location = useLocation();
  useSetupGate(user?.role === "admin" && !user.must_change_password);
  if (!user) return <Navigate to="/entrar" replace state={{ from: location.pathname }} />;
  if (user.must_change_password) return <Navigate to="/configurar" replace />;
  return (
    <StoreProvider key={user.username}>
      <Shell><Suspense fallback={<div className="page" aria-busy="true" />}><Outlet /></Suspense></Shell>
    </StoreProvider>
  );
}

export function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/entrar" element={user ? <Navigate to={user.must_change_password ? "/configurar" : "/conversas"} replace /> : <LoginPage />} />
      <Route path="/configurar" element={user ? <Suspense fallback={null}><SetupPage /></Suspense> : <Navigate to="/entrar" replace />} />
      <Route element={<PrivateLayout />}>
        <Route path="/conversas" element={<ChatPage />} />
        <Route path="/conversas/:id" element={<ChatPage />} />
        <Route path="/chats" element={<ChatsPage />} />
        <Route path="/agentes" element={<AgentsPage />} />
        <Route path="/bases" element={<BasesPage />} />
        <Route path="/bases/:id" element={<BasesPage />} />
        <Route path="/whatsapp" element={<WhatsAppPage />} />
        <Route path="/busca" element={<SearchPage />} />
        <Route path="/documentos" element={<DocumentsPage />} />
        <Route path="/painel" element={<MetricsPage />} />
        <Route path="/integracoes" element={<IntegrationsPage />} />
        <Route path="/sistema" element={<SystemPage />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? "/conversas" : "/entrar"} replace />} />
    </Routes>
  );
}
