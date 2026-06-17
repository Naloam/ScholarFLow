// Read-only render of paper/draft.md with inline [UNVERIFIED: ...] highlighting.
//
// The AuditorAgent inserts `**[UNVERIFIED: reason]**` after each unsupported
// claim. We render the draft as faithful markdown (structure + tables intact) and
// additionally wrap every [UNVERIFIED ...] span in a red <mark> so a human can
// see exactly which claims the evidence gate rejected — without reframing any
// of the surrounding, honest text.
import { memo, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface PaperDraftProps {
  source: string;
}

// Matches ` [UNVERIFIED: ...]` markers the auditor inserts. Tolerant to the
// surrounding bold (**), so it works whether the marker was wrapped or not.
const UNVERIFIED_RE = /\[UNVERIFIED(?::([^\]]+))?\]/g;

function highlightInline(text: string, keyPrefix: string): ReactNode[] {
  // Split the string on each [UNVERIFIED ...] marker and interleave red marks.
  const out: ReactNode[] = [];
  let last = 0;
  UNVERIFIED_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = UNVERIFIED_RE.exec(text)) !== null) {
    if (match.index > last) {
      out.push(text.slice(last, match.index));
    }
    const reason = match[1]?.trim();
    out.push(
      <mark
        key={`${keyPrefix}-uv-${i}`}
        className="unverified"
        title={reason ? `Unverified claim: ${reason}` : "Unverified claim"}
      >
        [UNVERIFIED{reason ? `: ${reason}` : ""}]
      </mark>,
    );
    last = match.index + match[0].length;
    i += 1;
  }
  if (last < text.length) {
    out.push(text.slice(last));
  }
  return out;
}

// Walk React children; any string node containing [UNVERIFIED] is split + marked.
function highlightChildren(nodes: ReactNode, keyPrefix: string): ReactNode {
  if (nodes == null || typeof nodes === "boolean") {
    return nodes;
  }
  if (typeof nodes === "string") {
    return UNVERIFIED_RE.test(nodes) ? highlightInline(nodes, keyPrefix) : nodes;
  }
  if (Array.isArray(nodes)) {
    return nodes.map((n, i) => highlightChildren(n, `${keyPrefix}-${i}`));
  }
  return nodes;
}

const components: Components = {
  p: ({ children }) => <p>{highlightChildren(children, "p")}</p>,
  li: ({ children }) => <li>{highlightChildren(children, "li")}</li>,
  blockquote: ({ children }) => (
    <blockquote>{highlightChildren(children, "bq")}</blockquote>
  ),
  td: ({ children }) => <td>{highlightChildren(children, "td")}</td>,
  // Recurse into inline emphasis so a marker inside bold/italic text is still caught
  // (defense in depth — the auditor emits a bare marker, but be tolerant of bold wrapping).
  strong: ({ children }) => <strong>{highlightChildren(children, "strong")}</strong>,
  em: ({ children }) => <em>{highlightChildren(children, "em")}</em>,
};

function PaperDraftImpl({ source }: PaperDraftProps) {
  return (
    <div className="markdown paper-draft">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {source}
      </ReactMarkdown>
    </div>
  );
}

export const PaperDraft = memo(PaperDraftImpl);
