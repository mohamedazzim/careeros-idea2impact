"""Package version history models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PackageVersion(Base):
    __tablename__ = "package_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generated_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(256), nullable=False, default="regenerated")
    resume_content: Mapped[Optional[str]] = mapped_column(Text)
    cover_letter_content: Mapped[Optional[str]] = mapped_column(Text)
    outreach_content: Mapped[Optional[str]] = mapped_column(Text)
    interview_guide_content: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_package_versions_package", "package_id", "version_num"),
    )
