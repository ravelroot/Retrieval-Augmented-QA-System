interface LogoProps {
  size?: number;
  title?: string;
  className?: string;
}

export function LogoMark({ size = 40, title, className }: LogoProps) {
  const altura = size * 0.52;
  return (
    <svg
      className={className}
      width={(altura * 64) / 68}
      height={altura}
      viewBox="18 16 64 68"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <g fill="currentColor">
        <rect x="18" y="16" width="18" height="68" />
        <rect x="64" y="16" width="18" height="68" />
      </g>
      <path d="M36 18L64 82" fill="none" stroke="currentColor" strokeWidth="3.5" />
    </svg>
  );
}

export function Brand({ subtitle = "Respostas com fonte", inverted = false }: { subtitle?: string; inverted?: boolean }) {
  return (
    <span className={`brand${inverted ? " brand--inverted" : ""}`}>
      <span className="brand__mark">
        <LogoMark size={34} />
      </span>
      <span className="brand__text">
        <span className="brand__name">Nexo</span>
        {subtitle && <span className="brand__sub">{subtitle}</span>}
      </span>
    </span>
  );
}
