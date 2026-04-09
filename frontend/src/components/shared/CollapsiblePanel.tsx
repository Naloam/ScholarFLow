import { useState, type ReactNode } from "react";

type CollapsiblePanelProps = {
  eyebrow?: string;
  title: string;
  badge?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
};

export function CollapsiblePanel({
  eyebrow,
  title,
  badge,
  defaultOpen = true,
  children,
  className,
  ...rest
}: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section
      className={`panel ${open ? "" : "panel-collapsed"} ${className ?? ""}`}
      data-testid={rest["data-testid"]}
    >
      <div
        className="panel-header panel-toggle-header"
        onClick={() => setOpen((prev) => !prev)}
      >
        <div>
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2 className="panel-title">{title}</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {badge}
          <span className={`panel-chevron ${open ? "panel-chevron-open" : ""}`}>
            &#9662;
          </span>
        </div>
      </div>
      <div
        className={`panel-body ${open ? "panel-body-open" : "panel-body-closed"}`}
      >
        {children}
      </div>
    </section>
  );
}
