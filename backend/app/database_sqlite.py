"""
SQLite database configuration as fallback when MongoDB Atlas is unavailable
"""
import sqlite3
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import os

DATABASE_FILE = "job_search.db"

class AsyncSQLiteDB:
    def __init__(self, db_path: str = DATABASE_FILE):
        self.db_path = db_path
        self.conn = None
        
    async def connect(self):
        """Initialize SQLite database and create tables"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Create tables
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Resumes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_data BLOB NOT NULL,
                parsed_data TEXT,
                search_terms TEXT,
                parsing_status TEXT NOT NULL,
                upload_date TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                job_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                description TEXT,
                url TEXT,
                posted_date TEXT,
                scraped_at TEXT NOT NULL,
                UNIQUE(platform, job_id)
            )
        ''')
        
        # Applications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL,
                applied_date TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        ''')
        
        self.conn.commit()
        print(f"✓ SQLite database initialized: {self.db_path}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            
    # User operations
    async def insert_user(self, user_data: Dict[str, Any]) -> str:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO users (id, username, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_data['_id'],
            user_data['username'],
            user_data['email'],
            user_data['password_hash'],
            user_data['created_at'],
            user_data['updated_at']
        ))
        self.conn.commit()
        return user_data['_id']
        
    async def find_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
        
    async def find_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    # Resume operations
    async def insert_resume(self, resume_data: Dict[str, Any]) -> str:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO resumes (id, user_id, filename, file_data, parsed_data, search_terms, parsing_status, upload_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            resume_data['_id'],
            resume_data['user_id'],
            resume_data['filename'],
            resume_data['file_data'],
            json.dumps(resume_data.get('parsed_data', {})),
            json.dumps(resume_data.get('search_terms', [])),
            resume_data['parsing_status'],
            resume_data['upload_date'],
            resume_data['updated_at']
        ))
        self.conn.commit()
        return resume_data['_id']
        
    async def find_resume_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM resumes WHERE user_id = ? ORDER BY upload_date DESC LIMIT 1', (user_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data['parsed_data'] = json.loads(data.get('parsed_data', '{}'))
            data['search_terms'] = json.loads(data.get('search_terms', '[]'))
            return data
        return None
        
    async def update_resume(self, resume_id: str, update_data: Dict[str, Any]):
        cursor = self.conn.cursor()
        fields = []
        values = []
        
        for key, value in update_data.items():
            if key in ['parsed_data', 'search_terms']:
                value = json.dumps(value)
            fields.append(f"{key} = ?")
            values.append(value)
            
        fields.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(resume_id)
        
        query = f"UPDATE resumes SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        self.conn.commit()
        
    async def get_resume_file(self, resume_id: str) -> Optional[bytes]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT file_data, filename FROM resumes WHERE id = ?', (resume_id,))
        row = cursor.fetchone()
        if row:
            return row['file_data'], row['filename']
        return None, None

# Global database instance
database = None

async def connect_to_db():
    """Connect to SQLite database"""
    global database
    try:
        database = AsyncSQLiteDB()
        await database.connect()
        print("✓ Database ready for use")
    except Exception as e:
        print(f"✗ Database error: {e}")
        raise

def get_database():
    """Get the database instance"""
    return database

async def close_db_connection():
    """Close database connection"""
    global database
    if database:
        database.close()
        print("✓ Database connection closed")
