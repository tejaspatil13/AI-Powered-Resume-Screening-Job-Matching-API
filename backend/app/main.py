from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.database import Base, engine, get_db
from app.models.resume import Resume
from app.models.job import Job

from app.services.pdf_service import extract_text_from_pdf


Base.metadata.create_all(bind=engine)


app = FastAPI()



@app.get("/")
def health_check():
    logger.info("Health check requested")
    return {"status": "healthy"}






# user will upload resume
@app.post("/resume/upload")
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




# recuirter will add job 
@app.post("/job-description/upload")
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