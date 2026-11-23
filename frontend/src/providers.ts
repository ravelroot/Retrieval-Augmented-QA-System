export type LlmProvider = "ollama" | "openai" | "compativel" | "extrativo";

export interface Preset {
  id: string;
  label: string;
  hint: string;
  provider: LlmProvider;
  baseUrl?: string;
  model?: string;
  modelExample?: string;
  keyUrl?: string;
  needsKey: boolean;
  editableUrl?: boolean;
}

export const PRESETS: Preset[] = [
  { id: "ollama", label: "Ollama", hint: "Gratuito, roda no seu computador ou servidor. Precisa do Ollama instalado.", provider: "ollama",
    model: "llama3.1", needsKey: false },
  { id: "openai", label: "OpenAI", hint: "Modelos da OpenAI com uma chave de API paga.", provider: "openai", model: "gpt-4o-mini",
    keyUrl: "https://platform.openai.com/api-keys", needsKey: true },
  { id: "groq", label: "Groq", hint: "Serviço compatível com a OpenAI, muito rápido, com plano gratuito.", provider: "compativel",
    baseUrl: "https://api.groq.com/openai/v1", modelExample: "openai/gpt-oss-20b", keyUrl: "https://console.groq.com/keys", needsKey: true },
  { id: "openrouter", label: "OpenRouter", hint: "Um só cadastro para modelos de vários fornecedores.", provider: "compativel",
    baseUrl: "https://openrouter.ai/api/v1", modelExample: "meta-llama/llama-3.1-8b-instruct", keyUrl: "https://openrouter.ai/keys", needsKey: true },
  { id: "gemini", label: "Google Gemini", hint: "Modelos Gemini pela interface compatível com a OpenAI.", provider: "compativel",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", modelExample: "gemini-3.8-flash",
    keyUrl: "https://aistudio.google.com/apikey", needsKey: true },
  { id: "lmstudio", label: "LM Studio", hint: "Modelos locais pelo servidor do LM Studio, sem chave.", provider: "compativel",
    baseUrl: "http://localhost:1234/v1", modelExample: "o nome do modelo carregado", needsKey: false, editableUrl: true },
  { id: "custom", label: "Outro compatível", hint: "Qualquer serviço com a rota /v1/chat/completions (vLLM, LocalAI, Azure…).",
    provider: "compativel", modelExample: "nome do modelo no serviço", needsKey: false, editableUrl: true },
  { id: "extrativo", label: "Sem modelo", hint: "Só para testar a instalação: mostra frases dos trechos, sem redigir.", provider: "extrativo",
    needsKey: false },
];

export function presetFor(provider: string, baseUrl: string | null | undefined): Preset {
  if (provider !== "compativel") return PRESETS.find((p) => p.provider === provider) ?? PRESETS[0];
  const url = (baseUrl ?? "").replace(/\/+$/, "");
  return PRESETS.find((p) => p.provider === "compativel" && p.baseUrl === url) ?? PRESETS.find((p) => p.id === "custom")!;
}
