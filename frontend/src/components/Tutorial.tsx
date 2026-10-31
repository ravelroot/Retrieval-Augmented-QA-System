import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Icon } from "./Icon";
import { LogoMark } from "./Logo";

interface Step {
  over: string;
  title: string;
  text: string;
  points: string[];
  art: ReactNode;
}

function ArtWelcome() {
  return (
    <div className="tut-art tut-art--welcome">
      <div className="tut-lid">
        <LogoMark size={56} />
        <span className="tut-lid__big fina">Nexo</span>
        <span className="tut-lid__sub">Respostas com fonte</span>
      </div>
      <div className="tut-card">
        <div className="tut-bubble tut-bubble--user">Qual o torque dos parafusos da tampa?</div>
        <div className="tut-bubble tut-bubble--bot">Aperte em cruz com 45 N·m <span className="tut-cite">1</span></div>
        <div className="tut-slip"><b>1</b><span>Guia de manutenção · página 5</span></div>
      </div>
    </div>
  );
}

function ArtBases() {
  return (
    <div className="tut-art">
      <div className="tut-card tut-card--wide">
        <div className="tut-row tut-row--head"><Icon name="base" size={16} /><strong>Suporte técnico</strong><span className="tut-dot">Pronta</span></div>
        <div className="tut-row"><span className="tut-ext">PDF</span>Manual do compressor CA-150<em>12 páginas</em></div>
        <div className="tut-row"><span className="tut-ext">DOCX</span>Política de garantia<em>4 partes</em></div>
        <div className="tut-row"><span className="tut-ext">CSV</span>Tabela de peças e preços<em>3 partes</em></div>
        <div className="tut-row"><span className="tut-ext">TXT</span>Horário de atendimento<em>texto digitado</em></div>
        <div className="tut-row tut-row--drop"><Icon name="upload" size={15} />Arraste arquivos ou escreva um texto</div>
      </div>
    </div>
  );
}

function ArtAgents() {
  return (
    <div className="tut-art">
      <div className="tut-card tut-card--wide tut-form">
        <div className="tut-agent"><span className="tut-avatar" style={{ background: "#2b4c5a" }}>S</span><div><strong>Sofia</strong><small>Suporte técnico</small></div></div>
        <label>Instruções<span>Fale de forma cordial e objetiva. Dê o passo a passo.</span></label>
        <label>Base de conhecimento<span className="tut-select"><Icon name="base" size={14} />Suporte técnico</span></label>
        <label>Quando não souber<span>Vou chamar uma pessoa da equipe.</span></label>
      </div>
    </div>
  );
}

