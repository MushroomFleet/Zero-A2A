"""
Database and caching infrastructure for Zero-A2A
"""

import aiosqlite
import redis.asyncio as redis
import structlog
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict
import json
from datetime import datetime
import os

from src.core.config import settings

logger = structlog.get_logger()


class DatabaseManager:
    """Async database manager with SQLite support for development"""
    
    def __init__(self):
        self.database_url = settings.database_url
        self.redis_url = settings.redis_url
        self.db_path = self._extract_db_path()
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.logger = logger.bind(component="database_manager")
    
    def _extract_db_path(self) -> str:
        """Extract database path from SQLite URL"""
        if self.database_url.startswith('sqlite:///'):
            return self.database_url[10:]  # Remove 'sqlite:///'
        elif self.database_url.startswith('sqlite://'):
            return self.database_url[9:]   # Remove 'sqlite://'
        else:
            # Fallback for PostgreSQL URLs - will cause graceful failure
            return "zero_a2a.db"
    
    async def initialize(self):
        """Initialize database connections"""
        try:
            # Test SQLite connection
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
                await db.commit()
            
            # Try to initialize Redis (optional for development)
            try:
                self.redis_pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    max_connections=settings.redis_pool_max_size,
                    retry_on_timeout=True
                )
                self.redis_client = redis.Redis(connection_pool=self.redis_pool)
                await self.redis_client.ping()
                self.logger.info("Redis connection initialized")
            except Exception as redis_error:
                self.logger.warning("Redis unavailable, continuing without cache", error=str(redis_error))
                self.redis_client = None
            
            self.logger.info(
                "Database connections initialized",
                db_path=self.db_path,
                redis_available=self.redis_client is not None
            )
            
        except Exception as e:
            self.logger.error("Database initialization failed", error=str(e))
            raise
    
    @asynccontextmanager
    async def get_db_connection(self):
        """Get SQLite database connection"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row  # Enable dict-like access
            try:
                yield db
            except Exception as e:
                self.logger.error("Database connection error", error=str(e))
                raise
    
    async def get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client (may be None if Redis unavailable)"""
        return self.redis_client
    
    async def close(self):
        """Close all connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
                self.logger.info("Redis client closed")
                
        except Exception as e:
            self.logger.error("Error closing database connections", error=str(e))


class TaskRepository:
    """Repository for task persistence"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logger.bind(component="task_repository")
    
    async def create_task_table(self):
        """Create task table if it doesn't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            context_id TEXT,
            task_id TEXT,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            result TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_tasks_agent_id ON tasks(agent_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_context_id ON tasks(context_id);
        """
        
        async with self.db_manager.get_db_connection() as db:
            await db.executescript(create_table_sql)
            await db.commit()
        
        self.logger.info("Task table created/verified")
    
    async def save_task(
        self, 
        task_id: str, 
        agent_id: str, 
        message: Dict[str, Any],
        context_id: Optional[str] = None,
        task_ref_id: Optional[str] = None
    ) -> str:
        """Save a new task"""
        insert_sql = """
        INSERT INTO tasks (id, agent_id, context_id, task_id, status, message)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        async with self.db_manager.get_db_connection() as db:
            await db.execute(
                insert_sql,
                (task_id, agent_id, context_id, task_ref_id, "created", json.dumps(message))
            )
            await db.commit()
        
        self.logger.info("Task saved", task_id=task_id, agent_id=agent_id)
        return task_id
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """Update task status and result"""
        update_sql = """
        UPDATE tasks 
        SET status = ?, 
            result = ?, 
            error_message = ?,
            updated_at = datetime('now'),
            completed_at = CASE WHEN ? IN ('completed', 'failed') THEN datetime('now') ELSE completed_at END
        WHERE id = ?
        """
        
        async with self.db_manager.get_db_connection() as db:
            await db.execute(
                update_sql,
                (status, json.dumps(result) if result else None, error_message, status, task_id)
            )
            await db.commit()
        
        self.logger.info("Task status updated", task_id=task_id, status=status)
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        select_sql = """
        SELECT id, agent_id, context_id, task_id, status, message, result, 
               error_message, created_at, updated_at, completed_at
        FROM tasks WHERE id = ?
        """
        
        async with self.db_manager.get_db_connection() as db:
            async with db.execute(select_sql, (task_id,)) as cursor:
                row = await cursor.fetchone()
            
            if row:
                return {
                    "id": row["id"],
                    "agent_id": row["agent_id"],
                    "context_id": row["context_id"],
                    "task_id": row["task_id"],
                    "status": row["status"],
                    "message": json.loads(row["message"]) if row["message"] else None,
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error_message": row["error_message"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "completed_at": row["completed_at"],
                }
        
        return None
    
    async def get_tasks_by_agent(
        self, 
        agent_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> list[Dict[str, Any]]:
        """Get tasks by agent ID"""
        select_sql = """
        SELECT id, agent_id, context_id, task_id, status, message, result,
               error_message, created_at, updated_at, completed_at
        FROM tasks 
        WHERE agent_id = ? 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
        """
        
        tasks = []
        async with self.db_manager.get_db_connection() as db:
            async with db.execute(select_sql, (agent_id, limit, offset)) as cursor:
                rows = await cursor.fetchall()
            
            for row in rows:
                tasks.append({
                    "id": row["id"],
                    "agent_id": row["agent_id"],
                    "context_id": row["context_id"],
                    "task_id": row["task_id"],
                    "status": row["status"],
                    "message": json.loads(row["message"]) if row["message"] else None,
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error_message": row["error_message"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "completed_at": row["completed_at"],
                })
        
        return tasks


class CacheManager:
    """Redis-based caching manager"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logger.bind(component="cache_manager")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            redis_client = await self.db_manager.get_redis_client()
            if not redis_client:
                return None  # Redis unavailable
                
            value = await redis_client.get(key)
            
            if value:
                return json.loads(value)
            return None
            
        except Exception as e:
            self.logger.debug("Cache get error", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        try:
            redis_client = await self.db_manager.get_redis_client()
            if not redis_client:
                return False  # Redis unavailable
                
            serialized_value = json.dumps(value, default=str)
            await redis_client.setex(key, ttl, serialized_value)
            return True
            
        except Exception as e:
            self.logger.debug("Cache set error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            redis_client = await self.db_manager.get_redis_client()
            if not redis_client:
                return False  # Redis unavailable
                
            result = await redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            self.logger.debug("Cache delete error", key=key, error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment a counter in cache"""
        try:
            redis_client = await self.db_manager.get_redis_client()
            if not redis_client:
                return 0  # Redis unavailable
                
            value = await redis_client.incr(key, amount)
            
            if ttl and value == amount:  # First time setting
                await redis_client.expire(key, ttl)
            
            return value
            
        except Exception as e:
            self.logger.debug("Cache increment error", key=key, error=str(e))
            return 0
    
    async def get_keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern"""
        try:
            redis_client = await self.db_manager.get_redis_client()
            if not redis_client:
                return []  # Redis unavailable
                
            keys = await redis_client.keys(pattern)
            return [key.decode() if isinstance(key, bytes) else key for key in keys]
            
        except Exception as e:
            self.logger.debug("Cache get_keys error", pattern=pattern, error=str(e))
            return []


# Global instances
db_manager = DatabaseManager()
cache_manager = CacheManager(db_manager)
task_repository = TaskRepository(db_manager)


async def initialize_database():
    """Initialize database connections and tables"""
    await db_manager.initialize()
    await task_repository.create_task_table()


async def close_database():
    """Close database connections"""
    await db_manager.close()
