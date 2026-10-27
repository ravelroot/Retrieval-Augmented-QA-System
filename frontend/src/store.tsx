import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type ConversationSummary, type DocumentItem } from "./api";

interface StoreValue {
  conversations: ConversationSummary[];
  documents: DocumentItem[];
  reloadConversations: () => void;
  reloadDocuments: () => void;
}

const StoreContext = createContext<StoreValue | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);

  const reloadConversations = useCallback(() => {
    api.conversations().then(setConversations).catch(() => undefined);
  }, []);
  const reloadDocuments = useCallback(() => {
    api.documents().then(setDocuments).catch(() => undefined);
  }, []);

  useEffect(() => {
    reloadConversations();
    reloadDocuments();
  }, [reloadConversations, reloadDocuments]);

  const value = useMemo(() => ({ conversations, documents, reloadConversations, reloadDocuments }),
    [conversations, documents, reloadConversations, reloadDocuments]);
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreValue {
  const value = useContext(StoreContext);
  if (!value) throw new Error("useStore fora do StoreProvider");
  return value;
}
