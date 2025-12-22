# db/users.py
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime


class UserDatabase:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=2,
                max_size=10,
                command_timeout=60
            )

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def create_user(
        self,
        username: str,
        email: str,
        password_hash: str,
        role: str = "user"
    ) -> int:
        query = """
            INSERT INTO users (username, email, password_hash, role)
            VALUES ($1, $2, $3, $4)
            RETURNING id;
        """
        async with self.pool.acquire() as conn:
            user_id = await conn.fetchval(query, username, email, password_hash, role)
            return user_id

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM users WHERE id = $1 AND is_active = TRUE;"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            return dict(row) if row else None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM users WHERE email = $1 AND is_active = TRUE;"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, email)
            return dict(row) if row else None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM users WHERE username = $1 AND is_active = TRUE;"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, username)
            return dict(row) if row else None

    async def update_user(self, user_id: int, **updates) -> bool:
        if not updates:
            return False

        updates["updated_at"] = datetime.utcnow()

        set_clause = ", ".join(f"{key} = ${i+2}" for i, key in enumerate(updates))
        values = [user_id] + list(updates.values())

        query = f"UPDATE users SET {set_clause} WHERE id = $1 RETURNING id;"
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, *values)
            return result is not None

    async def deactivate_user(self, user_id: int) -> bool:
        query = "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = $1;"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, user_id)
            return "UPDATE 1" in result

    async def user_exists(self, email: str = None, username: str = None) -> bool:
        if email:
            query = "SELECT 1 FROM users WHERE email = $1 AND is_active = TRUE;"
            async with self.pool.acquire() as conn:
                return await conn.fetchval(query, email) is not None
        if username:
            query = "SELECT 1 FROM users WHERE username = $1 AND is_active = TRUE;"
            async with self.pool.acquire() as conn:
                return await conn.fetchval(query, username) is not None
        return False