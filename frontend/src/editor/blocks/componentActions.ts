// Commands on components (macro blocks): group, create, enter/leave, expand.

import { ApiError, api, errorMessage } from "../../api/client";
import type { ComponentBundle, ComponentUsage } from "../../api/dynamic";
import type { Graph } from "../../api/types";
import { componentIdOf, emptyComponent } from "../../lib/components";
import { downloadText } from "../../lib/download";
import { useCatalogStore } from "../../store/catalogStore";
import { isDirty, sessionGraph, useComponentStore } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";
import { notify, useUiStore } from "../../store/uiStore";

function addedNodes(before: Graph, after: Graph): string[] {
  const known = new Set(before.nodes.map((node) => node.id));
  return after.nodes.filter((node) => !known.has(node.id)).map((node) => node.id);
}

async function libraryChanged(): Promise<void> {
  await Promise.all([useComponentStore.getState().loadLibrary(), useCatalogStore.getState().refresh()]);
}

/** Replaces the selected elements by one instance of a new component (undoable). */
export async function groupSelection(nodeIds: string[], name: string, id: string): Promise<boolean> {
  const before = useGraphStore.getState().graph;
  try {
    const result = await api.groupIntoComponent(before, nodeIds, id, name);
    await libraryChanged();
    useGraphStore.getState().commit(result.graph);
    useUiStore.getState().select(addedNodes(before, result.graph).slice(0, 1), []);
    notify({ level: "success", title: `Grouped ${nodeIds.length} elements into "${result.component.name}"`, timeout: 3000 });
    return true;
  } catch (error) {
    notify({ level: "error", title: "Could not group into a component", message: errorMessage(error) });
    return false;
  }
}

/** Creates an empty component in the library and opens it. */
export async function createComponent(name: string, id: string): Promise<boolean> {
  try {
    await api.saveComponent(emptyComponent(id, name));
    await libraryChanged();
  } catch (error) {
    notify({ level: "error", title: "Could not create the component", message: errorMessage(error) });
    return false;
  }
  return openComponent(id);
}

/** Opens a library definition (no runtime data: it is not an instance). */
export async function openComponent(id: string): Promise<boolean> {
  return enterComponent(id, []);
}

/** Opens the definition behind an instance node of the canvas, with its runtime data. */
export async function enterInstance(nodeId: string): Promise<boolean> {
  const node = useGraphStore.getState().graph.nodes.find((n) => n.id === nodeId);
  const id = node ? componentIdOf(node.factory) : null;
  if (!id) return false;
  const sessions = useComponentStore.getState().sessions;
  const parent = sessions[sessions.length - 1];
  // Inside a definition opened from the library there is no instance path to follow.
  const path = !parent ? [nodeId] : parent.path.length ? [...parent.path, nodeId] : [];
  return enterComponent(id, path);
}

async function enterComponent(id: string, path: string[]): Promise<boolean> {
  if (useComponentStore.getState().sessions.some((session) => session.base.id === id)) {
    notify({ level: "warning", title: `"${id}" is already open`, message: "A component cannot contain itself." });
    return false;
  }
  const entered = await useComponentStore.getState().enter(id, path);
  if (entered) {
    useUiStore.getState().select([], []);
    useUiStore.getState().requestFit();
  }
  return entered;
}

/** Leaves open components until ``depth`` remain, confirming when that loses unsaved edits. */
export function leaveTo(depth: number): boolean {
  const { sessions, exitTo } = useComponentStore.getState();
  const leaving = sessions.map((session, index) => ({ session, index })).slice(depth);
  const dirty = leaving.filter(({ session, index }) => isDirty(session, sessionGraph(index, sessions)));
  if (dirty.length && !window.confirm(
    `Leave without saving? Unsaved changes to ${dirty.map(({ session }) => `"${session.name}"`).join(", ")} are lost.`,
  )) return false;
  exitTo(depth);
  useUiStore.getState().select([], []);
  useUiStore.getState().requestFit();
  return true;
}

