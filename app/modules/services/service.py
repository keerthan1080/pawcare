from typing import List
from app.common.enums import PriceUnit, ServiceType
from app.database.connection import DatabaseManager
from app.modules.services.repository import ServiceCatalogRepository
from app.modules.services.schemas import ServiceCatalogResponse


class ServiceCatalogService:
    def __init__(self, db: DatabaseManager) -> None:
        self._repo = ServiceCatalogRepository(db)

    def list_services(self) -> List[ServiceCatalogResponse]:
        records = self._repo.list_active_services()
        return [
            ServiceCatalogResponse(
                code=ServiceType(r.code),
                name=r.name,
                description=r.description,
                default_price_unit=PriceUnit(r.default_price_unit),
                is_active=r.is_active,
            )
            for r in records
        ]
