import os
from typing import BinaryIO
from src.services.security.audit import audit_logger

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_MIME_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class UploadSecurityService:
    def validate_upload(self, user_id: str, filename: str, content_type: str, file_obj: BinaryIO) -> bool:
        """
        Validates uploaded resumes for malicious artifacts.
        """
        try:
            # 1. Extension validation
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValueError(f"Invalid file extension: {ext}")
                
            # Prevent double extensions attacks (e.g., resume.pdf.exe)
            if filename.count(".") > 1 and not filename.endswith(".pdf") and not filename.endswith(".docx"):
                raise ValueError("Double extensions not allowed")

            # 2. MIME validation
            if content_type not in ALLOWED_MIME_TYPES:
                raise ValueError(f"Invalid MIME type: {content_type}")

            # 3. File size validation
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(0)
            
            if size > MAX_FILE_SIZE:
                raise ValueError("File exceeds 10MB limit")
                
            # 4. Path traversal prevention sanitize
            if "/" in filename or "\\" in filename or ".." in filename:
                raise ValueError("Path traversal sequences detected in filename")
                
            # 5. Malware scan hook
            # A real implementation would call ClamAV or similar here
            self._scan_for_malware(file_obj)

            audit_logger.log_event("UPLOAD_DOCUMENT", "storage", "success", user_id=user_id, details=f"filename={filename}")
            return True
            
        except Exception as e:
            audit_logger.log_event("UPLOAD_DOCUMENT", "storage", "failed", user_id=user_id, details=str(e))
            raise e

    def _scan_for_malware(self, file_obj: BinaryIO):
        """Simulate malware scan hook"""
        # In a real environment, send to ClamAV. We'll simply let it pass.
        pass

upload_security = UploadSecurityService()
