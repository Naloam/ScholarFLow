// The research-harness workspace has a fixed layout (plan §5.2). Rather than
// add a directory-listing endpoint, we render this known tree and let the file
// viewer 404 gracefully for files a given run hasn't produced yet. This keeps
// the backend API at the 5 mandated endpoints and makes the Workspace view
// deterministic.

export interface WorkspaceNode {
  name: string;
  path: string; // workspace-relative path (the API file_path)
  children?: WorkspaceNode[];
}

const leaf = (name: string, path: string): WorkspaceNode => ({ name, path });

export const WORKSPACE_TREE: WorkspaceNode[] = [
  {
    name: "literature",
    path: "literature",
    children: [
      leaf("search_queries.json", "literature/search_queries.json"),
      leaf("papers.jsonl", "literature/papers.jsonl"),
      leaf("notes.md", "literature/notes.md"),
      leaf("gap_map.md", "literature/gap_map.md"),
      leaf("known_baselines.md", "literature/known_baselines.md"),
    ],
  },
  {
    name: "ideas",
    path: "ideas",
    children: [
      leaf("candidates.json", "ideas/candidates.json"),
      leaf("selected.md", "ideas/selected.md"),
    ],
  },
  {
    name: "experiments",
    path: "experiments",
    children: [
      leaf("plan.md", "experiments/plan.md"),
      leaf("plan.json", "experiments/plan.json"),
    ],
  },
  {
    name: "code",
    path: "code",
    children: [
      leaf("experiment.py", "code/experiment.py"),
      leaf("requirements.txt", "code/requirements.txt"),
    ],
  },
  {
    name: "artifacts",
    path: "artifacts",
    children: [
      leaf("metrics.json", "artifacts/metrics.json"),
      leaf("logs/run_1.log", "artifacts/logs/run_1.log"),
      leaf("tables/results.csv", "artifacts/tables/results.csv"),
    ],
  },
  {
    name: "reviews",
    path: "reviews",
    children: [
      leaf("reviewer_round_1.md", "reviews/reviewer_round_1.md"),
      leaf("action_plan_1.json", "reviews/action_plan_1.json"),
    ],
  },
  leaf("research_report.md", "research_report.md"),
  leaf("conclusion.md", "conclusion.md"),
  leaf("timeline.jsonl", "timeline.jsonl"),
];

export const DEFAULT_FILE = "research_report.md";

export function findNode(path: string): WorkspaceNode | undefined {
  const stack = [...WORKSPACE_TREE];
  while (stack.length) {
    const node = stack.shift()!;
    if (node.path === path) {
      return node;
    }
    if (node.children) {
      stack.push(...node.children);
    }
  }
  return undefined;
}
