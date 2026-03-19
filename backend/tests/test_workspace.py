from config.settings import settings
from services.workspace import papers_dir, parsed_dir, project_root


def test_workspace_uses_configured_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    root = project_root("project-123")
    papers = papers_dir("project-123")
    parsed = parsed_dir("project-123")

    assert root == tmp_path / "projects" / "project-123"
    assert papers == root / "papers"
    assert parsed == root / "parsed"
    assert papers.exists()
    assert parsed.exists()
