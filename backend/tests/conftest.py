"""Shared pytest setup for CI import stability."""

import sys

_REAL_PACKAGE_PREFIXES = (
    "PIL",
    "fitz",
    "pymupdf",
    "docx",
    "qdrant_client",
    "langgraph",
    "langchain_text_splitters",
    "aioboto3",
    "nltk",
    "rank_bm25",
)


def _looks_like_test_stub(module) -> bool:
    return (
        module is not None
        and not getattr(module, "__file__", None)
        and not getattr(module, "__path__", None)
    )


for name in list(sys.modules):
    if name in _REAL_PACKAGE_PREFIXES or name.startswith(tuple(p + "." for p in _REAL_PACKAGE_PREFIXES)):
        module = sys.modules.get(name)
        if _looks_like_test_stub(module):
            sys.modules.pop(name, None)
