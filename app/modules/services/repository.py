from dataclasses import dataclass
from typing import List
from app.database.connection import DatabaseManager


@dataclass
class ServiceCatalogRecord:
    code: str
    name: str
    description: str
    default_price_unit: str
    is_active: bool


class ServiceCatalogRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def list_active_services(self) -> List[ServiceCatalogRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM services WHERE is_active = 1 ORDER BY code ASC"
            )
            return [
                ServiceCatalogRecord(
                    code=r["code"],
                    name=r["name"],
                    description=r["description"],
                    default_price_unit=r["default_price_unit"],
                    is_active=bool(r["is_active"]),
                )
                for r in cur.fetchall()
            ]
