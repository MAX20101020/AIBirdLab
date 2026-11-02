from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    bird_name: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_details: Mapped[str | None] = mapped_column(Text, nullable=True)
