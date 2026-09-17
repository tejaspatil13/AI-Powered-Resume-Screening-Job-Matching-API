from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
import json
from app.core.logger import logger
from app.core.database import Base, engine, get_db


from app.models.resume import Resume
from app.models.job import Job
from app.models.screening import Screening

from app.schemas.screening import ScreeningRequest
from app.graph.screening_graph import screening_graph

from app.services.pdf_service import extract_text_from_pdf
from fastapi.middleware.cors import CORSMiddleware


Base.metadata.create_all(bind=engine)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5555",
        "http://localhost:5555",
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

    return {
        "jobs": [
            {
                "job_id": job.id,
                "title": job.title
            }
            for job in jobs
        ]
    }



@app.post("/user/resume/upload")
async def upload_resume(
    candidate_name: str = Form(...),
    job_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    logger.info(
        f"Resume upload requested: "
        f"candidate={candidate_name}, "
        f"job_id={job_id}, "
        f"file={file.filename}"
    )

    if file.content_type != "application/pdf":
        logger.warning(f"Invalid file type: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    content = await file.read()

    resume_text = extract_text_from_pdf(content)

    if not resume_text:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from resume"
        )

    resume = Resume(
        candidate_name=candidate_name,
        job_id=job_id,
        filename=file.filename,
        resume_text=resume_text
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
        "filename": file.filename
    }


@app.post("/user/screen-resume")
async def screen_resume(
    request: ScreeningRequest,
    db: Session = Depends(get_db)
):

    logger.info(
        f"Screening requested: "
        f"resume_id={request.resume_id}, "
        f"job_id={request.job_id}"
    )

    # --------------------------------
    # 1. Get resume
    # --------------------------------

    resume = (
        db.query(Resume)
        .filter(Resume.id == request.resume_id)
        .first()
    )

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )

    # --------------------------------
    # 2. Get job
    # --------------------------------

    job = (
        db.query(Job)
        .filter(Job.id == request.job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # --------------------------------
    # 3. Validate relationship
    # --------------------------------

    if resume.job_id != job.id:
        raise HTTPException(
            status_code=400,
            detail="Resume does not belong to this job"
        )

    # --------------------------------
    # 4. Invoke LangGraph
    # --------------------------------

    try:

        graph_result = await screening_graph.ainvoke({
            "resume_text": resume.resume_text,
            "jd_text": job.jd_text,
            "result": None
        })

    except Exception as e:

        logger.exception(
            f"Screening failed: "
            f"resume_id={request.resume_id}, "
            f"job_id={request.job_id}"
        )

        raise HTTPException(
            status_code=500,
            detail="AI screening failed"
        )

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
        result_json=json.dumps(result_dict)
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

        "result": result_dict
    }


# recuirter will add job 
@app.post("/recruiter/job-description/upload")
async def upload_job_description(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    logger.info(
        f"Job description upload requested: "
        f"title={title}, "
        f"file={file.filename}"
    )

    if file.content_type != "application/pdf":
        logger.warning(f"Invalid file type: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    content = await file.read()

    job_description_text = extract_text_from_pdf(content)

    if not job_description_text:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from job description"
        )

    job = Job(
        title=title,
        jd_text=job_description_text
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(f"Job created successfully: {job.id}")

    return {
        "message": "Job description uploaded successfully",
        "job_id": job.id,
        "title": title,
        "filename": file.filename
    }
@app.get("/recruiter/jobs/resumes")
def get_recruiter_resumes(
    db: Session = Depends(get_db)
):
    logger.info(
        "Recruiter requested all resumes with screening results"
    )

    # --------------------------------------------------
    # 1. Get all jobs
    # --------------------------------------------------

    jobs = (
        db.query(Job)
        .order_by(Job.created_at.desc())
        .all()
    )

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
                .filter(
                    Screening.resume_id == resume.id,
                    Screening.job_id == job.id
                )
                .order_by(Screening.id.desc())
                .first()
            )

            screening_data = None

            # --------------------------------------------------
            # 4. If screening exists, get its result
            # --------------------------------------------------

            if screening:

                try:
                    result = json.loads(
                        screening.result_json
                    )

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

                    "result": result
                }

            # --------------------------------------------------
            # 5. Add resume + screening information
            # --------------------------------------------------

            resume_data.append({

                "resume_id": resume.id,

                "candidate_name": resume.candidate_name,

                "filename": resume.filename,

                "created_at": resume.created_at,

                "screening": screening_data
            })

        # --------------------------------------------------
        # 6. Add job information
        # --------------------------------------------------

        response.append({

            "job_id": job.id,

            "job_title": job.title,

            "resume_count": len(resumes),

            "resumes": resume_data
        })

    # --------------------------------------------------
    # 7. Return response
    # --------------------------------------------------

    return {
        "jobs": response
    }

@app.get("/recruiter/jobs/{job_id}/screenings")
def get_job_screenings(
    job_id: int,
    db: Session = Depends(get_db)
):
    logger.info(
        f"Recruiter requested screening results for job_id={job_id}"
    )

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

    screenings = (
        db.query(Screening)
        .filter(Screening.job_id == job_id)
        .order_by(Screening.overall_score.desc())
        .all()
    )

    results = []

    for screening in screenings:

        resume = (
            db.query(Resume)
            .filter(Resume.id == screening.resume_id)
            .first()
        )

        if not resume:
            continue

        results.append({
            "screening_id": screening.id,
            "resume_id": resume.id,
            "candidate_name": resume.candidate_name,
            "filename": resume.filename,
            "overall_score": screening.overall_score,
            "recommendation": screening.recommendation,
            "result": json.loads(screening.result_json),
            "created_at": screening.created_at
        })

    return {
        "job_id": job.id,
        "job_title": job.title,
        "candidate_count": len(results),
        "candidates": results
    }


@app.get("/screening/history")
def get_screening_history(
    job_id: int | None = None,
    resume_id: int | None = None,
    db: Session = Depends(get_db)
):
    logger.info(
        f"Screening history requested: "
        f"job_id={job_id}, resume_id={resume_id}"
    )

    query = db.query(Screening)

    if job_id is not None:
        query = query.filter(
            Screening.job_id == job_id
        )

    if resume_id is not None:
        query = query.filter(
            Screening.resume_id == resume_id
        )

    screenings = (
        query
        .order_by(Screening.created_at.desc())
        .all()
    )

    history = []

    for screening in screenings:

        resume = (
            db.query(Resume)
            .filter(Resume.id == screening.resume_id)
            .first()
        )

        job = (
            db.query(Job)
            .filter(Job.id == screening.job_id)
            .first()
        )

        if not resume or not job:
            continue

        try:
            result = json.loads(
                screening.result_json
            )
        except (json.JSONDecodeError, TypeError):
            result = {}

        history.append({
            "screening_id": screening.id,
            "resume_id": resume.id,
            "job_id": job.id,
            "candidate_name": resume.candidate_name,
            "filename": resume.filename,
            "job_title": job.title,
            "overall_score": screening.overall_score,
            "recommendation": screening.recommendation,
            "result": result,
            "created_at": screening.created_at
        })

    return {
        "count": len(history),
        "history": history
    }