function ArtChats() {
  return (
    <div className="tut-art">
      <div className="tut-split">
        {[["S", "#2b4c5a", "Sofia", "Como trocar o filtro?"], ["V", "#3e6b2a", "Vendas", "Tem pronta entrega?"], ["R", "#5b4a7a", "RH", "Quantos dias de férias?"]].map(([i, c, n, q]) => (
          <div key={n} className="tut-pane">
            <div className="tut-pane__head"><span className="tut-avatar tut-avatar--sm" style={{ background: c }}>{i}</span>{n}</div>
            <div className="tut-bubble tut-bubble--user tut-bubble--sm">{q}</div>
            <div className="tut-lines"><span /><span /><span /></div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ArtWhatsApp() {
  return (
    <div className="tut-art">
      <div className="tut-card tut-card--wide tut-inbox">
        <div className="tut-inbox__list">
          <div className="tut-contact tut-contact--on"><span className="tut-avatar tut-avatar--sm tut-avatar--round">M</span>Marina<small>agente</small></div>
          <div className="tut-contact"><span className="tut-avatar tut-avatar--sm tut-avatar--round">J</span>João<small className="tut-wait">aguardando</small></div>
          <div className="tut-contact"><span className="tut-avatar tut-avatar--sm tut-avatar--round">A</span>Ana<small>você</small></div>
        </div>
        <div className="tut-inbox__chat">
          <div className="tut-bubble tut-bubble--in">Vocês consertam o CA-150?</div>
          <div className="tut-bubble tut-bubble--out">Sim! A assistência atende de segunda a sexta. <span className="tut-cite">1</span></div>
          <div className="tut-take"><Icon name="user2" size={14} />Assumir conversa</div>
        </div>
      </div>
    </div>
  );
}

function ArtDone() {
  return (
    <div className="tut-art">
      <div className="tut-check">
        {["Crie uma base e adicione conteúdo", "Crie um agente ligado à base", "Converse em vários chats", "Conecte o WhatsApp"].map((t, i) => (
          <div key={t} className="tut-check__row"><span>{i + 1}</span>{t}</div>
        ))}
      </div>
    </div>
  );
}

const STEPS: Step[] = [
  {
    over: "Boas-vindas",
    title: "Respostas só com o que está nos seus documentos",
    text: "O Nexo lê seus arquivos e responde citando o trecho e a página de onde tirou cada informação. Se não estiver nos documentos, ele diz que não encontrou.",
    points: ["Cada resposta mostra a fonte", "Nada inventado: sem base, sem resposta", "Leva menos de 2 minutos para conhecer"],
    art: <ArtWelcome />,
  },
  {
    over: "Passo 1",
    title: "Bases de conhecimento",
    text: "Uma base reúne o que um agente pode consultar. Envie PDF, Word, planilhas CSV, Markdown, JSON e HTML, ou digite um texto na hora.",
    points: ["Adicione e retire informações quando quiser", "Teste a busca antes de colocar no ar", "Aba Integrar com exemplos prontos de API"],
    art: <ArtBases />,
  },
  {
    over: "Passo 2",
    title: "Agentes",
    text: "Um agente é um assistente com nome, instruções e uma base. Defina o tom, a saudação e o que ele diz quando não sabe.",
    points: ["Um agente para cada assunto ou equipe", "Instruções de tom e de regras", "Escolha se ele cita as fontes"],
    art: <ArtAgents />,
  },
  {
    over: "Passo 3",
    title: "Vários chats ao mesmo tempo",
    text: "Em Chats com agentes você abre conversas com quantos agentes quiser, alterna entre as abas ou vê até três lado a lado.",
    points: ["Abas que ficam abertas entre as visitas", "Trechos citados abrem embaixo da resposta", "Histórico de cada agente na lateral"],
    art: <ArtChats />,
  },
  {
    over: "Passo 4",
    title: "Atendimento pelo WhatsApp",
    text: "Conecte seu número e deixe um agente responder os clientes. Quando ele não souber, a conversa fica aguardando um atendente.",
    points: ["Caixa de entrada com todos os clientes", "Assuma ou devolva a conversa ao agente", "Peça uma sugestão de resposta antes de enviar"],
    art: <ArtWhatsApp />,
  },
  {
    over: "Pronto",
    title: "Tudo certo para começar",
    text: "Siga a ordem abaixo na primeira vez. Você pode rever este tutorial a qualquer momento pelo menu, pela paleta de comandos ou em Sistema e conta.",
    points: [],
    art: <ArtDone />,
  },
];

const ACTIONS = [
  { to: "/bases", label: "Criar base", icon: "base" },
  { to: "/agentes", label: "Criar agente", icon: "bot" },
  { to: "/whatsapp", label: "Conectar WhatsApp", icon: "whatsapp" },
];

export function Tutorial({ name, onDone }: { name: string; onDone: () => void }) {
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const step = STEPS[index];
  const last = index === STEPS.length - 1;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDone();
      else if (e.key === "ArrowRight") setIndex((i) => Math.min(STEPS.length - 1, i + 1));
      else if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDone]);

  const first = name.split(/\s+/)[0] || "";

  return (
    <div className="tutorial-backdrop">
      <div className="tutorial" role="dialog" aria-modal="true" aria-labelledby="tutorial-title">
        <div className="tutorial__art" aria-hidden="true">{step.art}</div>
        <div className="tutorial__body">
          <div className="tutorial__top">
            <span className="tutorial__over">{index === 0 && first ? `Olá, ${first}` : step.over}</span>
            <button className="link-button tutorial__skip" onClick={onDone}>{last ? "Fechar" : "Pular tutorial"}</button>
          </div>
          <h2 id="tutorial-title" className="fina tutorial__title">{step.title}</h2>
          <p className="tutorial__text">{step.text}</p>
          {step.points.length > 0 && (
            <ul className="tutorial__points">
              {step.points.map((p) => <li key={p}><Icon name="check" size={15} />{p}</li>)}
            </ul>
          )}
          {last && (
            <div className="tutorial__actions">
              {ACTIONS.map((a) => (
                <button key={a.to} className="ghost-button" onClick={() => { onDone(); navigate(a.to); }}>
                  <Icon name={a.icon} size={16} />{a.label}
                </button>
              ))}
            </div>
          )}
          <div className="tutorial__foot">
            <div className="tutorial__progress" role="tablist" aria-label="Passos do tutorial">
              {STEPS.map((s, i) => (
                <button key={s.title} role="tab" aria-selected={i === index} aria-label={`Passo ${i + 1}: ${s.title}`}
                  className={i <= index ? "is-done" : ""} onClick={() => setIndex(i)} />
              ))}
              <span className="tutorial__count">{index + 1} de {STEPS.length}</span>
            </div>
            <div className="tutorial__nav">
              {index > 0 && <button className="ghost-button" onClick={() => setIndex(index - 1)}>Voltar</button>}
              {last ? (
                <button className="primary-button" onClick={onDone} autoFocus>Começar a usar</button>
              ) : (
                <button className="primary-button" onClick={() => setIndex(index + 1)} autoFocus>
                  {index === 0 ? "Vamos lá" : "Próximo"}<Icon name="send" size={15} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
