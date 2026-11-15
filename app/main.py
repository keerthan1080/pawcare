from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware
from app.database.connection import get_db_manager
from app.modules.admin.demo_router import router as demo_router, seed_demo_workspace
from app.modules.auth.router import router as auth_router
from app.modules.availability.router import router as availability_router
from app.modules.bookings.router import router as bookings_router
from app.modules.caregivers.router import router as caregivers_router
from app.modules.notifications.router import router as notifications_router
from app.modules.pets.router import router as pets_router
from app.modules.services.router import router as services_router
from app.modules.users.router import router as users_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    application = FastAPI(
        title=settings.app_name,
        description="PawCare — Book • Care • Stay Connected (Modular Monolith API)",
        version=settings.app_version,
    )

    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(users_router, prefix=settings.api_v1_prefix)
    application.include_router(pets_router, prefix=settings.api_v1_prefix)
    application.include_router(services_router, prefix=settings.api_v1_prefix)
    application.include_router(caregivers_router, prefix=settings.api_v1_prefix)
    application.include_router(availability_router, prefix=settings.api_v1_prefix)
    application.include_router(bookings_router, prefix=settings.api_v1_prefix)
    application.include_router(notifications_router, prefix=settings.api_v1_prefix)
    application.include_router(demo_router, prefix=settings.api_v1_prefix)

    # Pre-seed initial accounts on server startup so login works immediately
    try:
        seed_demo_workspace(get_db_manager())
    except Exception:
        pass

    @application.get(f"{settings.api_v1_prefix}/health", tags=["System"])
    def health_check() -> dict:
        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    return application


app = create_app()
