// Read-only markdown renderer (react-markdown + GFM tables). Safe by default —
// raw HTML is not rendered. Used for research_report.md, reviewer markdown, etc.
import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownViewProps {
  source: string;
  className?: string;
}

function MarkdownViewImpl({ source, className }: MarkdownViewProps) {
  return (
    <div className={["markdown", className].filter(Boolean).join(" ")}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{source}</ReactMarkdown>
    </div>
  );
}

export const MarkdownView = memo(MarkdownViewImpl);
