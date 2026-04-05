"""
Pydantic models for data validation and serialization
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime


# User Models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: Optional[str] = Field(alias="_id")
    username: str
    email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# Resume Models
class Contact(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None


class Experience(BaseModel):
    title: str
    company: str
    duration: str
    description: str


class Education(BaseModel):
    degree: str
    institution: str
    year: str


class ParsedData(BaseModel):
    raw_text: str
    skills: List[str] = []
    experience: List[Experience] = []
    education: List[Education] = []
    contact: Optional[Contact] = None
    role_terms: List[str] = []
    resume_score: Optional[int] = None
    improvement_suggestions: List[str] = []
    last_ats_checked_at: Optional[str] = None


class Resume(BaseModel):
    id: Optional[str] = Field(alias="_id")
    user_id: str
    filename: str
    upload_date: datetime
    parsed_data: ParsedData
    search_terms: List[str] = []
    updated_at: datetime

    class Config:
        populate_by_name = True


# Job Models
class Job(BaseModel):
    id: Optional[str] = Field(alias="_id")
    platform: str  # 'linkedin', 'indeed', 'glassdoor'
    job_id: str
    title: str
    company: str
    location: str
    description: str
    requirements: List[str] = []
    posted_date: Optional[datetime] = None
    url: str
    salary_range: Optional[str] = None
    job_type: Optional[str] = None
    keywords: List[str] = []
    scraped_at: datetime
    last_checked: datetime

    class Config:
        populate_by_name = True


# Application Models
class Contact(BaseModel):
    name: str
    email: Optional[str] = None
    role: Optional[str] = None


class Reminder(BaseModel):
    reminder_date: datetime
    message: str
    completed: bool = False


class TimelineEvent(BaseModel):
    date: datetime
    event: str
    notes: Optional[str] = None


class Application(BaseModel):
    id: Optional[str] = Field(alias="_id")
    user_id: str
    job_id: str
    status: str  # 'applied', 'interviewing', 'rejected', 'offer', 'accepted'
    applied_date: datetime
    notes: Optional[str] = None
    contacts: List[Contact] = []
    reminders: List[Reminder] = []
    timeline: List[TimelineEvent] = []
    match_score: Optional[float] = None
    last_updated: datetime

    class Config:
        populate_by_name = True


# Search Strategy Models
class SearchFilters(BaseModel):
    job_type: List[str] = []
    experience_level: Optional[str] = None
    location: List[str] = []
    remote: bool = False
    salary_min: Optional[int] = None


class SearchStrategy(BaseModel):
    id: Optional[str] = Field(alias="_id")
    user_id: str
    name: str
    platforms: List[str]  # ['linkedin', 'indeed', 'glassdoor']
    keywords: List[str]
    filters: SearchFilters
    active: bool = True
    created_at: datetime

    class Config:
        populate_by_name = True
