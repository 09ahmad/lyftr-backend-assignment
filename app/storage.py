"""Database operations for message storage."""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager."""
    
    def __init__(self, db_url: str):
        """Initialize database connection."""
        # Extract path from sqlite:////data/app.db format
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = db_url
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        from_msisdn TEXT NOT NULL,
                        to_msisdn TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        text TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
                conn.commit()
                logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str]
    ) -> Tuple[bool, bool]:
        """
        Insert a message into the database.
        
        Returns:
            (success, is_duplicate) tuple
        """
        created_at = datetime.utcnow().isoformat() + "Z"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (message_id, from_msisdn, to_msisdn, ts, text, created_at))
                    conn.commit()
                    return True, False
                except sqlite3.IntegrityError:
                    # Duplicate message_id
                    conn.rollback()
                    return True, True
        except Exception as e:
            logger.error(f"Failed to insert message: {e}")
            return False, False
    
    def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
        from_msisdn: Optional[str] = None,
        since: Optional[str] = None,
        q: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get messages with pagination and filters.
        
        Returns:
            (messages_list, total_count) tuple
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Build WHERE clause
                conditions = []
                params = []
                
                if from_msisdn:
                    conditions.append("from_msisdn = ?")
                    params.append(from_msisdn)
                
                if since:
                    conditions.append("ts >= ?")
                    params.append(since)
                
                if q:
                    conditions.append("LOWER(text) LIKE ?")
                    params.append(f"%{q.lower()}%")
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                # Get total count
                count_query = f"SELECT COUNT(*) as total FROM messages WHERE {where_clause}"
                cursor.execute(count_query, params)
                total = cursor.fetchone()["total"]
                
                # Get paginated results
                query = f"""
                    SELECT message_id, from_msisdn, to_msisdn, ts, text
                    FROM messages
                    WHERE {where_clause}
                    ORDER BY ts ASC, message_id ASC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                messages = [
                    {
                        "message_id": row["message_id"],
                        "from": row["from_msisdn"],
                        "to": row["to_msisdn"],
                        "ts": row["ts"],
                        "text": row["text"]
                    }
                    for row in rows
                ]
                
                return messages, total
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return [], 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get message statistics."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total messages
                cursor.execute("SELECT COUNT(*) as total FROM messages")
                total_messages = cursor.fetchone()["total"]
                
                # Senders count
                cursor.execute("SELECT COUNT(DISTINCT from_msisdn) as count FROM messages")
                senders_count = cursor.fetchone()["count"]
                
                # Top 10 senders
                cursor.execute("""
                    SELECT from_msisdn, COUNT(*) as count
                    FROM messages
                    GROUP BY from_msisdn
                    ORDER BY count DESC
                    LIMIT 10
                """)
                senders = [
                    {"from": row["from_msisdn"], "count": row["count"]}
                    for row in cursor.fetchall()
                ]
                
                # First and last message timestamps
                cursor.execute("SELECT MIN(ts) as first, MAX(ts) as last FROM messages")
                row = cursor.fetchone()
                first_message_ts = row["first"] if row["first"] else None
                last_message_ts = row["last"] if row["last"] else None
                
                return {
                    "total_messages": total_messages,
                    "senders_count": senders_count,
                    "messages_per_sender": senders,
                    "first_message_ts": first_message_ts,
                    "last_message_ts": last_message_ts
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_messages": 0,
                "senders_count": 0,
                "messages_per_sender": [],
                "first_message_ts": None,
                "last_message_ts": None
            }
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Global database instance
db = Database(settings.DATABASE_URL)

