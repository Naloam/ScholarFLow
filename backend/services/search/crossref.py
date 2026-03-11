from typing import List

from schemas.papers import PaperMeta


class CrossrefClient:
    def search(self, query: str, limit: int = 10) -> List[PaperMeta]:
        """Placeholder for CrossRef search."""
        raise NotImplementedError
