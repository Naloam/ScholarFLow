"""autoresearch package — slimmed (Session 15 orchestrator retirement).

The old thinking chain (~60 modules incl. project_paper_orchestrator.py) was
physically retired; the brain now lives in services/research_harness/. Only
literature_connectors.py is retained here (reused by research_harness). This
__init__ intentionally exports nothing so importing literature_connectors no
longer pulls in deleted modules.
"""