/** Saves the innermost component; every project using it gets the new definition. */
export async function saveComponent(): Promise<boolean> {
  return useComponentStore.getState().save();
}

export function discardComponent(): void {
  const session = useComponentStore.getState().sessions.at(-1);
  if (session && window.confirm(`Discard the unsaved changes to "${session.name}"?`)) {
    useComponentStore.getState().discard();
  }
}

function usageText(usage: ComponentUsage): string {
  const users = [
    ...usage.components.map((c) => `component "${c.name}"`),
    ...usage.projects.map((p) => `project "${p.name}"`),
  ];
  if (!users.length) return "No project or component uses it.";
  const shown = users.slice(0, 8).join(", ") + (users.length > 8 ? ` and ${users.length - 8} more` : "");
  return `Used by ${shown}: their instances and slots stop working.`;
}

/** Deletes the innermost open component from the library (after confirming who breaks) and leaves it. */
export async function deleteCurrentComponent(): Promise<boolean> {
  const { sessions, exitTo } = useComponentStore.getState();
  const session = sessions.at(-1);
  if (!session) return false;
  try {
    const usage = await api.componentUsage(session.base.id);
    if (!window.confirm(`Delete "${session.name}" from the library?\n\n${usageText(usage)}`)) return false;
    await api.deleteComponent(session.base.id);
  } catch (error) {
    notify({ level: "error", title: "Could not delete the component", message: errorMessage(error) });
    return false;
  }
  exitTo(sessions.length - 1);
  await libraryChanged();
  useUiStore.getState().select([], []);
  useUiStore.getState().requestFit();
  notify({ level: "success", title: `Deleted "${session.name}"`, timeout: 3000 });
  return true;
}

/** Copies a starter component into the library. */
export async function installStarter(id: string, name: string): Promise<boolean> {
  try {
    await api.installStarter(id);
    await libraryChanged();
    notify({ level: "success", title: `"${name}" added to the library`, message: "Find it in the palette under Components.", timeout: 4000 });
    return true;
  } catch (error) {
    notify({ level: "error", title: `Could not add "${name}"`, message: errorMessage(error) });
    return false;
  }
}

/** Downloads a component (and the components inside it) as a file to share. */
export async function exportComponentFile(id: string): Promise<void> {
  try {
    const bundle = await api.componentBundle(id);
    downloadText(JSON.stringify(bundle, null, 2), `${id}.pipelab-component.json`, "application/json");
  } catch (error) {
    notify({ level: "error", title: "Could not export the component", message: errorMessage(error) });
  }
}

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("unreadable file"));
    reader.readAsText(file);
  });
}

/** Reads a component file into the library, asking before replacing components with the same id. */
export async function importComponentFile(file: File): Promise<boolean> {
  let bundle: ComponentBundle;
  try {
    bundle = JSON.parse(await readText(file)) as ComponentBundle;
    if (bundle.format !== "pipelab-components" || !Array.isArray(bundle.components)) throw new Error("not a component file");
  } catch (error) {
    notify({ level: "error", title: `${file.name} is not a Pipelab component file`, message: errorMessage(error) });
    return false;
  }
  try {
    let result;
    try {
      result = await api.importComponents(bundle);
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 409)) throw error;
      if (!window.confirm(`Replace the library versions? ${error.message}`)) return false;
      result = await api.importComponents(bundle, true);
    }
    await libraryChanged();
    notify({ level: "success", title: `Imported ${result.imported.join(", ")}`, timeout: 4000 });
    return true;
  } catch (error) {
    notify({ level: "error", title: "Could not import the components", message: errorMessage(error) });
    return false;
  }
}

/** Replaces an instance by the elements of its definition (undoable). */
export async function expandInstance(nodeId: string): Promise<boolean> {
  const before = useGraphStore.getState().graph;
  try {
    const graph = await api.expandInstance(before, nodeId);
    useGraphStore.getState().commit(graph);
    useUiStore.getState().select(addedNodes(before, graph), []);
    return true;
  } catch (error) {
    notify({ level: "error", title: "Could not expand the component", message: errorMessage(error) });
    return false;
  }
}
