from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime

from app.core.database import Base


# ============================================================
# JOB MODEL
# ============================================================


class Job(Base):

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    jd_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# RESUME MODEL
# ============================================================

class Resume(Base):

    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    filename = Column(String, nullable=False)
    resume_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# SCREENING MODEL
# ============================================================


class Screening(Base):

    __tablename__ = "screenings"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    overall_score = Column(Integer, nullable=False)
    recommendation = Column(String, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GmailConnection(Base):

    __tablename__ = "gmail_connections"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    token_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# RESUMES FETCHED FROM GMAIL
# ============================================================


class GmailResume(Base):

    __tablename__ = "gmail_resumes"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    gmail_message_id = Column(String, nullable=False, index=True)
    gmail_attachment_id = Column(String, nullable=True)
    candidate_name = Column(String, nullable=False)
    email_address = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    resume_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# GMAIL RESUME SCREENING
# ============================================================


class GmailScreening(Base):

    __tablename__ = "gmail_screenings"

    id = Column(Integer, primary_key=True, index=True)
    gmail_resume_id = Column(Integer, ForeignKey("gmail_resumes.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    overall_score = Column(Integer, nullable=False)
    recommendation = Column(String, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
