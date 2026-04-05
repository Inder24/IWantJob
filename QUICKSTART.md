# Job Search Tool - Quick Start Guide

## 🎯 What's Been Built

A **working backend application** with:
- ✅ User authentication (JWT-based)
- ✅ Resume upload & intelligent parsing
- ✅ Skill extraction using NLP
- ✅ Auto-generated job search terms
- ✅ MongoDB Atlas integration
- ✅ Full API documentation

## 🚀 Quick Start

### Start the Server

```bash
cd backend
./start.sh
```

Or manually:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server starts at: **http://localhost:8000**  
API Docs: **http://localhost:8000/docs**

## 📖 Usage Examples

### 1. Create Account
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "yourname",
    "email": "your@email.com",
    "password": "yourpassword"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "yourname",
    "password": "yourpassword"
  }'
```

Copy the `access_token` from response.

### 3. Upload Your Resume
```bash
curl -X POST http://localhost:8000/api/resume/upload \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/your/resume.pdf"
```

### 4. View Parsed Resume (with extracted skills)
```bash
curl -X GET http://localhost:8000/api/resume/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🎨 Try It in Browser

1. Open http://localhost:8000/docs
2. Click "Authorize" button (top right)
3. Login and get your token
4. Paste token in authorization dialog
5. Try uploading your resume!

## ✨ What It Extracts

From your resume PDF, the system automatically identifies:
- **Technical Skills**: Python, Java, Docker, AWS, React, etc.
- **Soft Skills**: Leadership, communication, teamwork, etc.
- **Job Titles**: Software Engineer, Data Scientist, etc.
- **Companies**: Previous employers
- **Education**: Degrees and institutions
- **Contact Info**: Email, phone, location
- **Search Terms**: Auto-generated job search queries

## 📊 Example Results

**Sample resume tested**: Resume - Simran Arora.pdf

**Extracted:**
- 40+ skills (Java, Spring Boot, Docker, Kubernetes, Python, Kafka, AWS, etc.)
- 3 job titles (Software Engineer, Senior Java Developer, etc.)
- 5 companies (ASTAR, OCBC, Oracle, etc.)
- 12 auto-generated search terms
- Email: simran.arora@u.nus.edu
- Parsing time: ~3 seconds

## 🔧 Configuration

Create `backend/.env` from `backend/.env.example`.

Minimum required:
- `JWT_SECRET`

Only for AI ATS scoring button:
- `ENABLE_AGENT_EXTRACTION=true`
- `GEMINI_API_KEY=...`

Everything else is optional (defaults exist in code).

## 📈 What's Next?

The foundation is ready for:
- Job scraping from LinkedIn, Indeed, Glassdoor
- Job matching and scoring
- Application tracking
- React frontend (requires Node.js installation)

## 🐛 Troubleshooting

**Server won't start?**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

**Can't upload resume?**
- Check file is PDF format
- File must be < 10MB
- Make sure you're authenticated (have valid token)

## 📚 More Information

- Full README: `/Users/inder/Documents/JobSearch/README.md`
- Implementation Plan: See plan.md in session folder
- Progress Report: See PROGRESS.md in session folder

---

**Status**: ✅ Backend Fully Functional  
**Tested**: ✅ With real resume (Simran Arora)  
**Ready**: ✅ For job scraping implementation
