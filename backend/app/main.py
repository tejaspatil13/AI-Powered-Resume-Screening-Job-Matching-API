from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
import json
from app.core.logger import logger
from app.core.database import Base, engine, get_db
from app.services.gmail_service import GmailResumeService


from app.models.models import (
    Job,
    Resume,
    Screening,
    GmailConnection,
    GmailResume,
    GmailScreening,
)

from app.schemas.screening import ScreeningRequest
from app.graph.screening_graph import screening_graph

from app.services.pdf_service import extract_text_from_pdf
from fastapi.middleware.cors import CORSMiddleware


Base.metadata.create_all(bind=engine)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://localhost:3000",
        "https://ai-powered-resume-screening-job-mat-theta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "healthy"}


# user will get and upload resume
@app.get("/user/jobs")
def get_jobs(db: Session = Depends(get_db)):
    logger.info("Fetching available jobs")

    jobs = db.query(Job).order_by(Job.created_at.desc()).all()

    return {"jobs": [{"job_id": job.id, "title": job.title} for job in jobs]}


@app.post("/user/resume/upload")
async def upload_resume(
    candidate_name: str = Form(...),
    job_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    logger.info(
        f"Resume upload requested: "
        f"candidate={candidate_name}, "
        f"job_id={job_id}, "
        f"file={file.filename}"
    )

    if file.content_type != "application/pdf":
        logger.warning(f"Invalid file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await file.read()

    resume_text = extract_text_from_pdf(content)

    if not resume_text:
        raise HTTPException(
            status_code=400, detail="Could not extract text from resume"
        )

    resume = Resume(
        candidate_name=candidate_name,
        job_id=job_id,
        filename=file.filename,
        resume_text=resume_text,
    )

    db.add(resume)
    db.commit()
    db.refresh(resume)

    logger.info(f"Resume stored successfully: {resume.id}")

    return {
        "message": "Resume uploaded successfully",
        "resume_id": resume.id,
        "candidate_name": candidate_name,
        "job_id": job_id,
        "filename": file.filename,
    }


@app.post("/user/screen-resume")
async def screen_resume(request: ScreeningRequest, db: Session = Depends(get_db)):

    logger.info(
        f"Screening requested: "
        f"resume_id={request.resume_id}, "
        f"job_id={request.job_id}"
    )

    # --------------------------------
    # 1. Get resume
    # --------------------------------

    resume = db.query(Resume).filter(Resume.id == request.resume_id).first()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # --------------------------------
    # 2. Get job
    # --------------------------------

    job = db.query(Job).filter(Job.id == request.job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # --------------------------------
    # 3. Validate relationship
    # --------------------------------

    if resume.job_id != job.id:
        raise HTTPException(
            status_code=400, detail="Resume does not belong to this job"
        )

    # --------------------------------
    # 4. Invoke LangGraph
    # --------------------------------

    try:

        graph_result = await screening_graph.ainvoke(
            {"resume_text": resume.resume_text, "jd_text": job.jd_text, "result": None}
        )

    except Exception as e:

        logger.exception(
            f"Screening failed: "
            f"resume_id={request.resume_id}, "
            f"job_id={request.job_id}"
        )

        raise HTTPException(status_code=500, detail="AI screening failed")

    # --------------------------------
    # 5. Get structured result
    # --------------------------------

    result = graph_result["result"]

    # --------------------------------
    # 6. Convert Pydantic → dictionary
    # --------------------------------

    result_dict = result.model_dump()

    # --------------------------------
    # 7. Save screening
    # --------------------------------

    screening = Screening(
        resume_id=resume.id,
        job_id=job.id,
        overall_score=result.overall_score,
        recommendation=result.recommendation,
        result_json=json.dumps(result_dict),
    )

    db.add(screening)
    db.commit()
    db.refresh(screening)

    logger.info(
        f"Screening completed successfully: "
        f"screening_id={screening.id}, "
        f"score={result.overall_score}"
    )

    # --------------------------------
    # 8. Return result
    # --------------------------------

    return {
        "message": "Resume screened successfully",
        "screening_id": screening.id,
        "resume_id": resume.id,
        "job_id": job.id,
        "candidate_name": resume.candidate_name,
        "job_title": job.title,
        "result": result_dict,
    }


# recuirter will add job
@app.post("/recruiter/job-description/upload")
async def upload_job_description(
    title: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
):
    logger.info(
        f"Job description upload requested: " f"title={title}, " f"file={file.filename}"
    )

    if file.content_type != "application/pdf":
        logger.warning(f"Invalid file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await file.read()

    job_description_text = extract_text_from_pdf(content)

    if not job_description_text:
        raise HTTPException(
            status_code=400, detail="Could not extract text from job description"
        )

    job = Job(title=title, jd_text=job_description_text)

    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(f"Job created successfully: {job.id}")

    return {
        "message": "Job description uploaded successfully",
        "job_id": job.id,
        "title": title,
        "filename": file.filename,
    }


@app.get("/recruiter/jobs/resumes")
def get_recruiter_resumes(db: Session = Depends(get_db)):
    logger.info("Recruiter requested all resumes with screening results")

    # --------------------------------------------------
    # 1. Get all jobs
    # --------------------------------------------------

    jobs = db.query(Job).order_by(Job.created_at.desc()).all()

    response = []

    # --------------------------------------------------
    # 2. Process every job
    # --------------------------------------------------

    for job in jobs:

        # Get resumes belonging to this job
        resumes = (
            db.query(Resume)
            .filter(Resume.job_id == job.id)
            .order_by(Resume.created_at.desc())
            .all()
        )

        resume_data = []

        # --------------------------------------------------
        # 3. Process every resume
        # --------------------------------------------------

        for resume in resumes:

            # Find the latest screening for this resume
            screening = (
                db.query(Screening)
                .filter(Screening.resume_id == resume.id, Screening.job_id == job.id)
                .order_by(Screening.id.desc())
                .first()
            )

            screening_data = None

            # --------------------------------------------------
            # 4. If screening exists, get its result
            # --------------------------------------------------

            if screening:

                try:
                    result = json.loads(screening.result_json)

                except (json.JSONDecodeError, TypeError):

                    logger.warning(
                        f"Could not parse screening result "
                        f"for screening_id={screening.id}"
                    )

                    result = {}

                screening_data = {
                    "screening_id": screening.id,
                    "overall_score": screening.overall_score,
                    "recommendation": screening.recommendation,
                    "result": result,
                }

            # --------------------------------------------------
            # 5. Add resume + screening information
            # --------------------------------------------------

            resume_data.append(
                {
                    "resume_id": resume.id,
                    "candidate_name": resume.candidate_name,
                    "filename": resume.filename,
                    "created_at": resume.created_at,
                    "screening": screening_data,
                }
            )

        # --------------------------------------------------
        # 6. Add job information
        # --------------------------------------------------

        response.append(
            {
                "job_id": job.id,
                "job_title": job.title,
                "resume_count": len(resumes),
                "resumes": resume_data,
            }
        )

    # --------------------------------------------------
    # 7. Return response
    # --------------------------------------------------

    return {"jobs": response}


@app.get("/recruiter/jobs/{job_id}/screenings")
def get_job_screenings(job_id: int, db: Session = Depends(get_db)):
    logger.info(f"Recruiter requested screening results for job_id={job_id}")

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    screenings = (
        db.query(Screening)
        .filter(Screening.job_id == job_id)
        .order_by(Screening.overall_score.desc())
        .all()
    )

    results = []

    for screening in screenings:

        resume = db.query(Resume).filter(Resume.id == screening.resume_id).first()

        if not resume:
            continue

        results.append(
            {
                "screening_id": screening.id,
                "resume_id": resume.id,
                "candidate_name": resume.candidate_name,
                "filename": resume.filename,
                "overall_score": screening.overall_score,
                "recommendation": screening.recommendation,
                "result": json.loads(screening.result_json),
                "created_at": screening.created_at,
            }
        )

    return {
        "job_id": job.id,
        "job_title": job.title,
        "candidate_count": len(results),
        "candidates": results,
    }


@app.get("/screening/history")
def get_screening_history(db: Session = Depends(get_db)):
    logger.info("Screening history requested")

    screenings = db.query(Screening).order_by(Screening.created_at.desc()).all()

    history = []

    for screening in screenings:

        # Get resume
        resume = db.query(Resume).filter(Resume.id == screening.resume_id).first()

        if not resume:
            continue

        # Get job
        job = db.query(Job).filter(Job.id == screening.job_id).first()

        if not job:
            continue

        # Parse stored JSON result
        try:
            result = json.loads(screening.result_json)

        except (json.JSONDecodeError, TypeError):
            logger.warning(
                f"Could not parse screening result " f"for screening_id={screening.id}"
            )

            result = {}

        history.append(
            {
                "screening_id": screening.id,
                "resume_id": resume.id,
                "job_id": job.id,
                "candidate_name": resume.candidate_name,
                "filename": resume.filename,
                "job_title": job.title,
                "overall_score": screening.overall_score,
                "recommendation": screening.recommendation,
                "result": result,
                "created_at": screening.created_at,
            }
        )

    return {"count": len(history), "history": history}





# ============================================================
# RECRUITER - FETCH RESUMES FROM GMAIL
# ============================================================

@app.post("/recruiter/jobs/{job_id}/gmail/fetch-resumes")
def fetch_gmail_resumes(
    job_id: int,
    db: Session = Depends(get_db)
):

    logger.info(
        f"Gmail resume fetch requested for job_id={job_id}"
    )

    # --------------------------------------------------------
    # 1. Get job
    # --------------------------------------------------------

    job = (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # --------------------------------------------------------
    # 2. CLEAR PREVIOUS GMAIL DATA
    # --------------------------------------------------------

    old_resumes = (
        db.query(GmailResume)
        .filter(GmailResume.job_id == job_id)
        .all()
    )

    for old_resume in old_resumes:

        db.query(GmailScreening).filter(
            GmailScreening.gmail_resume_id == old_resume.id
        ).delete()

    db.query(GmailResume).filter(
        GmailResume.job_id == job_id
    ).delete()

    db.commit()

    logger.info(
        f"Previous Gmail resumes cleared for job_id={job_id}"
    )

    # --------------------------------------------------------
    # 3. Create Gmail service
    # --------------------------------------------------------

    try:

        gmail_service = GmailResumeService()

    except Exception as e:

        logger.exception(
            "Failed to initialize Gmail service"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to connect to Gmail"
        )

    # --------------------------------------------------------
    # 4. Fetch resumes from Gmail
    # --------------------------------------------------------

    try:

        resumes = gmail_service.fetch_resumes(
            query="has:attachment"
        )

    except Exception as e:

        logger.exception(
            "Failed to fetch Gmail resumes"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch resumes from Gmail"
        )

    # --------------------------------------------------------
    # 5. REMOVE DUPLICATES FROM CURRENT FETCH
    # --------------------------------------------------------

    unique_resumes = []
    seen = set()

    for resume in resumes:

        key = (
            resume["gmail_message_id"],
            resume["filename"].strip().lower()
        )

        if key in seen:
            continue

        seen.add(key)
        unique_resumes.append(resume)

    resumes = unique_resumes

    logger.info(
        f"Unique Gmail resumes found: "
        f"job_id={job_id}, count={len(resumes)}"
    )

    # --------------------------------------------------------
    # 6. Save unique resumes
    # --------------------------------------------------------

    saved_resumes = []

    for resume_data in resumes:

        message_id = resume_data["gmail_message_id"]
        attachment_id = resume_data["gmail_attachment_id"]

        gmail_resume = GmailResume(
            job_id=job_id,
            gmail_message_id=message_id,
            gmail_attachment_id=attachment_id,
            candidate_name=resume_data["candidate_name"],
            email_address=resume_data["email_address"],
            filename=resume_data["filename"],
            resume_text=resume_data["resume_text"],
        )

        db.add(gmail_resume)
        db.flush()

        saved_resumes.append(
            {
                "gmail_resume_id": gmail_resume.id,
                "candidate_name": gmail_resume.candidate_name,
                "email_address": gmail_resume.email_address,
                "filename": gmail_resume.filename,
            }
        )

    # --------------------------------------------------------
    # 7. Commit
    # --------------------------------------------------------

    db.commit()

    logger.info(
        f"Gmail resumes saved: "
        f"job_id={job_id}, "
        f"count={len(saved_resumes)}"
    )

    # --------------------------------------------------------
    # 8. Response
    # --------------------------------------------------------

    return {
        "message": "Gmail resumes fetched successfully",
        "job_id": job_id,
        "job_title": job.title,
        "saved_count": len(saved_resumes),
        "skipped_count": len(resumes) - len(saved_resumes),
        "resumes": saved_resumes,
    }


# ============================================================
# RECRUITER - SCREEN GMAIL RESUMES
# ============================================================

@app.post("/recruiter/jobs/{job_id}/gmail/screen")
async def screen_gmail_resumes(
    job_id: int,
    db: Session = Depends(get_db)
):

    logger.info(
        f"Gmail resume screening requested "
        f"for job_id={job_id}"
    )

    # --------------------------------------------------------
    # 1. Get job
    # --------------------------------------------------------

    job = (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # --------------------------------------------------------
    # 2. Get Gmail resumes
    # --------------------------------------------------------

    gmail_resumes = (
        db.query(GmailResume)
        .filter(GmailResume.job_id == job_id)
        .all()
    )

    if not gmail_resumes:

        raise HTTPException(
            status_code=404,
            detail="No Gmail resumes found for this job"
        )

    results = []

    # --------------------------------------------------------
    # 3. Screen Gmail resumes
    # --------------------------------------------------------

    for resume in gmail_resumes:

        # ----------------------------------------------------
        # Check if already screened
        # ----------------------------------------------------

        existing_screening = (
            db.query(GmailScreening)
            .filter(
                GmailScreening.gmail_resume_id == resume.id,
                GmailScreening.job_id == job_id,
            )
            .order_by(
                GmailScreening.id.desc()
            )
            .first()
        )

        # ----------------------------------------------------
        # Already screened
        # ----------------------------------------------------

        if existing_screening:

            try:

                result = json.loads(
                    existing_screening.result_json
                )

            except (
                json.JSONDecodeError,
                TypeError
            ):

                result = {}

            results.append(
                {
                    "gmail_resume_id": resume.id,
                    "candidate_name": resume.candidate_name,
                    "email_address": resume.email_address,
                    "filename": resume.filename,
                    "overall_score": existing_screening.overall_score,
                    "recommendation": existing_screening.recommendation,
                    "result": result,
                }
            )

            continue

        # ----------------------------------------------------
        # New resume → call LLM
        # ----------------------------------------------------

        try:

            graph_result = await screening_graph.ainvoke(
                {
                    "resume_text": resume.resume_text,
                    "jd_text": job.jd_text,
                    "result": None,
                }
            )

            result = graph_result["result"]

            result_dict = result.model_dump()

            screening = GmailScreening(
                gmail_resume_id=resume.id,
                job_id=job_id,
                overall_score=result.overall_score,
                recommendation=result.recommendation,
                result_json=json.dumps(result_dict),
            )

            db.add(screening)

            results.append(
                {
                    "gmail_resume_id": resume.id,
                    "candidate_name": resume.candidate_name,
                    "email_address": resume.email_address,
                    "filename": resume.filename,
                    "overall_score": result.overall_score,
                    "recommendation": result.recommendation,
                    "result": result_dict,
                }
            )

        except Exception as e:

            logger.exception(
                f"Gmail resume screening failed "
                f"for resume_id={resume.id}"
            )

            continue

    # --------------------------------------------------------
    # 4. Commit screenings
    # --------------------------------------------------------

    db.commit()

    # --------------------------------------------------------
    # 5. Sort highest score first
    # --------------------------------------------------------

    results.sort(
        key=lambda x: x["overall_score"],
        reverse=True
    )

    # --------------------------------------------------------
    # 6. Response
    # --------------------------------------------------------

    return {
        "message": "Gmail resumes screened successfully",
        "job_id": job_id,
        "job_title": job.title,
        "candidate_count": len(results),
        "candidates": results,
    }


# ============================================================
# RECRUITER - TOP GMAIL CANDIDATES
# ============================================================

@app.get("/recruiter/jobs/{job_id}/gmail/top-resumes")
def get_top_gmail_resumes(
    job_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):

    logger.info(
        f"Top Gmail resumes requested "
        f"for job_id={job_id}"
    )

    # --------------------------------------------------------
    # 1. Get job
    # --------------------------------------------------------

    job = (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # --------------------------------------------------------
    # 2. Get top screenings
    # --------------------------------------------------------

    screenings = (
        db.query(GmailScreening)
        .filter(
            GmailScreening.job_id == job_id
        )
        .order_by(
            GmailScreening.overall_score.desc()
        )
        .limit(limit)
        .all()
    )

    candidates = []

    # --------------------------------------------------------
    # 3. Build candidate response
    # --------------------------------------------------------

    for screening in screenings:

        resume = (
            db.query(GmailResume)
            .filter(
                GmailResume.id ==
                screening.gmail_resume_id
            )
            .first()
        )

        if not resume:
            continue

        try:

            result = json.loads(
                screening.result_json
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            result = {}

        candidates.append(
            {
                "gmail_resume_id": resume.id,
                "candidate_name": resume.candidate_name,
                "email_address": resume.email_address,
                "filename": resume.filename,
                "overall_score": screening.overall_score,
                "recommendation": screening.recommendation,
                "result": result,
            }
        )

    # --------------------------------------------------------
    # 4. Response
    # --------------------------------------------------------

    return {
        "job_id": job.id,
        "job_title": job.title,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }