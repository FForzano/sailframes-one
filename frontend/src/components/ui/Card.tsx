import type { ReactNode } from "react";

export function Card({
  title,
  children,
  className = "",
}: {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`sf-card ${className}`}>
      {title && <h2 className="sf-card__title">{title}</h2>}
      {children}
    </section>
  );
}
