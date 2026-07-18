import logging
import io
import pytesseract
from PIL import Image
from langsmith import traceable
import fitz

logger = logging.getLogger(__name__)

class OCRService:
    @traceable(name="extract_text_from_image")
    def extract_text_from_image(self, file_bytes: bytes) -> str:
        try:
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            logger.error(f"OCR failed for image: {e}")
            return ""

    @traceable(name="extract_text_from_scanned_pdf")
    def extract_text_from_scanned_pdf(self, file_bytes: bytes) -> str:
        try:
            text_parts = []
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                page_text = self.extract_text_from_image(img_bytes)
                text_parts.append(page_text)
            doc.close()
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"OCR failed for scanned PDF: {e}")
            return ""

ocr_service = OCRService()
