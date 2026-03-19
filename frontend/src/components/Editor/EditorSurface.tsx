import { useEffect, useRef } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import Placeholder from "@tiptap/extension-placeholder";
import StarterKit from "@tiptap/starter-kit";

import { MarkerHighlighter } from "./MarkerHighlighter";
import { documentToMarkdown, markdownToDocument } from "./markdownish";

type EditorSurfaceProps = {
  content: string;
  working: boolean;
  canEdit: boolean;
  onChange: (content: string) => void;
  onFocusText: (content: string) => void;
  onSave: () => Promise<void>;
  onGenerate: () => Promise<void>;
  onReview: () => Promise<void>;
  onExport: (format: "markdown" | "latex" | "word" | "docx") => Promise<void>;
};

function currentSelectionText(editor: NonNullable<ReturnType<typeof useEditor>>): string {
  const { from, to } = editor.state.selection;
  const direct = editor.state.doc.textBetween(from, to, " ").trim();
  if (direct) {
    return direct;
  }

  let blockText = "";
  editor.state.doc.nodesBetween(from, to, (node) => {
    if (blockText || !node.isTextblock) {
      return true;
    }
    blockText = node.textContent.trim();
    return false;
  });
  return blockText;
}

export function EditorSurface({
  content,
  working,
  canEdit,
  onChange,
  onFocusText,
  onSave,
  onGenerate,
  onReview,
  onExport,
}: EditorSurfaceProps) {
  const lastSerialized = useRef(content);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder: "Draft content will appear here...",
      }),
      MarkerHighlighter,
    ],
    content: markdownToDocument(content),
    editable: canEdit,
    immediatelyRender: false,
    onSelectionUpdate({ editor: currentEditor }) {
      onFocusText(currentSelectionText(currentEditor));
    },
    onUpdate({ editor: currentEditor }) {
      const markdown = documentToMarkdown(currentEditor.getJSON());
      lastSerialized.current = markdown;
      onChange(markdown);
    },
  });

  useEffect(() => {
    if (!editor) {
      return;
    }
    editor.setEditable(canEdit);
  }, [canEdit, editor]);

  useEffect(() => {
    if (!editor) {
      return;
    }
    if (content === lastSerialized.current) {
      return;
    }
    editor.commands.setContent(markdownToDocument(content), false);
    lastSerialized.current = content;
  }, [content, editor]);

  return (
    <section className="panel panel-editor" data-testid="editor-surface">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Workspace Core</p>
          <h2 className="panel-title">Editor Surface</h2>
        </div>
        <span className="badge badge-soft">TipTap live</span>
      </div>

      <div className="button-row">
        <button
          className="primary-btn"
          data-testid="generate-draft-button"
          disabled={working || !canEdit}
          onClick={() => void onGenerate()}
        >
          Generate Draft
        </button>
        <button
          className="ghost-btn"
          data-testid="save-draft-button"
          disabled={working || !canEdit}
          onClick={() => void onSave()}
        >
          Save Draft
        </button>
        <button
          className="ghost-btn"
          data-testid="run-review-button"
          disabled={working || !canEdit}
          onClick={() => void onReview()}
        >
          Run Review
        </button>
        <button
          className="ghost-btn"
          data-testid="export-markdown-button"
          disabled={working || !canEdit}
          onClick={() => void onExport("markdown")}
        >
          Export MD
        </button>
        <button className="ghost-btn" disabled={working || !canEdit} onClick={() => void onExport("latex")}>
          Export TeX
        </button>
        <button className="ghost-btn" disabled={working || !canEdit} onClick={() => void onExport("word")}>
          Export DOCX
        </button>
      </div>

      <div className="toolbar-row">
        <button
          className="toolbar-btn"
          disabled={!editor || !canEdit}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          Bold
        </button>
        <button
          className="toolbar-btn"
          disabled={!editor || !canEdit}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        >
          Italic
        </button>
        <button
          className="toolbar-btn"
          disabled={!editor || !canEdit}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
        >
          H1
        </button>
        <button
          className="toolbar-btn"
          disabled={!editor || !canEdit}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
        >
          H2
        </button>
        <button
          className="toolbar-btn"
          disabled={!editor || !canEdit}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        >
          List
        </button>
      </div>

      <div className="editor-hint">
        Citation markers like [1] and unsupported claims like [NEEDS_EVIDENCE] are highlighted by
        a custom TipTap plugin. The right sidebar stays aligned to the paragraph you are editing.
      </div>

      <div
        className={canEdit ? "editor-prose" : "editor-prose editor-readonly"}
        data-testid="editor-prose"
      >
        <EditorContent editor={editor} />
      </div>
    </section>
  );
}
