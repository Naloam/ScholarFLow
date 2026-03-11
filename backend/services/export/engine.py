from __future__ import annotations

from pathlib import Path

try:
    from docx import Document  # type: ignore
except Exception:  # pragma: no cover
    Document = None

from services.workspace import project_root


def _export_dir(project_id: str) -> Path:
    path = project_root(project_id) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_markdown(project_id: str, content: str, export_id: str) -> str:
    path = _export_dir(project_id) / f"{export_id}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


def export_latex(project_id: str, content: str, export_id: str) -> str:
    path = _export_dir(project_id) / f"{export_id}.tex"
    lines: list[str] = []
    for line in content.splitlines():
        if line.startswith("# "):
            lines.append(f"\\section{{{line[2:].strip()}}}")
        elif line.startswith("## "):
            lines.append(f"\\subsection{{{line[3:].strip()}}}")
        else:
            lines.append(line)
    latex = (
        "\\documentclass{article}\n\\begin{document}\n"
        + "\n".join(lines)
        + "\n\\end{document}\n"
    )
    path.write_text(latex, encoding="utf-8")
    return str(path)


def export_word(project_id: str, content: str, export_id: str) -> str:
    if Document is None:
        raise RuntimeError("python-docx not available")
    path = _export_dir(project_id) / f"{export_id}.docx"
    doc = Document()
    for line in content.splitlines():
        if line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        else:
            doc.add_paragraph(line)
    doc.save(str(path))
    return str(path)
