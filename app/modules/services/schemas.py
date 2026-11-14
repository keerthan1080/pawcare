from pydantic import BaseModel
from app.common.enums import PriceUnit, ServiceType


class ServiceCatalogResponse(BaseModel):
    code: ServiceType
    name: str
    description: str
    default_price_unit: PriceUnit
    is_active: bool
