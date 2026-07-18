import pytest
from src.services.processing.parser import document_parser

def test_parse_text_file():
    text_content = b"This is a test resume."
    result = document_parser.parse_document(text_content, "resume.txt")
    
    assert result["document_type"] == "txt"
    assert result["text"] == "This is a test resume."
    assert result["page_count"] == 1

def test_parse_pdf_file_mocked(mocker):
    # We mock PyMuPDF to avoid needing actual PDF bytes in text
    mock_pdf = mocker.MagicMock()
    mock_page = mocker.MagicMock()
    mock_page.get_text.return_value = "Mocked PDF text"
    # Setting len(doc) via __len__ on the mock or simply mocking the iterator
    mock_pdf.__iter__.return_value = [mock_page]
    mock_pdf.__len__.return_value = 1
    
    mocker.patch('fitz.open', return_value=mock_pdf)
    
    result = document_parser.parse_document(b"fake_pdf_bytes", "resume.pdf")
    assert result["document_type"] == "pdf"
    assert "Mocked PDF text" in result["text"]
    assert result["page_count"] == 1

def test_parse_docx_file_mocked(mocker):
    mock_doc = mocker.MagicMock()
    mock_para = mocker.MagicMock()
    mock_para.text = "Mocked DOCX text"
    mock_doc.paragraphs = [mock_para]
    
    mocker.patch('src.services.processing.parser.DocxDocument', return_value=mock_doc)
    
    result = document_parser.parse_document(b"fake_docx_bytes", "resume.docx")
    assert result["document_type"] == "docx"
    assert "Mocked DOCX text" in result["text"]
    assert result["page_count"] == 1
