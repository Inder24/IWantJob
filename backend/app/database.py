"""
Database configuration - SQLite with MongoDB-compatible interface
"""
import sqlite3
import os
from dotenv import load_dotenv
from app.db_adapter import Database, GridFS

load_dotenv()

# Database settings
DATABASE_FILE = "job_search.db"

# Global database instance
database = None
fs = None
conn = None


def get_database():
    """Get the database instance"""
    return database


def get_gridfs():
    """Get GridFS instance"""
    return fs


async def connect_to_mongo():
    """Initialize SQLite database with MongoDB-compatible interface"""
    global database, fs, conn
    try:
        # Create connection
        conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # Create tables
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                _id TEXT,
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
                _id TEXT,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_hash TEXT,
                file_id TEXT,
                parsed_data TEXT,
                search_terms TEXT,
                parsing_status TEXT NOT NULL,
                parsing_error TEXT,
                upload_date TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        # Backfill for existing DBs that predate parsing_error
        try:
            cursor.execute("ALTER TABLE resumes ADD COLUMN parsing_error TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE resumes ADD COLUMN content_hash TEXT")
        except sqlite3.OperationalError:
            pass
        
        # GridFS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gridfs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                data BLOB NOT NULL,
                upload_date TEXT NOT NULL
            )
        ''')
        
        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                _id TEXT,
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
                _id TEXT,
                user_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL,
                applied_date TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Track seen jobs per user/day to enforce top freshness
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_job_views (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_key TEXT NOT NULL,
                viewed_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_job_views_unique
            ON user_job_views(user_id, job_key, viewed_date)
        ''')
        
        conn.commit()
        
        # Create MongoDB-compatible interface
        database = Database(conn)
        fs = GridFS(conn)
        
        print(f"✓ SQLite database initialized: {DATABASE_FILE}")
        print("✓ MongoDB-compatible interface ready")
        
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        raise


async def close_mongo_connection():
    """Close database connection"""
    global conn
    if conn:
        conn.close()
        print("✓ Database connection closed")
