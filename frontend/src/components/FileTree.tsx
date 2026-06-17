// File tree for the Workspace view. Renders the fixed workspace layout; the
// selected path is highlighted. Clicking a node calls onSelect(path).
import type { WorkspaceNode } from "../lib/workspaceLayout";

interface FileTreeProps {
  nodes: WorkspaceNode[];
  selectedPath: string;
  onSelect: (path: string) => void;
}

function NodeRow({
  node,
  depth,
  selectedPath,
  onSelect,
}: {
  node: WorkspaceNode;
  depth: number;
  selectedPath: string;
  onSelect: (path: string) => void;
}) {
  const isLeaf = !node.children;
  const selected = node.path === selectedPath;
  const style = { paddingLeft: `${12 + depth * 14}px` };

  if (isLeaf) {
    return (
      <button
        type="button"
        className={`filetree__leaf${selected ? " filetree__leaf--selected" : ""}`}
        style={style}
        onClick={() => onSelect(node.path)}
      >
        <span className="filetree__name">{node.name}</span>
      </button>
    );
  }

  return (
    <div className="filetree__group">
      <div className="filetree__dir" style={style}>
        {node.name}
      </div>
      {node.children?.map((child) => (
        <NodeRow
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

export function FileTree({ nodes, selectedPath, onSelect }: FileTreeProps) {
  return (
    <nav className="filetree" aria-label="Workspace files">
      {nodes.map((node) => (
        <NodeRow
          key={node.path}
          node={node}
          depth={0}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </nav>
  );
}
