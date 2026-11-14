# PawCare — Book • Care • Stay Connected

Trusted pet-care marketplace and pet-care management platform built as a **Modular Monolith** with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Redis, and React + TypeScript.

## Architecture Overview

```text
app/
├── main.py                  # FastAPI application entrypoint, middleware & routers
├── config/                  # Environment-aware settings (local, dev, qa, prod)
├── core/                    # Standardized errors, logging, correlation ID middleware
├── database/                # SQLAlchemy declarative base, session & repository abstraction
├── security/                # Password hashing, JWT tokens, RBAC dependencies
├── common/                  # Shared enums, pagination, base schemas
├── modules/
│   ├── auth/                # Registration, login, token refresh, audit logging
│   ├── users/               # User profile & admin user management
│   ├── pets/                # Phase 2: Pet profiles & emergency info
│   ├── caregivers/          # Phase 3: Caregiver profiles & verification
│   ├── services/            # Phase 3: Service definitions & pricing
│   ├── availability/        # Phase 3/4: Caregiver availability slots
│   ├── bookings/            # Phase 5: Booking workflow & state machine
│   ├── care_plans/          # Phase 7: Structured Pet Care Plans & tasks
│   ├── care_updates/        # Phase 7: Caregiver photo & status updates
│   ├── payments/            # Phase 6: Payment gateway abstraction & verification
│   ├── notifications/       # Phase 8: Notifications
│   ├── messaging/           # Phase 8: Booking-scoped messaging
│   ├── reviews/             # Phase 9: Verified booking ratings & reviews
│   └── admin/               # Phase 10: Admin dashboard & moderation
└── tests/                   # Unit & integration test suite
```

## Quick Start (Docker Compose)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Start PostgreSQL, Redis, Backend, and Frontend:
   ```bash
   docker compose up --build -d
   ```
3. Run database migrations:
   ```bash
   docker compose exec backend alembic upgrade head
   ```
4. Access the services:
   - **Backend API Docs (Swagger UI)**: `http://localhost:8000/docs`
   - **Health Check**: `http://localhost:8000/api/v1/health`
   - **Frontend Web App**: `http://localhost:5173`

## Running Tests

```bash
# With pytest (in local virtualenv or container)
pytest -v

# Or via standard library unittest runner
python3 -m unittest discover -s app/tests -p "test_*.py" -v
```
