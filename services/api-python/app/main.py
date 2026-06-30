"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, attachments, auth, documents, health, notifications, projects, sprints, tasks, users, views
from app.core.config import settings
from app.core.redis import close_redis, init_redis
from app.core.storage import ensure_bucket

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    # Startup
    logger.info("Starting Paca API service...")
    await init_redis()
    await ensure_bucket()
    await _seed_admin()
    logger.info(f"Paca API ready on port {settings.server_port}")
    yield
    # Shutdown
    await close_redis()
    logger.info("Paca API shut down.")


app = FastAPI(
    title="Paca API",
    description="AI-native project management platform API",
    version="0.4.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(sprints.router, prefix="/api/v1")
app.include_router(views.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(attachments.router, prefix="/api/v1")


async def _seed_admin():
    """Seed the default admin user and global roles on startup."""
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.security import hash_password
    from app.models.global_role import GlobalRole
    from app.models.user import User

    async with async_session_factory() as session:
        # Seed default global roles
        for role_def in [
            ("SUPER_ADMIN", {"*": True}),
            ("ADMIN", {"users.*": True, "global_roles.*": True, "projects.*": True}),
            ("USER", {"users.read": True}),
        ]:
            result = await session.execute(select(GlobalRole).where(GlobalRole.name == role_def[0]))
            role = result.scalar_one_or_none()
            if role is None:
                role = GlobalRole(name=role_def[0], permissions=role_def[1])
                session.add(role)
        await session.flush()

        # Seed admin user
        result = await session.execute(select(User).where(User.username == settings.admin_username))
        admin = result.scalar_one_or_none()
        if admin is None:
            # Get SUPER_ADMIN role
            result = await session.execute(select(GlobalRole).where(GlobalRole.name == "SUPER_ADMIN"))
            super_admin_role = result.scalar_one()

            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                full_name="Admin",
                role_id=super_admin_role.id,
            )
            session.add(admin)
            logger.info(f"Admin user '{settings.admin_username}' seeded.")

        await session.commit()
