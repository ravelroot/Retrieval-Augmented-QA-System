import type { ReactNode } from "react";

const STOP = new Set(("a o as os um uma de do da dos das e em no na nos nas por para com sem que se ao aos é ser como " +
  "mais mas ou sua seu suas seus este esta isso isto esse essa qual quais quando onde devo deve fazer the of and to in is " +
  "are for on with by an be this that it as at from or").split(" "));

function fold(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function terms(query: string): string[] {
  return Array.from(new Set(fold(query).match(/[a-z0-9]+(?:[.,][0-9]+)?/g) ?? []))
    .filter((w) => (w.length > 2 || /\d/.test(w)) && !STOP.has(w));
}

export function Highlight({ text, query }: { text: string; query: string }) {
  const words = terms(query);
  if (!words.length) return <>{text}</>;
  const folded = fold(text);
  const marks: [number, number][] = [];
  for (const word of words) {
    const stem = word.length > 5 ? word.slice(0, word.length - 2) : word;
    let at = folded.indexOf(stem);
    while (at !== -1) {
      const before = at === 0 ? " " : folded[at - 1];
      if (!/[a-z0-9]/.test(before)) {
        let end = at + stem.length;
        while (end < folded.length && /[a-z0-9]/.test(folded[end])) end += 1;
        marks.push([at, end]);
      }
      at = folded.indexOf(stem, at + stem.length);
    }
  }
  if (!marks.length) return <>{text}</>;
  marks.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const m of marks) {
    const last = merged[merged.length - 1];
    if (last && m[0] <= last[1] + 1) last[1] = Math.max(last[1], m[1]);
    else merged.push([...m]);
  }
  const out: ReactNode[] = [];
  let pos = 0;
  merged.forEach(([s, e], i) => {
    if (s > pos) out.push(text.slice(pos, s));
    out.push(<mark key={i}>{text.slice(s, e)}</mark>);
    pos = e;
  });
  if (pos < text.length) out.push(text.slice(pos));
  return <>{out}</>;
}
