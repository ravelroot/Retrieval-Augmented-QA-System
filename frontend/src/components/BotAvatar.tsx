interface Props {
  name: string;
  color: string;
  size?: number;
}

export function BotAvatar({ name, color, size = 40 }: Props) {
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <span className="bot-avatar" aria-hidden="true"
      style={{ width: size, height: size, background: color || "#000000", fontSize: Math.round(size * 0.46) }}>
      {initial}
    </span>
  );
}

export const BOT_COLORS = ["#000000", "#4d4b4b", "#2b4c5a", "#3e6b2a", "#7a5a12", "#9b2f1e", "#5b4a7a", "#1f5f5b"];
