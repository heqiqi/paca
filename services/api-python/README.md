# Paca API (Python/FastAPI)

Python/FastAPI rewrite of the Go API service.

## Architecture

```
app/
├── api/              # FastAPI route handlers
│   ├── deps.py       # Auth dependencies (get_current_user, etc.)
│   └── routes/       # Route modules (auth, users, admin, projects, tasks, etc.)
├── core/             # Platform/infrastructure
│   ├── config.py     # Pydantic Settings configuration
│   ├── database.py   # SQLAlchemy async engine + session factory
│   ├── events.py     # Redis pub/sub event publishing
│   ├── permissions.py # RBAC permission definitions
│   ├── redis.py      # Redis/Valkey client
│   ├── security.py   # JWT, password hashing, API key utilities
│   └── storage.py    # S3/MinIO presigned URL operations
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic request/response schemas
├── services/         # Business logic layer
├── repositories/     # Data access layer
├── middleware/       # Custom middleware
├── workers/          # Background workers (activity consumer, etc.)
└── main.py           # FastAPI app instance + lifespan
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Docker

```bash
docker build -t paca-api .
docker run -p 8080:8080 --env-file .env paca-api
```

## API Endpoints

All endpoints are under `/api/v1/`:

| Category | Endpoints |
|----------|-----------|
| Health | `GET /api/healthz` |
| Auth | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` |
| Users | `GET /users/me`, `PATCH /users/me`, `PATCH /users/me/password` |
| Admin | `GET/POST /admin/users`, `PATCH/DELETE /admin/users/:id`, global roles |
| Projects | CRUD `/projects`, members, roles |
| Tasks | CRUD `/projects/:id/tasks`, types, statuses, links, activities, comments |
| Sprints | CRUD `/projects/:id/sprints`, complete |
| Views | CRUD `/projects/:id/views`, task positions |
| Docs | CRUD `/projects/:id/docs`, folders, snapshots |
| Attachments | Presigned upload/download, delete |
| Notifications | List, mark read |

## Tech Stack

- **Framework**: FastAPI with async/await
- **ORM**: SQLAlchemy 2.0 async
- **Database**: PostgreSQL (via asyncpg)
- **Cache**: Redis/Valkey
- **Object Storage**: S3/MinIO (via aioboto3)
- **Auth**: JWT (python-jose) + HttpOnly cookies + API keys
- **Migrations**: Alembic
- **Validation**: Pydantic v2
