import base64
import json
from datetime import date
from typing import List, Optional
from fastapi import status

from app.common.enums import MedicalRecordType, PetGender, PetSpecies, UserRole
from app.common.pagination import PaginatedResponse
from app.common.storage import StorageService
from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager
from app.modules.pets.repository import PetRecord, PetRepository
from app.modules.pets.schemas import (
    EmergencyContactResponse,
    FeedingScheduleItem,
    MedicalRecordCreateRequest,
    MedicalRecordResponse,
    PetCreateRequest,
    PetEmergencyInfoUpdateRequest,
    PetEmergencySummaryResponse,
    PetParentContactSummary,
    PetPhotoUploadRequest,
    PetPhotoUploadResponse,
    PetResponse,
    PetUpdateRequest,
    VeterinarianResponse,
    WalkingScheduleItem,
)
from app.modules.users.repository import UserRecord, UserRepository


class PetService:
    """Business logic for Pet Profiles, Medical Records, Emergency Workflows, and Privacy Authorization."""

    def __init__(self, db: DatabaseManager, storage: Optional[StorageService] = None) -> None:
        self._pet_repo = PetRepository(db)
        self._user_repo = UserRepository(db)
        self._storage = storage

    @staticmethod
    def _calculate_age_years(dob_str: Optional[str], explicit_age: Optional[float]) -> Optional[float]:
        if explicit_age is not None:
            return round(explicit_age, 1)
        if dob_str:
            dob = date.fromisoformat(dob_str)
            days = (date.today() - dob).days
            return round(max(days / 365.25, 0.0), 1)
        return None

    def _ensure_owner_or_admin(self, pet: PetRecord, user: UserRecord) -> None:
        if user.role == UserRole.ADMIN.value:
            return
        if pet.owner_id != user.id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PET_ACCESS_FORBIDDEN",
                message="You are not authorized to modify or access another user's pet profile.",
            )

    def _ensure_can_view_pet(self, pet: PetRecord, user: UserRecord) -> None:
        if user.role == UserRole.ADMIN.value or pet.owner_id == user.id:
            return
        if user.role == UserRole.CAREGIVER.value and self._pet_repo.is_caregiver_authorized_for_pet(
            pet_id=pet.id,
            caregiver_user_id=user.id,
        ):
            return
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PET_ACCESS_FORBIDDEN",
            message="You do not have permission to view this pet's private profile.",
        )

    def _get_active_pet_or_404(self, pet_id: str) -> PetRecord:
        pet = self._pet_repo.get_by_id(pet_id)
        if pet is None or not pet.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PET_NOT_FOUND",
                message="Requested pet profile was not found.",
            )
        return pet

    def _assemble_pet_response(self, pet: PetRecord) -> PetResponse:
        feeding_list = json.loads(pet.feeding_schedule_json) if pet.feeding_schedule_json else []
        walking_list = json.loads(pet.walking_schedule_json) if pet.walking_schedule_json else []
        contacts = self._pet_repo.list_emergency_contacts(pet.id)
        vet = self._pet_repo.get_veterinarian(pet.id)
        med_records = self._pet_repo.list_medical_records(pet.id)

        return PetResponse(
            id=pet.id,
            owner_id=pet.owner_id,
            name=pet.name,
            species=PetSpecies(pet.species),
            breed=pet.breed,
            gender=PetGender(pet.gender),
            date_of_birth=pet.date_of_birth,
            age_years=pet.age_years,
            weight_kg=pet.weight_kg,
            photo_url=pet.photo_url,
            personality=pet.personality,
            feeding_instructions=pet.feeding_instructions,
            feeding_schedule=[FeedingScheduleItem(**item) for item in feeding_list],
            walking_schedule=[WalkingScheduleItem(**item) for item in walking_list],
            medication_instructions=pet.medication_instructions,
            allergies=pet.allergies,
            behaviour_notes=pet.behaviour_notes,
            special_requirements=pet.special_requirements,
            additional_notes=pet.additional_notes,
            is_active=pet.is_active,
            emergency_contacts=[
                EmergencyContactResponse(
                    id=c.id,
                    pet_id=c.pet_id,
                    name=c.name,
                    relationship=c.relationship,
                    phone=c.phone,
                    email=c.email,
                    is_primary=c.is_primary,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in contacts
            ],
            preferred_veterinarian=(
                VeterinarianResponse(
                    id=vet.id,
                    pet_id=vet.pet_id,
                    clinic_name=vet.clinic_name,
                    vet_name=vet.vet_name,
                    phone=vet.phone,
                    address=vet.address,
                    notes=vet.notes,
                    created_at=vet.created_at,
                    updated_at=vet.updated_at,
                )
                if vet
                else None
            ),
            medical_records=[
                MedicalRecordResponse(
                    id=m.id,
                    pet_id=m.pet_id,
                    record_type=MedicalRecordType(m.record_type),
                    title=m.title,
                    administered_date=m.administered_date,
                    expiry_date=m.expiry_date,
                    provider_name=m.provider_name,
                    document_url=m.document_url,
                    notes=m.notes,
                    created_at=m.created_at,
                )
                for m in med_records
            ],
            created_at=pet.created_at,
            updated_at=pet.updated_at,
        )

    def create_pet(self, current_user: UserRecord, payload: PetCreateRequest) -> PetResponse:
        if current_user.role not in (UserRole.PET_PARENT.value, UserRole.ADMIN.value):
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="INSUFFICIENT_PERMISSIONS",
                message="Only Pet Parents can create pet profiles.",
            )

        computed_age = self._calculate_age_years(payload.date_of_birth, payload.age_years)
        pet = self._pet_repo.create_pet(
            owner_id=current_user.id,
            fields={
                "name": payload.name,
                "species": payload.species.value,
                "breed": payload.breed,
                "gender": payload.gender.value,
                "date_of_birth": payload.date_of_birth,
                "age_years": computed_age,
                "weight_kg": payload.weight_kg,
                "personality": payload.personality,
                "feeding_instructions": payload.feeding_instructions,
                "feeding_schedule": [item.dict() for item in payload.feeding_schedule],
                "walking_schedule": [item.dict() for item in payload.walking_schedule],
                "medication_instructions": payload.medication_instructions,
                "allergies": payload.allergies,
                "behaviour_notes": payload.behaviour_notes,
                "special_requirements": payload.special_requirements,
                "additional_notes": payload.additional_notes,
            },
        )

        if payload.emergency_contacts:
            self._pet_repo.replace_emergency_contacts(
                pet_id=pet.id,
                contacts=[c.dict() for c in payload.emergency_contacts],
            )
        if payload.preferred_veterinarian:
            self._pet_repo.upsert_veterinarian(
                pet_id=pet.id,
                vet_data=payload.preferred_veterinarian.dict(),
            )
        for rec in payload.medical_records:
            self._pet_repo.add_medical_record(
                pet_id=pet.id,
                data={
                    **rec.dict(),
                    "record_type": rec.record_type.value,
                },
            )

        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_CREATED",
            entity_type="PET",
            entity_id=pet.id,
            correlation_id=get_correlation_id() or None,
            metadata={"name": pet.name, "species": pet.species},
        )
        return self._assemble_pet_response(pet)

    def list_my_pets(
        self,
        current_user: UserRecord,
        page: int = 1,
        size: int = 20,
        species: Optional[PetSpecies] = None,
    ) -> PaginatedResponse[PetResponse]:
        offset = (page - 1) * size
        owner_filter = None if current_user.role == UserRole.ADMIN.value else current_user.id
        records, total = self._pet_repo.list_pets(
            owner_id=owner_filter,
            species=species.value if species else None,
            offset=offset,
            limit=size,
        )
        return PaginatedResponse[PetResponse](
            items=[self._assemble_pet_response(r) for r in records],
            total=total,
            page=page,
            size=size,
        )

    def get_pet_by_id(self, current_user: UserRecord, pet_id: str) -> PetResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_can_view_pet(pet, current_user)
        return self._assemble_pet_response(pet)

    def update_pet(self, current_user: UserRecord, pet_id: str, payload: PetUpdateRequest) -> PetResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_owner_or_admin(pet, current_user)

        raw = payload.dict(exclude_unset=True)
        db_updates = {}
        for key, value in raw.items():
            if key == "gender" and value is not None:
                db_updates["gender"] = value.value if hasattr(value, "value") else value
            elif key == "feeding_schedule" and value is not None:
                db_updates["feeding_schedule_json"] = json.dumps(value)
            elif key == "walking_schedule" and value is not None:
                db_updates["walking_schedule_json"] = json.dumps(value)
            else:
                db_updates[key] = value

        if "date_of_birth" in db_updates and "age_years" not in db_updates:
            db_updates["age_years"] = self._calculate_age_years(db_updates["date_of_birth"], None)

        updated = self._pet_repo.update_pet(pet_id, db_updates)
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_UPDATED",
            entity_type="PET",
            entity_id=pet_id,
            correlation_id=get_correlation_id() or None,
        )
        return self._assemble_pet_response(updated)  # type: ignore[arg-type]

    def deactivate_pet(self, current_user: UserRecord, pet_id: str) -> PetResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_owner_or_admin(pet, current_user)
        updated = self._pet_repo.update_pet(pet_id, {"is_active": 0})
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_DEACTIVATED",
            entity_type="PET",
            entity_id=pet_id,
            correlation_id=get_correlation_id() or None,
        )
        return self._assemble_pet_response(updated)  # type: ignore[arg-type]

    def upload_pet_photo(
        self,
        current_user: UserRecord,
        pet_id: str,
        payload: PetPhotoUploadRequest,
    ) -> PetPhotoUploadResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_owner_or_admin(pet, current_user)

        if self._storage is None:
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="STORAGE_NOT_CONFIGURED",
                message="Object storage service is not configured.",
            )

        try:
            raw_bytes = base64.b64decode(payload.data_base64, validate=True)
        except Exception:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_BASE64_PAYLOAD",
                message="Image data_base64 is not valid base64.",
            )

        stored = self._storage.upload_image(
            namespace=f"pets/{pet.id}",
            content_type=payload.content_type,
            data=raw_bytes,
        )
        self._pet_repo.update_pet(pet.id, {"photo_url": stored.public_url})
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_PHOTO_UPLOADED",
            entity_type="PET",
            entity_id=pet.id,
            correlation_id=get_correlation_id() or None,
            metadata={"object_key": stored.object_key, "size_bytes": stored.size_bytes},
        )
        return PetPhotoUploadResponse(
            pet_id=pet.id,
            photo_url=stored.public_url,
            object_key=stored.object_key,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
        )

    def add_medical_record(
        self,
        current_user: UserRecord,
        pet_id: str,
        payload: MedicalRecordCreateRequest,
    ) -> MedicalRecordResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_owner_or_admin(pet, current_user)

        rec = self._pet_repo.add_medical_record(
            pet_id=pet.id,
            data={
                **payload.dict(),
                "record_type": payload.record_type.value,
            },
        )
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_MEDICAL_RECORD_ADDED",
            entity_type="PET",
            entity_id=pet.id,
            correlation_id=get_correlation_id() or None,
            metadata={"record_id": rec.id, "record_type": rec.record_type, "title": rec.title},
        )
        return MedicalRecordResponse(
            id=rec.id,
            pet_id=rec.pet_id,
            record_type=MedicalRecordType(rec.record_type),
            title=rec.title,
            administered_date=rec.administered_date,
            expiry_date=rec.expiry_date,
            provider_name=rec.provider_name,
            document_url=rec.document_url,
            notes=rec.notes,
            created_at=rec.created_at,
        )

    def list_medical_records(
        self,
        current_user: UserRecord,
        pet_id: str,
    ) -> List[MedicalRecordResponse]:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_can_view_pet(pet, current_user)
        records = self._pet_repo.list_medical_records(pet.id)
        return [
            MedicalRecordResponse(
                id=m.id,
                pet_id=m.pet_id,
                record_type=MedicalRecordType(m.record_type),
                title=m.title,
                administered_date=m.administered_date,
                expiry_date=m.expiry_date,
                provider_name=m.provider_name,
                document_url=m.document_url,
                notes=m.notes,
                created_at=m.created_at,
            )
            for m in records
        ]

    def update_emergency_info(
        self,
        current_user: UserRecord,
        pet_id: str,
        payload: PetEmergencyInfoUpdateRequest,
    ) -> PetEmergencySummaryResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_owner_or_admin(pet, current_user)

        pet_updates = {}
        if payload.allergies is not None:
            pet_updates["allergies"] = payload.allergies
        if payload.medication_instructions is not None:
            pet_updates["medication_instructions"] = payload.medication_instructions
        if payload.special_requirements is not None:
            pet_updates["special_requirements"] = payload.special_requirements
        if pet_updates:
            self._pet_repo.update_pet(pet.id, pet_updates)

        self._pet_repo.replace_emergency_contacts(
            pet_id=pet.id,
            contacts=[c.dict() for c in payload.emergency_contacts],
        )
        self._pet_repo.upsert_veterinarian(
            pet_id=pet.id,
            vet_data=payload.preferred_veterinarian.dict() if payload.preferred_veterinarian else None,
        )

        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_EMERGENCY_INFO_UPDATED",
            entity_type="PET",
            entity_id=pet.id,
            correlation_id=get_correlation_id() or None,
        )
        return self.get_emergency_info(current_user, pet.id)

    def get_emergency_info(
        self,
        current_user: UserRecord,
        pet_id: str,
    ) -> PetEmergencySummaryResponse:
        pet = self._get_active_pet_or_404(pet_id)
        self._ensure_can_view_pet(pet, current_user)

        owner = self._user_repo.get_by_id(pet.owner_id)
        assembled = self._assemble_pet_response(pet)

        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="PET_EMERGENCY_INFO_ACCESSED",
            entity_type="PET",
            entity_id=pet.id,
            correlation_id=get_correlation_id() or None,
            metadata={"viewer_role": current_user.role},
        )
        return PetEmergencySummaryResponse(
            pet_id=pet.id,
            pet_name=pet.name,
            species=assembled.species,
            breed=pet.breed,
            weight_kg=pet.weight_kg,
            allergies=pet.allergies,
            medication_instructions=pet.medication_instructions,
            special_requirements=pet.special_requirements,
            pet_parent=PetParentContactSummary(
                user_id=owner.id if owner else pet.owner_id,
                full_name=owner.full_name if owner else "Unknown",
                email=owner.email if owner else "",
                phone=owner.phone if owner else None,
            ),
            emergency_contacts=assembled.emergency_contacts,
            preferred_veterinarian=assembled.preferred_veterinarian,
            medical_records=assembled.medical_records,
        )
