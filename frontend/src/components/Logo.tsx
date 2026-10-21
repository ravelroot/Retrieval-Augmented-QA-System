interface LogoProps {
  size?: number;
  title?: string;
  className?: string;
}

export function LogoMark({ size = 40, title, className }: LogoProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size * 0.7}
      viewBox="62 118 376 262"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <g fill="none" stroke="currentColor" strokeWidth="10" strokeLinejoin="round">
        <rect x="90" y="228" width="68" height="41" rx="4" />
        <rect x="81" y="285" width="86" height="4" rx="2" />
        <rect x="216" y="132" width="68" height="41" rx="4" />
        <rect x="207" y="189" width="86" height="4" rx="2" />
        <rect x="342" y="228" width="68" height="41" rx="4" />
        <rect x="333" y="285" width="86" height="4" rx="2" />
        <rect x="211" y="336" width="78" height="31" rx="15.5" />
      </g>
      <g fill="currentColor">
        <rect x="245" y="196" width="10" height="138" />
        <rect x="70" y="347" width="140" height="9" />
        <rect x="290" y="347" width="140" height="9" />
      </g>
    </svg>
  );
}

export function Wordmark({ size = 34 }: { size?: number }) {
  return (
    <span className="wordmark">
      <LogoMark size={size} />
      <span>Nexo</span>
    </span>
  );
}
