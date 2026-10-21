import type { ReactNode } from "react";

interface Props {
  text: string;
  sources: number;
  active: number | null;
  onCite: (rank: number) => void;
}

function inline(text: string, props: Props, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|\[\d+\])/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = pattern.exec(text))) {
    if (match.index > last) out.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) out.push(<strong key={`${key}-${i}`}>{token.slice(2, -2)}</strong>);
    else {
      const rank = Number(token.slice(1, -1));
      if (rank >= 1 && rank <= props.sources) {
        out.push(
          <button key={`${key}-${i}`} type="button" className={`cite${props.active === rank ? " cite--active" : ""}`}
            onClick={() => props.onCite(rank)} aria-label={`Ver trecho ${rank}`}>
            {rank}
          </button>,
        );
      } else out.push(token);
    }
    last = match.index + token.length;
    i += 1;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function AnswerText(props: Props) {
  const blocks: ReactNode[] = [];
  const lines = props.text.split("\n");
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (!list) return;
    const items = list.items.map((item, i) => <li key={i}>{inline(item, props, `l${blocks.length}-${i}`)}</li>);
    blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trim();
    const bullet = /^[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\d+[.)]\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      const ordered = !!numbered;
      if (!list || list.ordered !== ordered) {
        flush();
        list = { ordered, items: [] };
      }
      list.items.push((bullet ?? numbered)![1]);
      continue;
    }
    flush();
    if (line) blocks.push(<p key={blocks.length}>{inline(line, props, `p${blocks.length}`)}</p>);
  }
  flush();
  return <div className="answer-text">{blocks}</div>;
}
