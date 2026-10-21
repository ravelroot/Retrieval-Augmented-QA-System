import type { InputHTMLAttributes } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function Field({ label, error, hint, id, ...rest }: FieldProps) {
  const fieldId = id ?? `campo-${rest.name}`;
  const describedBy = error ? `${fieldId}-erro` : hint ? `${fieldId}-dica` : undefined;
  return (
    <div className={`field${error ? " field--error" : ""}`}>
      <label htmlFor={fieldId}>{label}</label>
      <input id={fieldId} aria-invalid={!!error} aria-describedby={describedBy} {...rest} />
      {error ? <p className="field__message" id={`${fieldId}-erro`}>{error}</p>
        : hint ? <p className="field__hint" id={`${fieldId}-dica`}>{hint}</p> : null}
    </div>
  );
}
