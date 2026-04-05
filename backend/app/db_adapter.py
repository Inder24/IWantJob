"""
Database adapter that provides MongoDB-like interface for SQLite
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


def _normalize_key(key: str) -> str:
    """Map Mongo-style keys to actual SQLite columns."""
    return "id" if key == "_id" else key


class Collection:
    """MongoDB-like collection interface for SQLite"""
    def __init__(self, conn, table_name):
        self.conn = conn
        self.table_name = table_name
        
    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find one document matching query"""
        cursor = self.conn.cursor()
        
        # Build WHERE clause
        where_parts = []
        values = []
        for key, value in query.items():
            where_parts.append(f"{_normalize_key(key)} = ?")
            values.append(value)
            
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        
        cursor.execute(f"SELECT * FROM {self.table_name} WHERE {where_clause}", values)
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            # Parse JSON fields
            if 'parsed_data' in result and isinstance(result['parsed_data'], str):
                result['parsed_data'] = json.loads(result['parsed_data'])
            if 'search_terms' in result and isinstance(result['search_terms'], str):
                result['search_terms'] = json.loads(result['search_terms'])
            # Add MongoDB-style _id
            result['_id'] = result.get('id', str(uuid.uuid4()))
            return result
        return None

    async def find(
        self,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> list[Dict[str, Any]]:
        """Find multiple documents matching query."""
        cursor = self.conn.cursor()
        query = query or {}

        where_parts = []
        values = []
        for key, value in query.items():
            where_parts.append(f"{_normalize_key(key)} = ?")
            values.append(value)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        order_clause = ""
        if order_by:
            direction = "DESC" if desc else "ASC"
            order_clause = f" ORDER BY {_normalize_key(order_by)} {direction}"
        if limit < 1:
            limit = 1

        cursor.execute(
            f"SELECT * FROM {self.table_name} WHERE {where_clause}{order_clause} LIMIT ?",
            values + [limit],
        )
        rows = cursor.fetchall()

        results = []
        for row in rows:
            item = dict(row)
            if 'parsed_data' in item and isinstance(item['parsed_data'], str):
                item['parsed_data'] = json.loads(item['parsed_data'])
            if 'search_terms' in item and isinstance(item['search_terms'], str):
                item['search_terms'] = json.loads(item['search_terms'])
            item['_id'] = item.get('id', str(uuid.uuid4()))
            results.append(item)
        return results
        
    async def insert_one(self, document: Dict[str, Any]) -> Any:
        """Insert one document"""
        cursor = self.conn.cursor()
        
        # Generate ID if not present
        if '_id' not in document:
            document['_id'] = str(uuid.uuid4())
        document['id'] = document['_id']
            
        # Prepare data
        doc = document.copy()
        if 'parsed_data' in doc and isinstance(doc['parsed_data'], dict):
            doc['parsed_data'] = json.dumps(doc['parsed_data'])
        if 'search_terms' in doc and isinstance(doc['search_terms'], list):
            doc['search_terms'] = json.dumps(doc['search_terms'])
            
        # Build INSERT query
        columns = list(doc.keys())
        placeholders = ','.join(['?' for _ in columns])
        
        query = f"INSERT INTO {self.table_name} ({','.join(columns)}) VALUES ({placeholders})"
        
        try:
            cursor.execute(query, [doc[col] for col in columns])
            self.conn.commit()
            
            class InsertResult:
                def __init__(self, inserted_id):
                    self.inserted_id = inserted_id
                    
            return InsertResult(document['_id'])
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed' in str(e):
                raise Exception("Duplicate key error")
            raise
            
    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        """Update one document"""
        cursor = self.conn.cursor()
        
        # Handle $set operator
        if '$set' in update:
            update_data = update['$set']
        else:
            update_data = update
            
        # Prepare update data
        update_copy = update_data.copy()
        if 'parsed_data' in update_copy and isinstance(update_copy['parsed_data'], dict):
            update_copy['parsed_data'] = json.dumps(update_copy['parsed_data'])
        if 'search_terms' in update_copy and isinstance(update_copy['search_terms'], list):
            update_copy['search_terms'] = json.dumps(update_copy['search_terms'])
            
        # Build UPDATE query
        set_parts = [f"{_normalize_key(key)} = ?" for key in update_copy.keys()]
        where_parts = [f"{_normalize_key(key)} = ?" for key in query.keys()]
        
        query_str = f"UPDATE {self.table_name} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
        values = list(update_copy.values()) + list(query.values())
        
        cursor.execute(query_str, values)
        self.conn.commit()
        
        class UpdateResult:
            def __init__(self, modified_count):
                self.modified_count = modified_count
                
        return UpdateResult(cursor.rowcount)
        
    async def delete_one(self, query: Dict[str, Any]) -> Any:
        """Delete one document"""
        cursor = self.conn.cursor()
        
        where_parts = [f"{_normalize_key(key)} = ?" for key in query.keys()]
        query_str = f"DELETE FROM {self.table_name} WHERE {' AND '.join(where_parts)}"
        
        cursor.execute(query_str, list(query.values()))
        self.conn.commit()
        
        class DeleteResult:
            def __init__(self, deleted_count):
                self.deleted_count = deleted_count
                
        return DeleteResult(cursor.rowcount)

class Database:
    """MongoDB-like database interface for SQLite"""
    def __init__(self, conn):
        self.conn = conn
        self.users = Collection(conn, 'users')
        self.resumes = Collection(conn, 'resumes')
        self.jobs = Collection(conn, 'jobs')
        self.applications = Collection(conn, 'applications')
        
class GridFS:
    """GridFS-like interface for SQLite BLOB storage"""
    def __init__(self, conn):
        self.conn = conn
        
    async def put(self, file_data: bytes, filename: str) -> str:
        """Store file and return ID"""
        file_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO gridfs (id, filename, data, upload_date)
            VALUES (?, ?, ?, ?)
        ''', (file_id, filename, file_data, datetime.utcnow().isoformat()))
        self.conn.commit()
        return file_id
        
    async def get(self, file_id: str):
        """Get file by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT data, filename FROM gridfs WHERE id = ?', (file_id,))
        row = cursor.fetchone()
        if row:
            class GridOut:
                def __init__(self, data, filename):
                    self._data = data
                    self.filename = filename
                    
                async def read(self):
                    return self._data
                    
            return GridOut(row['data'], row['filename'])
        return None
        
    async def delete(self, file_id: str):
        """Delete file by ID"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM gridfs WHERE id = ?', (file_id,))
        self.conn.commit()
