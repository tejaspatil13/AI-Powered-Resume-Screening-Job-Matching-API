from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime

from app.core.database import Base


class Screening(Base):
    __tablename__ = "screenings"

    id = Column(Integer, primary_key=True, index=True)

    resume_id = Column(
        Integer,
        ForeignKey("resumes.id"),
        nullable=False
    )

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=False
    )

    overall_score = Column(Integer, nullable=False)

    recommendation = Column(String, nullable=False)

    result_json = Column(Text, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )