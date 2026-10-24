// Python code editor (CodeMirror 6). Loaded lazily: import it through React.lazy.

import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { python } from "@codemirror/lang-python";
import {
  HighlightStyle, bracketMatching, indentOnInput, indentUnit, syntaxHighlighting,
} from "@codemirror/language";
import { EditorState, RangeSetBuilder, StateEffect, StateField, type Extension } from "@codemirror/state";
import {
  Decoration, EditorView, drawSelection, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers,
  type DecorationSet,
} from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { useEffect, useRef } from "react";

export interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
  /** 1-based lines to mark as erroneous. */
  errorLines?: number[];
  ariaLabel?: string;
}

const highlight = HighlightStyle.define([
  { tag: [tags.keyword, tags.controlKeyword, tags.definitionKeyword, tags.operatorKeyword], color: "var(--code-keyword)" },
  { tag: [tags.string, tags.special(tags.string)], color: "var(--code-string)" },
  { tag: [tags.number, tags.bool, tags.null], color: "var(--code-number)" },
  { tag: tags.comment, color: "var(--code-comment)", fontStyle: "italic" },
  { tag: [tags.function(tags.definition(tags.variableName)), tags.definition(tags.className)], color: "var(--code-def)" },
  { tag: tags.propertyName, color: "var(--code-property)" },
]);

const theme = EditorView.theme({
  "&": { height: "100%", fontSize: "12.5px", backgroundColor: "var(--bg-input)", color: "var(--text)" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.55" },
  ".cm-content": { caretColor: "var(--text)" },
  ".cm-gutters": { backgroundColor: "var(--bg-panel)", color: "var(--text-faint)", border: "none" },
  ".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "var(--bg-hover)" },
  "&.cm-focused": { outline: "none" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
    backgroundColor: "var(--primary-soft)",
  },
  ".cm-error-line": { backgroundColor: "var(--danger-soft)" },
});

const setErrors = StateEffect.define<number[]>();
const errorLine = Decoration.line({ class: "cm-error-line" });

const errorField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(decorations, transaction) {
    let next = decorations.map(transaction.changes);
    for (const effect of transaction.effects) {
      if (!effect.is(setErrors)) continue;
      const builder = new RangeSetBuilder<Decoration>();
      const doc = transaction.state.doc;
      for (const line of [...new Set(effect.value)].sort((a, b) => a - b)) {
        if (line >= 1 && line <= doc.lines) builder.add(doc.line(line).from, doc.line(line).from, errorLine);
      }
      next = builder.finish();
    }
    return next;
  },
  provide: (field) => EditorView.decorations.from(field),
});

function extensions(onChange: () => void, onSave: () => void, label: string): Extension[] {
  return [
    lineNumbers(), highlightActiveLineGutter(), highlightActiveLine(), drawSelection(), history(),
    indentOnInput(), bracketMatching(), closeBrackets(), indentUnit.of("    "), EditorState.tabSize.of(4),
    python(), syntaxHighlighting(highlight), theme, errorField,
    keymap.of([
      { key: "Mod-s", preventDefault: true, run: () => (onSave(), true) },
      ...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap, indentWithTab,
    ]),
    EditorView.updateListener.of((update) => update.docChanged && onChange()),
    EditorView.contentAttributes.of({ "aria-label": label }),
  ];
}

export default function CodeEditor({ value, onChange, onSave, errorLines = [], ariaLabel = "Code" }: CodeEditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const callbacks = useRef({ onChange, onSave });
  callbacks.current = { onChange, onSave };

  useEffect(() => {
    if (!host.current) return undefined;
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: extensions(
          () => callbacks.current.onChange(editor.state.doc.toString()),
          () => callbacks.current.onSave?.(),
          ariaLabel,
        ),
      }),
    });
    view.current = editor;
    return () => {
      editor.destroy();
      view.current = null;
    };
    // The editor owns the document after creation; later ``value`` changes come from it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const errorKey = errorLines.join(",");
  useEffect(() => {
    view.current?.dispatch({ effects: setErrors.of(errorLines) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [errorKey]);

  return <div className="code-editor" ref={host} />;
}
