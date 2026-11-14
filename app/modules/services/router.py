from typing import List
from fastapi import APIRouter, Depends

from app.database.connection import DatabaseManager, get_db
from app.modules.services.schemas import ServiceCatalogResponse
from app.modules.services.service import ServiceCatalogService

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("", response_model=List[ServiceCatalogResponse])
def get_supported_services(db: DatabaseManager = Depends(get_db)) -> List[ServiceCatalogResponse]:
    service = ServiceCatalogService(db)
    return service.list_services()
