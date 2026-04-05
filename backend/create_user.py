"""
Script to create static user: Inder / Simran24
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.utils.security import get_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "job_search_db")

async def create_static_user():
    """Create static user Inder / Simran24"""
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    
    # Check if user already exists
    existing_user = await db.users.find_one({"username": "Inder"})
    
    if existing_user:
        print("✓ User 'Inder' already exists")
        print(f"  Email: {existing_user.get('email', 'N/A')}")
        print(f"  Created: {existing_user.get('created_at', 'N/A')}")
    else:
        # Create new user
        hashed_password = get_password_hash("Simran24")
        
        user_dict = {
            "username": "Inder",
            "email": "inder@jobsearch.com",
            "password_hash": hashed_password,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.users.insert_one(user_dict)
        print("✅ Static user created successfully!")
        print(f"  Username: Inder")
        print(f"  Password: Simran24")
        print(f"  Email: inder@jobsearch.com")
        print(f"  User ID: {result.inserted_id}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_static_user())
