"""
Resume router for handling resume upload and management
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_database, get_gridfs
from app.routers.auth import get_current_user
from app.models.schemas import Resume
from app.services.pdf_parser import pdf_parser
from app.services.skill_extractor import skill_extractor
from datetime import datetime
import uuid
import io

router = APIRouter()
security = HTTPBearer()


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
        pdf_result = pdf_parser.parse_pdf(pdf_bytes)
        
        if not pdf_result["success"]:
            await db.resumes.update_one(
                {"_id": resume_id},
                {"$set": {"parsing_status": "failed", "parsing_error": pdf_result["error"]}}
            )
            return
        
        raw_text = pdf_result["raw_text"]
        
        # Extract contact information
        contact_info = pdf_parser.extract_contact_info(raw_text)
        
        # Extract skills
        skills_result = skill_extractor.extract_skills(raw_text)
        all_skills = skills_result["tech_skills"] + skills_result["soft_skills"]
        
        # Extract job titles
        job_titles = skill_extractor.extract_job_titles(raw_text)
        
        # Extract companies
        companies = skill_extractor.extract_companies(raw_text)
        
        # Extract education degrees
        degrees = skill_extractor.extract_education_degrees(raw_text)
        
        # Generate search terms from extracted data
        search_terms = []
        
        # Add job titles as search terms
        search_terms.extend(job_titles[:5])  # Top 5 job titles
        
        # Add skill-based searches
        top_skills = skills_result["tech_skills"][:5]
        for skill in top_skills:
            search_terms.append(f"{skill} developer")
            search_terms.append(f"{skill} engineer")
        
        # Add location-based searches if available
        if contact_info["location"]:
            if job_titles:
                search_terms.append(f"{job_titles[0]} {contact_info['location']}")
        
        # Remove duplicates
        search_terms = list(set(search_terms))
        
        # Update resume with parsed data
        parsed_data = {
            "raw_text": raw_text[:5000],  # Store first 5000 chars
            "skills": all_skills,
            "experience": [{"company": comp, "title": "", "duration": "", "description": ""} 
                          for comp in companies[:5]],  # Placeholder
            "education": [{"degree": deg, "institution": "", "year": ""} 
                         for deg in degrees],
            "contact": contact_info
        }
        
        await db.resumes.update_one(
            {"_id": resume_id},
            {
                "$set": {
                    "parsed_data": parsed_data,
                    "search_terms": search_terms,
                    "parsing_status": "completed",
                    "last_updated": datetime.utcnow()
                }
            }
        )
        
    except Exception as e:
        # Update status to failed
        await db.resumes.update_one(
            {"_id": resume_id},
            {"$set": {"parsing_status": "failed", "parsing_error": str(e)}}
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a PDF resume"""
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )
    
    db = get_database()
    
    # Check if user already has a resume
    existing_resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    
    # Store file in GridFS
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    fs = AsyncIOMotorGridFSBucket(db)
    
    # Delete old resume file if exists
    if existing_resume and "file_id" in existing_resume:
        try:
            await fs.delete(existing_resume["file_id"])
        except:
            pass  # File might not exist
    
    # Upload new file
    file_id = await fs.put(contents, filename=file.filename)
    
    # Create or update resume record (without parsed data yet)
    resume_id = str(uuid.uuid4())
    resume_data = {
        "_id": resume_id,
        "user_id": current_user["_id"],
        "filename": file.filename,
        "file_id": file_id,
        "upload_date": datetime.utcnow().isoformat(),
        "parsed_data": {
            "raw_text": "",
            "skills": [],
            "experience": [],
            "education": [],
            "contact": None
        },
        "search_terms": [],
        "updated_at": datetime.utcnow().isoformat(),
        "parsing_status": "pending"  # pending, processing, completed, failed
    }
    
    if existing_resume:
        # Update existing resume
        await db.resumes.update_one(
            {"_id": existing_resume["_id"]},
            {"$set": resume_data}
        )
        resume_id = existing_resume["_id"]
    else:
        # Create new resume
        result = await db.resumes.insert_one(resume_data)
        resume_id = result.inserted_id
    
    # Trigger background parsing
    background_tasks.add_task(parse_resume_background, str(resume_id), contents)
    
    return {
        "message": "Resume uploaded successfully. Parsing in progress...",
        "resume_id": str(resume_id),
        "filename": file.filename,
        "size_bytes": len(contents),
        "status": "parsing_started"
    }


@router.get("/me")
async def get_my_resume(current_user: dict = Depends(get_current_user)):
    """Get current user's resume"""
    db = get_database()
    
    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found for this user"
        )
    
    # Convert ObjectId to string for JSON serialization
    resume["_id"] = str(resume["_id"])
    resume["user_id"] = str(resume["user_id"])
    if "file_id" in resume:
        resume["file_id"] = str(resume["file_id"])
    
    return resume


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_resume(current_user: dict = Depends(get_current_user)):
    """Delete current user's resume"""
    db = get_database()
    
    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found for this user"
        )
    
    # Delete file from GridFS
    if "file_id" in resume:
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        fs = AsyncIOMotorGridFSBucket(db)
        try:
            await fs.delete(resume["file_id"])
        except:
            pass
    
    # Delete resume record
    await db.resumes.delete_one({"_id": resume["_id"]})
    
    return None


@router.get("/download")
async def download_resume(current_user: dict = Depends(get_current_user)):
    """Download current user's resume PDF"""
    from fastapi.responses import StreamingResponse
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    
    db = get_database()
    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    
    if not resume or "file_id" not in resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume file found"
        )
    
    fs = AsyncIOMotorGridFSBucket(db)
    
    try:
        # Get file from GridFS
        grid_out = await fs.open_download_stream(resume["file_id"])
        
        # Read file contents
        contents = await grid_out.read()
        
        return StreamingResponse(
            io.BytesIO(contents),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={resume['filename']}"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume file not found in storage"
        )
