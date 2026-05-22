import { useState } from "react";
import type { PipelineStatus } from "../api/types";
import { useUiStore } from "../stores/uiStore";
import { IconChevron } from "./WorkspaceIcons";

type Props = {
  open: boolean;
  onClose: () => void;
  projectId: string;
  pipelineStatus: PipelineStatus | undefined;
  pipelineError?: string | null;
  elementCount?: number | null;
  storeys: string[];
  types: string[];
  filtersReady: boolean;
};

type TreeNode = {
  id: string;
  label: string;
  children?: TreeNode[];
  meta?: string;
  onSelect?: () => void;
  selected?: boolean;
};

function TreeBranch({
  node,
  depth,
  expanded,
  onToggle,
}: {
  node: TreeNode;
  depth: number;
  expanded: Record<string, boolean>;
  onToggle: (id: string) => void;
}) {
  const hasChildren = !!node.children?.length;
  const isOpen = expanded[node.id] ?? depth < 1;

  return (
    <li className="ws-tree-item" style={{ paddingLeft: `${depth * 0.85 + 0.35}rem` }}>
      <div className="ws-tree-row">
        {hasChildren ? (
          <button type="button" className="ws-tree-toggle" onClick={() => onToggle(node.id)} aria-expanded={isOpen}>
            <IconChevron open={isOpen} />
          </button>
        ) : (
          <span className="ws-tree-spacer" />
        )}
        {node.onSelect ? (
          <button
            type="button"
            className={`ws-tree-label-btn ${node.selected ? "selected" : ""}`}
            onClick={node.onSelect}
          >
            {node.label}
          </button>
        ) : (
          <span className="ws-tree-label">{node.label}</span>
        )}
        {node.meta && <span className="ws-tree-meta">{node.meta}</span>}
      </div>
      {hasChildren && (
        <ul className={`ws-tree-children ${isOpen ? "open" : ""}`}>
          {node.children!.map((child) => (
            <TreeBranch key={child.id} node={child} depth={depth + 1} expanded={expanded} onToggle={onToggle} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function WorkspaceSidebar({
  open,
  onClose,
  projectId,
  pipelineStatus,
  pipelineError,
  elementCount,
  storeys,
  types,
  filtersReady,
}: Props) {
  const storeyFilter = useUiStore((s) => s.storeyFilter);
  const typeFilter = useUiStore((s) => s.typeFilter);
  const selectedElementId = useUiStore((s) => s.selectedElementId);
  const setStoreyFilter = useUiStore((s) => s.setStoreyFilter);
  const setTypeFilter = useUiStore((s) => s.setTypeFilter);

  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    project: true,
    filters: true,
    storeys: false,
    types: false,
    selection: true,
  });

  const toggle = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  const storeyNodes: TreeNode[] = [
    {
      id: "storey-all",
      label: "All storeys",
      selected: !storeyFilter,
      onSelect: () => setStoreyFilter(""),
    },
    ...storeys.map((s) => ({
      id: `storey-${s}`,
      label: s,
      selected: storeyFilter === s,
      onSelect: () => setStoreyFilter(s),
    })),
  ];

  const typeNodes: TreeNode[] = [
    {
      id: "type-all",
      label: "All types",
      selected: !typeFilter,
      onSelect: () => setTypeFilter(""),
    },
    ...types.map((t) => ({
      id: `type-${t}`,
      label: t,
      selected: typeFilter === t,
      onSelect: () => setTypeFilter(t),
    })),
  ];

  const tree: TreeNode[] = [
    {
      id: "project",
      label: "Project",
      children: [
        {
          id: "pipeline",
          label: "Pipeline",
          meta: pipelineStatus ?? "…",
        },
        {
          id: "elements",
          label: "Elements",
          meta: elementCount != null ? String(elementCount) : "—",
        },
        {
          id: "project-id",
          label: projectId.slice(0, 12) + "…",
        },
      ],
    },
    {
      id: "filters",
      label: "Filters",
      meta: filtersReady ? "" : "pending",
      children: [
        { id: "storeys", label: "Storey", children: filtersReady ? storeyNodes : [] },
        { id: "types", label: "Component type", children: filtersReady ? typeNodes : [] },
      ],
    },
    {
      id: "selection",
      label: "Selection",
      children: [
        {
          id: "selected-el",
          label: selectedElementId ? `IFC #${selectedElementId}` : "Click model to select",
          meta: selectedElementId ? "active" : "",
        },
      ],
    },
  ];

  if (pipelineError) {
    tree[0]?.children?.push({ id: "pipeline-err", label: "Error", meta: "!" });
  }

  return (
    <>
      <div className={`ws-sidebar-backdrop ${open ? "open" : ""}`} onClick={onClose} aria-hidden={!open} />
      <nav className={`ws-sidebar ${open ? "open" : ""}`} aria-label="Project tools">
        <div className="ws-sidebar-head">
          <span>Explorer</span>
          <button type="button" className="ws-sidebar-close" onClick={onClose} aria-label="Close sidebar">
            ×
          </button>
        </div>
        <ul className="ws-tree">
          {tree.map((node) => (
            <TreeBranch key={node.id} node={node} depth={0} expanded={expanded} onToggle={toggle} />
          ))}
        </ul>
      </nav>
    </>
  );
}
