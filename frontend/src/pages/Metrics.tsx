import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, type Metrics } from "../api";
import { Icon } from "../components/Icon";
import { formatRelative, plural } from "../format";

const periods = [7, 30, 90];

function clip(answer: string): string {
  const text = answer.replace(/\s*\[\d+\]/g, "").replace(/^\s*[-*•]\s+/gm, "").replace(/\s*\n+\s*/g, " ").trim();
  return text.length > 260 ? `${text.slice(0, 257)}…` : text;
}

function pct(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

function seconds(ms: number | null): string {
  return ms === null ? "—" : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
}

function Daily({ data }: { data: Metrics["daily"] }) {
  const max = Math.max(1, ...data.map((d) => d.questions));
  const w = 100 / Math.max(1, data.length);
  const label = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const ticks = data.length > 14 ? [0, Math.floor(data.length / 2), data.length - 1] : data.map((_, i) => i);
  return (
    <figure className="daily">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img"
        aria-label={`Perguntas por dia: ${data.map((d) => `${label(d.date)} ${d.questions}`).join(", ")}`}>
        {[0.5, 1].map((f) => <line key={f} x1="0" x2="100" y1={40 - f * 38} y2={40 - f * 38} className="daily__grid" />)}
        {data.map((d, i) => {
          const h = (d.questions / max) * 38;
          const u = (d.unanswered / max) * 38;
          return (
            <g key={d.date}>
              <title>{`${label(d.date)}: ${plural(d.questions, "pergunta", "perguntas")}, ${d.unanswered} sem resposta`}</title>
              <rect x={i * w + w * 0.2} width={w * 0.6} y={40 - h} height={Math.max(h - u, 0)} className="daily__ok" />
              {u > 0 && <rect x={i * w + w * 0.2} width={w * 0.6} y={40 - u} height={u} className="daily__miss" />}
            </g>
          );
        })}
      </svg>
      <div className="daily__axis">
        {ticks.map((i) => <span key={i} style={{ left: `${(i + 0.5) * w}%` }}>{label(data[i].date)}</span>)}
      </div>
      <figcaption>
        <span className="key key--ok" />Respondidas
        <span className="key key--miss" />Sem resposta nos documentos
        <span className="daily__peak">Pico de {plural(max, "pergunta", "perguntas")} em um dia</span>
      </figcaption>
    </figure>
  );
}

export function MetricsPage() {
  const [days, setDays] = useState(30);
  const [m, setM] = useState<Metrics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    api.metrics(days).then(setM).catch((e: ApiError) => setError(e.message));
  }, [days]);

  const maxCite = Math.max(1, ...(m?.top_documents.map((d) => d.citations) ?? [1]));
  const rated = m ? m.feedback.up + m.feedback.down : 0;

  return (
    <div className="page">
      <header className="page__head">
        <div className="page__titles">
          <span className="page__over">Gestão</span>
          <h1>Painel de qualidade</h1>
          <p className="page__lead">
            Quanto o acervo responde, em quanto tempo e onde faltam documentos.
            {m && (m.scope === "all" ? " Dados de todas as contas." : " Dados das suas conversas.")}
          </p>
        </div>
        <div className="segmented" role="tablist" aria-label="Período">
          {periods.map((p) => (
            <button key={p} role="tab" aria-selected={days === p} onClick={() => setDays(p)}>{p} dias</button>
          ))}
        </div>
      </header>

      {error && <p className="alert" role="alert">{error}</p>}

      {m && (
        <>
          <div className="box box--metrics">
            <section className="lid" aria-label="Resumo do período">
              <span className="lid__label">Perguntas nos últimos {m.period_days} dias</span>
              <strong className="lid__number">{m.questions.toLocaleString("pt-BR")}</strong>
              <p className="lid__sub">{plural(m.conversations, "conversa", "conversas")} e {plural(m.unanswered, "pergunta", "perguntas")} sem base nos documentos.</p>
              <dl className="lid__stats">
                <div><dt>Taxa de resposta</dt><dd>{pct(m.answer_rate)}</dd></div>
                <div><dt>Tempo médio</dt><dd>{seconds(m.avg_latency_ms)}</dd></div>
                <div><dt>95% abaixo de</dt><dd>{seconds(m.p95_latency_ms)}</dd></div>
                <div><dt>Avaliações úteis</dt><dd>{rated ? `${pct(m.feedback.up / rated)} de ${rated}` : "—"}</dd></div>
              </dl>
            </section>
            <section className="panel">
              <h2>Perguntas por dia</h2>
              {m.questions === 0 ? <p className="panel__lead">Nenhuma pergunta no período.</p> : <Daily data={m.daily} />}
            </section>
          </div>

          <div className="box box--two">
            <section className="panel">
              <h2>Lacunas do acervo</h2>
              <p className="panel__lead">Perguntas que nenhum documento respondeu. Cada uma indica um PDF que falta ou um termo diferente do usado no manual.</p>
              {m.unanswered_recent.length === 0 ? (
                <p className="panel__lead">Nenhuma lacuna no período.</p>
              ) : (
                <ul className="gaps">
                  {m.unanswered_recent.map((g, i) => (
                    <li key={i}>
                      <span className="gaps__q">{g.question}</span>
                      <span className="gaps__meta">{formatRelative(g.asked_at)}</span>
                      <span className="gaps__actions">
                        <Link to={`/busca?q=${encodeURIComponent(g.question)}`} className="link-button"><Icon name="search" size={14} />Buscar</Link>
                        <Link to={`/conversas/${g.conversation_id}`} className="link-button"><Icon name="chat" size={14} />Abrir</Link>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="panel">
              <h2>Documentos mais citados</h2>
              <p className="panel__lead">Quantas vezes cada PDF apareceu como fonte de uma resposta.</p>
              {m.top_documents.length === 0 ? (
                <p className="panel__lead">Nenhuma citação no período.</p>
              ) : (
                <ol className="bars">
                  {m.top_documents.map((d) => (
                    <li key={d.document_id ?? d.title}>
                      <span className="bars__label" title={d.title}>{d.title}</span>
                      <span className="bars__track"><span style={{ width: `${(d.citations / maxCite) * 100}%` }} /></span>
                      <span className="bars__value">{d.citations}</span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>

          <div className="box">
            <section className="panel">
              <h2>Respostas avaliadas como “não ajudou”</h2>
              {m.negative_recent.length === 0 ? (
                <p className="panel__lead">Nenhuma avaliação negativa no período.</p>
              ) : (
                <ul className="reviews">
                  {m.negative_recent.map((r) => (
                    <li key={r.message_id}>
                      <p className="reviews__q">{r.question}</p>
                      <p className="reviews__a">{clip(r.answer)}</p>
                      <Link to={`/conversas/${r.conversation_id}`} className="link-button">Abrir conversa, {formatRelative(r.asked_at)}</Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
