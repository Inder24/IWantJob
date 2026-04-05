"""
Resume router - simplified for SQLite
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, BackgroundTasks
from app.database import get_database, get_gridfs
from app.routers.auth import get_current_user
from app.models.schemas import Resume
from app.services.pdf_parser import pdf_parser
from app.services.skill_extractor import skill_extractor
from app.services.agent_extractor import agent_extractor
from datetime import datetime
import uuid
import hashlib

router = APIRouter()


async def parse_resume_background(resume_id: str, pdf_bytes: bytes):
    """Background task to parse resume"""
    db = get_database()
    
    try:
        # Update status to processing
        await db.resumes.update_one(
            {"_id": resume_id},
            {"$set": {"parsing_status": "processing"}}
        )
        
        # Parse PDF
        parsed_pdf = pdf_parser.parse_pdf(pdf_bytes)
        if not parsed_pdf.get("success"):
            raise ValueError(parsed_pdf.get("error") or "Failed to parse PDF")
        raw_text = parsed_pdf.get("raw_text", "")
        contact_info = pdf_parser.extract_contact_info(raw_text)
        
        # Extract skills
        skills_result = skill_extractor.extract_skills(raw_text)
        all_skills = skills_result["tech_skills"] + skills_result["soft_skills"]
        
        # Extract job titles and companies (spaCy/rules)
        job_titles = skill_extractor.extract_job_titles(raw_text)
        companies = skill_extractor.extract_companies(raw_text)
        degrees = skill_extractor.extract_education_degrees(raw_text)

        # Optional agent pass for higher precision and scoring
        agent_data = {
            "companies": [],
            "location": None,
            "skills": [],
            "resume_score": None,
            "improvement_suggestions": [],
        }
        try:
            agent_data = await agent_extractor.extract_resume_intelligence(raw_text)
        except Exception:
            agent_data = {
                "companies": [],
                "location": None,
                "skills": [],
                "resume_score": None,
                "improvement_suggestions": [],
            }

        if agent_data.get("companies"):
            merged = []
            seen = set()
            for c in agent_data["companies"] + companies:
                key = c.lower().strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(c.strip())
            companies = merged[:8]
        if agent_data.get("location"):
            contact_info["location"] = agent_data["location"]
        if agent_data.get("skills"):
            merged_skills = []
            seen_skills = set()
            for s in all_skills + agent_data["skills"]:
                key = s.lower().strip()
                if not key or key in seen_skills:
                    continue
                seen_skills.add(key)
                merged_skills.append(s.strip())
            all_skills = merged_skills[:80]
        
        # Generate search terms
        search_terms = []
        search_terms.extend(job_titles[:5])
        top_skills = skills_result["tech_skills"][:5]
        for skill in top_skills:
            search_terms.append(f"{skill} developer")
            search_terms.append(f"{skill} engineer")
        
        search_terms = list(set(search_terms))[:12]
        
        # Prepare parsed data
        parsed_data = {
            "raw_text": raw_text[:5000],
            "skills": all_skills,
            "experience": [{"company": comp, "title": "", "duration": "", "description": ""} 
                          for comp in companies[:5]],
            "education": [{"degree": deg, "institution": "", "year": ""} 
                         for deg in degrees],
            "contact": contact_info,
            "resume_score": agent_data.get("resume_score"),
            "improvement_suggestions": agent_data.get("improvement_suggestions", []),
        }
        
        # Update resume
        await db.resumes.update_one(
            {"_id": resume_id},
            {"$set": {
                "parsed_data": parsed_data,
                "search_terms": search_terms,
                "parsing_status": "completed",
                "updated_at": datetime.utcnow().isoformat()
            }}
        )
        
    except Exception as e:
        await db.resumes.update_one(
            {"_id": resume_id},
            {"$set": {
                "parsing_status": "failed",
                "parsing_error": str(e),
                "updated_at": datetime.utcnow().isoformat()
            }}
        )


@router.post("/me/ats-score")
async def check_my_ats_score(current_user: dict = Depends(get_current_user)):
    """Re-run AI ATS scoring for the current user's uploaded resume."""
    db = get_database()
    fs = get_gridfs()

    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found")
    if "file_id" not in resume or not resume["file_id"]:
        raise HTTPException(status_code=400, detail="Resume file is missing")

    grid_out = await fs.get(resume["file_id"])
    if not grid_out:
        raise HTTPException(status_code=404, detail="Resume file not found")

    pdf_bytes = await grid_out.read()
    parsed_pdf = pdf_parser.parse_pdf(pdf_bytes)
    if not parsed_pdf.get("success"):
        raise HTTPException(status_code=400, detail=parsed_pdf.get("error") or "Failed to parse resume PDF")
    raw_text = parsed_pdf.get("raw_text", "")
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Resume text is empty after parsing")

    agent_data = await agent_extractor.extract_resume_intelligence(raw_text)
    score = agent_data.get("resume_score")
    suggestions = agent_data.get("improvement_suggestions", [])
    ats_checked_at = datetime.utcnow().isoformat()

    parsed_data = resume.get("parsed_data") or {}
    parsed_data["resume_score"] = score
    parsed_data["improvement_suggestions"] = suggestions
    parsed_data["last_ats_checked_at"] = ats_checked_at

    await db.resumes.update_one(
        {"_id": resume["_id"]},
        {"$set": {
            "parsed_data": parsed_data,
            "updated_at": datetime.utcnow().isoformat()
        }}
    )

    return {
        "message": "ATS score refreshed successfully",
        "resume_id": resume["_id"],
        "resume_score": score,
        "improvement_suggestions": suggestions,
        "last_ats_checked_at": ats_checked_at
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a PDF resume"""
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    db = get_database()
    fs = get_gridfs()
    
    # Check existing
    existing_resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    content_hash = hashlib.sha256(contents).hexdigest()
    existing_same_hash = await db.resumes.find_one(
        {"user_id": current_user["_id"], "content_hash": content_hash}
    )

    if existing_same_hash:
        return {
            "message": "This exact resume is already uploaded. Reusing existing parsed record.",
            "resume_id": existing_same_hash["_id"],
            "filename": existing_same_hash["filename"],
            "status": existing_same_hash["parsing_status"],
        }
    
    # Delete old file if exists
    if existing_resume and "file_id" in existing_resume:
        try:
            await fs.delete(existing_resume["file_id"])
        except:
            pass
    
    # Store new file
    file_id = await fs.put(contents, filename=file.filename)
    
    # Create resume record
    resume_id = str(uuid.uuid4())
    resume_data = {
        "_id": resume_id,
        "user_id": current_user["_id"],
        "filename": file.filename,
        "content_hash": content_hash,
        "file_id": file_id,
        "upload_date": datetime.utcnow().isoformat(),
        "parsed_data": {"raw_text": "", "skills": [], "experience": [], "education": [], "contact": None},
        "search_terms": [],
        "updated_at": datetime.utcnow().isoformat(),
        "parsing_status": "pending"
    }
    
    if existing_resume:
        resume_id = existing_resume["_id"]
        resume_data["_id"] = resume_id
        await db.resumes.update_one({"_id": resume_id}, {"$set": resume_data})
    else:
        await db.resumes.insert_one(resume_data)
    
    # Start parsing
    background_tasks.add_task(parse_resume_background, resume_id, contents)
    
    return {
        "message": "Resume uploaded successfully. Parsing in progress...",
        "resume_id": resume_id,
        "filename": file.filename,
        "status": "parsing_started"
    }


@router.get("/me")
async def get_my_resume(current_user: dict = Depends(get_current_user)):
    """Get current user's resume"""
    db = get_database()
    
    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found")
    
    return resume


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_resume(current_user: dict = Depends(get_current_user)):
    """Delete current user's resume"""
    db = get_database()
    fs = get_gridfs()
    
    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found")
    
    # Delete file
    if "file_id" in resume:
        try:
            await fs.delete(resume["file_id"])
        except:
            pass
    
    # Delete resume record
    await db.resumes.delete_one({"_id": resume["_id"]})
    
    return None
