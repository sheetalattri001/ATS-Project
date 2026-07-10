from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader
import io
from sqlalchemy import create_engine, text
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "postgresql://postgres:postgress1@localhost:5432/ats_db"
engine = create_engine(DATABASE_URL)

def init_db():
    with engine.connect() as conn:
        # Table create karna
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS resumes (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                score FLOAT,
                status TEXT DEFAULT 'Applied',
                interview_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

init_db()

def calculate_match(resume_text, job_description):
    resume_words = set(resume_text.lower().split())
    jd_words = set(job_description.lower().split())
    if not jd_words: return 0.0
    match_count = len(resume_words.intersection(jd_words))
    return round((match_count / len(jd_words)) * 100, 2)

@app.post("/match-resume")
async def match_resume(job_description: str = Form(...), file: UploadFile = File(...)):
    try:
        pdf_content = await file.read()
        reader = PdfReader(io.BytesIO(pdf_content))
        resume_text = "".join([page.extract_text() for page in reader.pages])
        
        score = calculate_match(resume_text, job_description)

        with engine.connect() as conn:
            query = text("INSERT INTO resumes (filename, score, status) VALUES (:filename, :score, :status)")
            conn.execute(query, {"filename": file.filename, "score": score, "status": "Applied"})
            conn.commit() # Commit zaroori hai
        
        return {"filename": file.filename, "match_score": f"{score}%"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/get-candidates")
async def get_candidates():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, filename, score, status FROM resumes ORDER BY score DESC"))
        # Row mapping (professional way)
        candidates = [{"id": r[0], "name": r[1], "score": r[2], "status": r[3]} for r in result]
    return {"candidates": candidates}

class InterviewSchema(BaseModel):
    candidate_id: int
    interview_date: str

@app.post("/schedule-interview")
async def schedule_interview(data: InterviewSchema):
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE resumes SET status = 'Interview Scheduled', interview_date = :date WHERE id = :id"),
                {"date": data.interview_date, "id": data.candidate_id}
            )
            conn.commit()
        return {"message": "Interview Scheduled Successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))