"""Smoke tests proving CI uses real packages, not global stubs."""


def test_real_optional_packages_are_not_shadowed():
    import PIL
    import pymupdf
    import fitz
    import nltk
    import aioboto3

    from PIL import Image, ImageDraw, ImageFont
    from docx import Document
    from qdrant_client.models import PointStruct, Distance, VectorParams
    from langgraph.graph import StateGraph
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from rank_bm25 import BM25Okapi

    assert getattr(PIL, "__file__", None), "PIL is shadowed by a fake module"
    assert getattr(pymupdf, "__file__", None), "pymupdf is shadowed by a fake module"
    assert getattr(fitz, "__file__", None), "fitz is shadowed by a fake module"
    assert getattr(nltk, "__file__", None), "nltk is shadowed by a fake module"

    assert Image is not None
    assert ImageDraw is not None
    assert ImageFont is not None
    assert Document is not None
    assert PointStruct is not None
    assert Distance is not None
    assert VectorParams is not None
    assert StateGraph is not None
    assert RecursiveCharacterTextSplitter is not None
    assert BM25Okapi is not None
    assert aioboto3 is not None


def test_observability_middleware_importable():
    from src.observability import observability_middleware
    assert observability_middleware is not None
