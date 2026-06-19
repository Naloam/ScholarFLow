// V3 editable paper (goal_session11): view/edit dual-mode + re-audit closure.
//
// view: the existing faithful read-only render (PaperDraft, incl. [UNVERIFIED]
//       red marks) — byte-equivalent to the pre-V3 behaviour when there is no
//       draft or the user is just reading.
// edit: a TipTap rich-text editor round-tripping markdown (tiptap-markdown).
//
// Honesty closure: "Save" writes paper/draft.md; "Re-run audit" re-applies the
// Auditor to the (human-edited) draft — a newly-added unsupported claim is marked
// [UNVERIFIED] and fails the gate. The human collaborates with the gate, never
// bypasses it. An unsaved edit guards navigation (beforeunload + react-router).
import { useCallback, useEffect, useRef, useState } from "react";
import { useBlocker, type BlockerFunction } from "react-router-dom";
import { type Editor, EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "tiptap-markdown";

import { reauditPaper, savePaperDraft } from "../api/client";
import type { ReauditResponse } from "../api/types";
import { PaperDraft } from "./PaperDraft";

// tiptap-markdown augments the editor storage with a `markdown` namespace; TS
// doesn't see it, so access it through a narrow typed accessor (no `any`).
interface MarkdownStorage {
  markdown?: { getMarkdown?: () => string };
}
function getMarkdown(editor: Editor | null): string {
  if (!editor || editor.isDestroyed) return "";
  const storage = editor.storage as unknown as MarkdownStorage;
  return storage.markdown?.getMarkdown?.() ?? "";
}

interface PaperEditorProps {
  projectId: string;
  draft: string;
  /** Called after a save or re-audit so the page reloads draft + ledger from disk. */
  onChanged: () => void;
}

type Mode = "view" | "edit";

export function PaperEditor({ projectId, draft, onChanged }: PaperEditorProps) {
  const [mode, setMode] = useState<Mode>("view");
  const [busy, setBusy] = useState<"save" | "reaudit" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reaudit, setReaudit] = useState<ReauditResponse | null>(null);
  // The markdown the editor is editing (snapshot at edit-entry time).
  const editingRef = useRef<string>(draft);

  const editor = useEditor({
    extensions: [StarterKit, Markdown.configure({ html: false, breaks: true })],
    content: draft,
    editorProps: { attributes: { class: "paper-editor__tiptap" } },
  });

  // Re-initialize the editor content when entering edit mode or when the draft
  // changes externally while not editing.
  useEffect(() => {
    if (mode === "edit" && editor && !editor.isDestroyed) {
      editor.commands.setContent(draft, { emitUpdate: false });
      editingRef.current = draft;
    }
  }, [mode, editor, draft]);

  const dirty =
    mode === "edit" &&
    editor != null &&
    !editor.isDestroyed &&
    getMarkdown(editor) !== editingRef.current;

  // Guard tab close + in-app navigation on unsaved edits.
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useBlocker(useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
    [dirty],
  ));

  const handleSave = useCallback(async () => {
    if (!editor || editor.isDestroyed) return;
    const markdown = getMarkdown(editor);
    setBusy("save");
    setMessage(null);
    try {
      await savePaperDraft(projectId, markdown);
      editingRef.current = markdown;
      setMode("view");
      onChanged();
    } catch (err) {
      setMessage(err instanceof Error ? `Save failed: ${err.message}` : "Save failed");
    } finally {
      setBusy(null);
    }
  }, [editor, projectId, onChanged]);

  const handleReaudit = useCallback(async () => {
    setBusy("reaudit");
    setMessage(null);
    try {
      const result = await reauditPaper(projectId);
      setReaudit(result);
      onChanged(); // reload annotated draft + ledger from disk
    } catch (err) {
      setMessage(err instanceof Error ? `Re-audit failed: ${err.message}` : "Re-audit failed");
    } finally {
      setBusy(null);
    }
  }, [projectId, onChanged]);

  return (
    <div className="paper-editor">
      <div className="paper-editor__toolbar" role="toolbar" aria-label="Paper draft actions">
        {mode === "view" ? (
          <button className="btn btn--ghost" onClick={() => setMode("edit")}>
            ✏️ Edit draft
          </button>
        ) : (
          <>
            <button
              className="btn"
              type="button"
              disabled={!editor}
              onClick={() => editor?.chain().focus().toggleBold().run()}
              aria-label="Bold"
            >
              B
            </button>
            <button
              className="btn"
              type="button"
              disabled={!editor}
              onClick={() => editor?.chain().focus().toggleItalic().run()}
              aria-label="Italic"
            >
              <em>I</em>
            </button>
            <button
              className="btn"
              type="button"
              disabled={!editor}
              onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
            >
              H2
            </button>
            <button
              className="btn"
              type="button"
              disabled={!editor}
              onClick={() => editor?.chain().focus().toggleBulletList().run()}
            >
              • List
            </button>
            <button
              className="btn"
              type="button"
              disabled={!editor}
              onClick={() => editor?.chain().focus().toggleOrderedList().run()}
            >
              1. List
            </button>
            <span className="paper-editor__spacer" />
            <button className="btn btn--ghost" onClick={() => setMode("view")} disabled={busy !== null}>
              Cancel
            </button>
            <button className="btn" onClick={handleSave} disabled={busy !== null}>
              {busy === "save" ? "Saving…" : "Save draft"}
            </button>
          </>
        )}
        <button
          className="btn btn--ghost"
          onClick={handleReaudit}
          disabled={busy !== null || mode === "edit"}
          title="Re-run the Auditor on the current draft"
        >
          {busy === "reaudit" ? "Auditing…" : "🔍 Re-run audit"}
        </button>
      </div>

      {message ? <p className="paper-editor__msg paper-editor__msg--err" role="alert">{message}</p> : null}
      {reaudit ? (
        <p className={`paper-editor__msg ${reaudit.gate ? "" : "paper-editor__msg--warn"}`}>
          Re-audit: gate <strong>{reaudit.gate ? "passed" : "FAILED"}</strong>
          {typeof reaudit.unverified_count === "number"
            ? ` · ${reaudit.unverified_count} unverified claim${reaudit.unverified_count === 1 ? "" : "s"}`
            : ""}
          {reaudit.skipped ? ` · ${reaudit.reason ?? "skipped"}` : ""}
        </p>
      ) : null}

      {mode === "view" ? (
        <PaperDraft source={draft} />
      ) : (
        <div className="paper-editor__edit">
          <EditorContent editor={editor} />
          {dirty ? <p className="paper-editor__hint">Unsaved changes — leaving the page will prompt to confirm.</p> : null}
        </div>
      )}
    </div>
  );
}
