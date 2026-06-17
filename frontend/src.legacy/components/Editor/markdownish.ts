import type { JSONContent } from "@tiptap/core";

type MarkType = "bold" | "italic";

function textNode(text: string, marks: MarkType[] = []): JSONContent {
  return {
    type: "text",
    text,
    ...(marks.length > 0
      ? {
          marks: marks.map((mark) => ({ type: mark })),
        }
      : {}),
  };
}

function parseInlineMarkdown(text: string): JSONContent[] {
  const content: JSONContent[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const token = text.startsWith("***", cursor)
      ? "***"
      : text.startsWith("**", cursor)
        ? "**"
        : text[cursor] === "*"
          ? "*"
          : null;

    if (!token) {
      const nextToken = text.slice(cursor).search(/\*{1,3}/);
      const end = nextToken === -1 ? text.length : cursor + nextToken;
      content.push(textNode(text.slice(cursor, end)));
      cursor = end;
      continue;
    }

    const end = text.indexOf(token, cursor + token.length);
    if (end === -1 || end === cursor + token.length) {
      content.push(textNode(token));
      cursor += token.length;
      continue;
    }

    const marks: MarkType[] =
      token === "***"
        ? ["bold", "italic"]
        : token === "**"
          ? ["bold"]
          : ["italic"];
    content.push(textNode(text.slice(cursor + token.length, end), marks));
    cursor = end + token.length;
  }

  return content;
}

function linesToInlineContent(lines: string[]): JSONContent[] {
  const content: JSONContent[] = [];

  lines.forEach((line, index) => {
    if (index > 0) {
      content.push({ type: "hardBreak" });
    }
    if (line.length > 0) {
      content.push(...parseInlineMarkdown(line));
    }
  });

  return content;
}

function itemToListNode(text: string): JSONContent {
  return {
    type: "listItem",
    content: [
      {
        type: "paragraph",
        content: text ? parseInlineMarkdown(text) : [],
      },
    ],
  };
}

export function markdownToDocument(markdown: string): JSONContent {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const content: JSONContent[] = [];
  let paragraphLines: string[] = [];
  let bulletItems: string[] = [];

  const flushParagraph = () => {
    if (!paragraphLines.length) {
      return;
    }
    content.push({
      type: "paragraph",
      content: linesToInlineContent(paragraphLines),
    });
    paragraphLines = [];
  };

  const flushBulletList = () => {
    if (!bulletItems.length) {
      return;
    }
    content.push({
      type: "bulletList",
      content: bulletItems.map(itemToListNode),
    });
    bulletItems = [];
  };

  for (const line of lines) {
    if (line.startsWith("# ")) {
      flushParagraph();
      flushBulletList();
      content.push({
        type: "heading",
        attrs: { level: 1 },
        content: line.slice(2) ? parseInlineMarkdown(line.slice(2)) : [],
      });
      continue;
    }

    if (line.startsWith("## ")) {
      flushParagraph();
      flushBulletList();
      content.push({
        type: "heading",
        attrs: { level: 2 },
        content: line.slice(3) ? parseInlineMarkdown(line.slice(3)) : [],
      });
      continue;
    }

    if (line.startsWith("- ")) {
      flushParagraph();
      bulletItems.push(line.slice(2));
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      flushBulletList();
      continue;
    }

    flushBulletList();
    paragraphLines.push(line);
  }

  flushParagraph();
  flushBulletList();

  return {
    type: "doc",
    content: content.length > 0 ? content : [{ type: "paragraph" }],
  };
}

function inlineToText(node?: JSONContent): string {
  if (!node) {
    return "";
  }
  if (node.type === "text") {
    const text = node.text ?? "";
    const marks = new Set((node.marks ?? []).map((mark) => mark.type));
    if (marks.has("bold") && marks.has("italic")) {
      return `***${text}***`;
    }
    if (marks.has("bold")) {
      return `**${text}**`;
    }
    if (marks.has("italic")) {
      return `*${text}*`;
    }
    return text;
  }
  if (node.type === "hardBreak") {
    return "\n";
  }
  return (node.content ?? []).map(inlineToText).join("");
}

function nodeToMarkdown(node?: JSONContent): string[] {
  if (!node) {
    return [];
  }

  if (node.type === "heading") {
    const level = Number(node.attrs?.level ?? 1);
    const prefix = level === 1 ? "# " : "## ";
    return [`${prefix}${(node.content ?? []).map(inlineToText).join("")}`];
  }

  if (node.type === "paragraph") {
    return [(node.content ?? []).map(inlineToText).join("")];
  }

  if (node.type === "bulletList") {
    return (node.content ?? []).flatMap((item) => {
      const paragraph = item.content?.find(
        (child) => child.type === "paragraph",
      );
      const text = (paragraph?.content ?? []).map(inlineToText).join("");
      return [`- ${text}`];
    });
  }

  return (node.content ?? []).flatMap(nodeToMarkdown);
}

export function documentToMarkdown(document: JSONContent): string {
  return (document.content ?? [])
    .flatMap(nodeToMarkdown)
    .join("\n\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
