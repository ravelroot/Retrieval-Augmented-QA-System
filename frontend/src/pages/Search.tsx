import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, api, type SearchResult } from "../api";
import { Icon } from "../components/Icon";
import { SourceSlip } from "../components/SourceSlip";
import { useToast } from "../components/Toast";
import { plural } from "../format";
import { useStore } from "../store";

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const { documents, reloadDocuments } = useStore();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [scope, setScope] = useState("");
  const [rerank, setRerank] = useState(true);
  const [limit, setLimit] = useState(8);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const ready = useMemo(() => documents.filter((d) => d.status === "READY"), [documents]);

  useEffect(reloadDocuments, [reloadDocuments]);
  useEffect(() => {
    const q = params.get("q");
    if (q) void run(q);
  }, []);

  async function run(text: string) {
    const q = text.trim();
    if (!q) return;
    setBusy(true);
    setError("");
    try {
      setResult(await api.search(q, scope ? [scope] : [], rerank, limit));
      setParams({ q }, { replace: true });
    } catch (e) {
      setError((e as ApiError).message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void run(query);
  }

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Consulta</span>
          <h1>Busca nos trechos</h1>
          <p className="page__lead">Encontre a passagem exata sem gerar resposta, para conferir o que o acervo diz e calibrar perguntas.</p>
        </div>
      </header>

      <form className="box searchbox" onSubmit={submit} role="search">
        <div className="searchbox__field">
          <Icon name="search" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ex.: torque dos parafusos da tampa"
            aria-label="Termos da busca" maxLength={500} autoFocus />
          <button className="primary-button" type="submit" disabled={busy || !query.trim() || !ready.length}>
            {busy ? "Buscando…" : "Buscar"}
          </button>
        </div>
        <div className="searchbox__opts">
          <label className="select">
            <span>Documento</span>
            <select value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="">Todos os prontos ({ready.length})</option>
              {ready.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </label>
          <label className="select">
            <span>Resultados</span>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              {[4, 8, 12, 20].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label className="check check--inline">
            <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />
            Reordenar com o reranker
          </label>
        </div>
      </form>

      {error && <p className="alert" role="alert">{error}</p>}

      {!ready.length && (
        <div className="empty empty--compact">
          <h2>Nenhum documento pronto</h2>
          <p>A busca percorre os trechos dos PDFs indexados.</p>
          <Link className="primary-button" to="/documentos">Ir para Documentos</Link>
        </div>
      )}

      {result && (
        <section className="results" aria-label="Resultados">
          <div className="results__head">
            <p>
              {result.results.length
                ? <>{plural(result.results.length, "trecho encontrado", "trechos encontrados")} para <strong>“{result.query}”</strong></>
                : <>Nenhum trecho passou no corte de similaridade para <strong>“{result.query}”</strong>.</>}
              <span className="muted">, em {(result.took_ms / 1000).toFixed(2).replace(".", ",")} s</span>
            </p>
            {result.results.length > 0 && (
              <Link className="ghost-button small" to={`/conversas?pergunta=${encodeURIComponent(result.query)}${scope ? `&documento=${scope}` : ""}`}>
                <Icon name="chat" size={15} />Perguntar sobre isso
              </Link>
            )}
          </div>
          <ol className="box results__list">
            {result.results.map((s) => (
              <li key={`${s.document_id}-${s.rank}`}>
                <SourceSlip source={s} query={result.query} onError={(m) => toast(m, "error")} />
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
