import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

const citationPattern = /\[(\d+(?:,\s*\d+)*)\]/g;
const evidencePattern = /\[NEEDS_EVIDENCE\]/g;

function buildDecorations(doc: Parameters<typeof DecorationSet.create>[0]) {
  const decorations: Decoration[] = [];

  doc.descendants((node, position) => {
    if (!node.isText) {
      return true;
    }

    const text = node.text ?? "";

    for (const match of text.matchAll(evidencePattern)) {
      const start = position + (match.index ?? 0);
      decorations.push(
        Decoration.inline(start, start + match[0].length, {
          class: "token-needs-evidence",
        }),
      );
    }

    for (const match of text.matchAll(citationPattern)) {
      const start = position + (match.index ?? 0);
      decorations.push(
        Decoration.inline(start, start + match[0].length, {
          class: "token-citation",
        }),
      );
    }

    return true;
  });

  return DecorationSet.create(doc, decorations);
}

export const MarkerHighlighter = Extension.create({
  name: "markerHighlighter",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("markerHighlighter"),
        state: {
          init: (_, state) => buildDecorations(state.doc),
          apply: (transaction, previous, _oldState, newState) => {
            if (!transaction.docChanged && !transaction.selectionSet) {
              return previous;
            }
            return buildDecorations(newState.doc);
          },
        },
        props: {
          decorations(state) {
            return this.getState(state);
          },
        },
      }),
    ];
  },
});
