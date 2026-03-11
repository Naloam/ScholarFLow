from typing import List

from schemas.papers import PaperMeta


class ArxivClient:
    def search(self, query: str, limit: int = 10) -> List[PaperMeta]:
        """Placeholder for arXiv search."""
        raise NotImplementedError
