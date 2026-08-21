from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.core.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String, nullable=False)
    job_id = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    resume_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)