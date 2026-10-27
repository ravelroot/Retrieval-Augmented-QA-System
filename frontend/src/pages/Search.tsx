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
  const [scope, setScope] = useState<string>("");
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
        <h1>Busca nos trechos</h1>
        <p className="page__lead">Encontre a passagem exata sem gerar resposta. Útil para conferir o que o acervo diz e calibrar perguntas.</p>
      </header>

      <form className="searchbar" onSubmit={submit} role="search">
        <div className="searchbar__field">
          <Icon name="search" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ex.: torque dos parafusos da tampa"
            aria-label="Termos da busca" maxLength={500} autoFocus />
          <button className="button button--primary" type="submit" disabled={busy || !query.trim() || !ready.length}>
            {busy ? "Buscando…" : "Buscar"}
          </button>
        </div>
        <div className="searchbar__opts">
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
          <label className="toggle">
            <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />
            <span className="toggle__ui" aria-hidden="true" />
            Reordenar com o reranker
          </label>
        </div>
      </form>

      {error && <p className="alert" role="alert">{error}</p>}

      {!ready.length && (
        <div className="empty empty--page">
          <h2>Nenhum documento pronto</h2>
          <p>A busca percorre os trechos dos PDFs indexados.</p>
          <Link className="button button--primary" to="/documentos"><Icon name="upload" size={16} />Enviar PDFs</Link>
        </div>
      )}

      {result && (
        <section className="results" aria-label="Resultados">
          <div className="results__head">
            <p>
              {result.results.length
                ? <>{plural(result.results.length, "trecho encontrado", "trechos encontrados")} para <b>“{result.query}”</b></>
                : <>Nenhum trecho passou no corte de similaridade para <b>“{result.query}”</b>.</>}
              <span className="muted"> em {(result.took_ms / 1000).toFixed(2).replace(".", ",")} s</span>
            </p>
            {result.results.length > 0 && (
              <Link className="button button--small" to={`/conversas?pergunta=${encodeURIComponent(result.query)}${scope ? `&documento=${scope}` : ""}`}>
                <Icon name="chat" size={15} />Perguntar sobre isso
              </Link>
            )}
          </div>
          <div className="results__list">
            {result.results.map((s) => (
              <SourceSlip key={`${s.document_id}-${s.rank}`} source={s} query={result.query} onError={(m) => toast(m, "error")} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
