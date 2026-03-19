from config.settings import settings
from services.embedding.vector_index import add_vectors, reset_index, search


def test_vector_index_search_works_without_faiss(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    reset_index("demo")
    add_vectors("demo", [[1.0, 0.0], [0.0, 1.0]], ["draft", "review"])

    results = search("demo", [1.0, 0.0], 2)

    assert [chunk_id for chunk_id, _score in results] == ["draft", "review"]


def test_reset_index_clears_search_results(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    add_vectors("demo", [[1.0, 0.0]], ["draft"])
    reset_index("demo")

    assert search("demo", [1.0, 0.0], 1) == []
