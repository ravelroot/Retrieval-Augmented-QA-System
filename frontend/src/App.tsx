import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { Shell } from "./components/Shell";
import { AgentsPage } from "./pages/Agents";
import { BasesPage } from "./pages/Bases";
import { ChatPage } from "./pages/Chat";
import { ChatsPage } from "./pages/Chats";
import { DocumentsPage } from "./pages/Documents";
import { IntegrationsPage } from "./pages/Integrations";
import { LoginPage } from "./pages/Login";
import { MetricsPage } from "./pages/Metrics";
import { SearchPage } from "./pages/Search";
import { SystemPage } from "./pages/System";
import { WhatsAppPage } from "./pages/WhatsApp";
import { StoreProvider } from "./store";

function PrivateLayout() {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/entrar" replace state={{ from: location.pathname }} />;
  return (
    <StoreProvider key={user.username}>
      <Shell><Outlet /></Shell>
    </StoreProvider>
  );
}

export function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/entrar" element={user ? <Navigate to="/conversas" replace /> : <LoginPage />} />
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
