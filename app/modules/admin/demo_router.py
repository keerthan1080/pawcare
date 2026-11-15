"""Demo Seeder & Client Telemetry Log ingestion endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.common.enums import UserRole
from app.core.context import get_correlation_id
from app.core.logging import logger
from app.database.connection import DatabaseManager, get_db
from app.modules.availability.repository import AvailabilityRepository
from app.modules.caregivers.repository import CaregiverRepository
from app.modules.pets.repository import PetRepository
from app.modules.users.repository import UserRepository
from app.security.jwt import create_jwt_token
from app.security.passwords import hash_password

router = APIRouter(prefix="/demo", tags=["System & Telemetry"])


class ClientErrorLogRequest(BaseModel):
    trace_id: str = Field(..., min_length=4, max_length=64)
    component: str = Field(..., min_length=2, max_length=100)
    operation: str = Field(..., min_length=2, max_length=100)
    error_message: str = Field(..., max_length=1000)
    path: Optional[str] = Field(default=None, max_length=255)


@router.post("/client-logs", status_code=status.HTTP_202_ACCEPTED)
def record_client_error_log(
    payload: ClientErrorLogRequest,
    db: DatabaseManager = Depends(get_db),
) -> dict:
    """Ingests hidden frontend runtime/network errors into backend developer logs and audit trail."""
    corr_id = get_correlation_id() or payload.trace_id
    logger.error(
        f"[CLIENT_ERROR_TRACE] trace_id={payload.trace_id} component={payload.component} "
        f"operation={payload.operation} path={payload.path} detail={payload.error_message}"
    )
    user_repo = UserRepository(db)
    user_repo.create_audit_log(
        actor_user_id=None,
        action="CLIENT_ERROR_TRACED",
        entity_type="FRONTEND",
        entity_id=payload.trace_id,
        correlation_id=corr_id,
        metadata=payload.dict(),
    )
    return {"status": "logged", "trace_id": payload.trace_id}


@router.post("/seed")
def seed_demo_workspace(db: DatabaseManager = Depends(get_db)) -> dict:
    user_repo = UserRepository(db)
    pet_repo = PetRepository(db)
    cg_repo = CaregiverRepository(db)
    avail_repo = AvailabilityRepository(db)

    parent = user_repo.get_by_email("keerthan@pawcare.in")
    if parent is None:
        parent = user_repo.create_user(
            email="keerthan@pawcare.in",
            full_name="Keerthan Tenneti",
            phone="+91-8247716995",
            password_hash=hash_password("Password123"),
            role=UserRole.PET_PARENT.value,
        )

    existing_pets, _ = pet_repo.list_pets(owner_id=parent.id)
    if existing_pets:
        bruno = existing_pets[0]
    else:
        bruno = pet_repo.create_pet(
            owner_id=parent.id,
            fields={
                "name": "Bruno",
                "species": "DOG",
                "breed": "Golden Retriever",
                "gender": "MALE",
                "date_of_birth": "2023-05-15",
                "age_years": 3.5,
                "weight_kg": 28.5,
                "personality": "Friendly, energetic, loves evening walks and belly rubs.",
                "feeding_instructions": "1.5 cups Pedigree dry kibble with warm water twice daily.",
                "feeding_schedule": [
                    {"time": "07:30", "meal": "Breakfast", "portion": "1.5 cups", "notes": "Add joint supplement"},
                    {"time": "19:00", "meal": "Dinner", "portion": "1.5 cups", "notes": "Fresh water refill"},
                ],
                "walking_schedule": [
                    {"time": "09:00", "duration_minutes": 30, "notes": "Morning park walk with harness"},
                    {"time": "20:00", "duration_minutes": 30, "notes": "Calm evening walk"},
                ],
                "medication_instructions": "1 chewable multivitamin tablet at 08:00 AM after breakfast.",
                "allergies": "Chicken protein",
                "behaviour_notes": "Gentle with people; sensitive to loud fireworks.",
                "special_requirements": "Keep fresh drinking water available at all times.",
            },
        )
        pet_repo.replace_emergency_contacts(
            pet_id=bruno.id,
            contacts=[
                {
                    "name": "Abhishek Tenneti",
                    "relationship": "Brother",
                    "phone": "+91-9848011223",
                    "email": "abhishek@example.com",
                    "is_primary": True,
                }
            ],
        )
        pet_repo.upsert_veterinarian(
            pet_id=bruno.id,
            vet_data={
                "clinic_name": "Crown Vet Clinic Whitefield",
                "vet_name": "Dr. Ananya Sharma",
                "phone": "+91-8044556677",
                "address": "ITPL Main Road, Whitefield, Bengaluru",
                "notes": "24x7 emergency care unit",
            },
        )
        pet_repo.add_medical_record(
            pet_id=bruno.id,
            data={
                "record_type": "VACCINATION",
                "title": "Anti-Rabies & DHPPi Annual Booster",
                "administered_date": "2026-04-10",
                "expiry_date": "2027-04-10",
                "provider_name": "Crown Vet Clinic Whitefield",
                "notes": "All core vaccinations up to date.",
            },
        )

    if not pet_repo.list_pet_media(bruno.id):
        pet_repo.add_pet_media(
            pet_id=bruno.id,
            data={
                "media_type": "VIDEO",
                "title": "Bruno Morning Walk & Leash Temperament Video",
                "url": "https://cdn.pawcare.local/pawcare-media/pets/bruno/walk-temperament.mp4",
                "duration_seconds": 42,
                "notes": "Shows Bruno walking calmly on chest harness and responding to recall commands.",
            },
        )
        pet_repo.add_pet_media(
            pet_id=bruno.id,
            data={
                "media_type": "VIDEO",
                "title": "Bruno Feeding Routine & Multivitamin Video",
                "url": "https://cdn.pawcare.local/pawcare-media/pets/bruno/feeding-routine.mp4",
                "duration_seconds": 35,
                "notes": "Demonstrates mixing 1.5 cups kibble with warm water and giving the 8:00 AM chewable tablet.",
            },
        )
        pet_repo.add_pet_media(
            pet_id=bruno.id,
            data={
                "media_type": "PHOTO",
                "title": "Bruno Full Body & Coat Health Photo",
                "url": "https://cdn.pawcare.local/pawcare-media/pets/bruno/profile-photo.jpg",
                "duration_seconds": None,
                "notes": "Recent full-body photo taken at home.",
            },
        )
        pet_repo.add_pet_media(
            pet_id=bruno.id,
            data={
                "media_type": "PHOTO",
                "title": "Crown Vet Vaccination Certificate Photo",
                "url": "https://cdn.pawcare.local/pawcare-media/pets/bruno/vaccination-card.jpg",
                "duration_seconds": None,
                "notes": "Signed Anti-Rabies & DHPPi certificate valid through April 2027.",
            },
        )

    admin = user_repo.get_by_email("admin@pawcare.in")
    if admin is None:
        admin = user_repo.create_user(
            email="admin@pawcare.in",
            full_name="PawCare Trust & Safety Admin",
            phone="+91-8247716995",
            password_hash=hash_password("AdminPass123"),
            role=UserRole.ADMIN.value,
        )

    demo_caregivers_spec = [
        {
            "email": "anita.sitter@pawcare.in",
            "full_name": "Anita Rao",
            "phone": "+91-9845011122",
            "bio": "Certified canine care specialist in Whitefield with a shaded, fenced garden. Hosted 90+ happy dogs.",
            "years_of_experience": 6,
            "locality": "Whitefield",
            "latitude": 12.9698,
            "longitude": 77.7500,
            "supported_species": ["DOG", "CAT"],
            "max_pet_weight_kg": 45.0,
            "special_capabilities": ["ORAL_MEDICATION", "SENIOR_PET_CARE", "FIRST_AID_CERTIFIED"],
            "verification_status": "VERIFIED",
            "rating_average": 4.9,
            "review_count": 38,
            "services": [
                {"service_type": "PET_BOARDING", "price_inr": 950.0, "price_unit": "PER_NIGHT", "description": "24/7 home boarding with 2 daily walks & photo updates"},
                {"service_type": "DOG_WALKING", "price_inr": 300.0, "price_unit": "PER_WALK", "duration_minutes": 45, "description": "45-minute harness walk"},
                {"service_type": "DAY_CARE", "price_inr": 650.0, "price_unit": "PER_DAY", "description": "8 AM – 7 PM supervised daytime care"},
            ],
        },
        {
            "email": "vikram.sitter@pawcare.in",
            "full_name": "Vikram Nair",
            "phone": "+91-9845022233",
            "bio": "Full-time remote software consultant & lifelong Golden Retriever lover in Kadugodi. Calm, pet-proofed home.",
            "years_of_experience": 4,
            "locality": "Kadugodi",
            "latitude": 12.9985,
            "longitude": 77.7610,
            "supported_species": ["DOG"],
            "max_pet_weight_kg": 40.0,
            "special_capabilities": ["PUPPY_CARE", "DAILY_PHOTO_UPDATES", "ORAL_MEDICATION"],
            "verification_status": "VERIFIED",
            "rating_average": 4.8,
            "review_count": 21,
            "services": [
                {"service_type": "PET_BOARDING", "price_inr": 850.0, "price_unit": "PER_NIGHT", "description": "Cozy home boarding with structured Care Plan adherence"},
                {"service_type": "IN_HOME_PET_SITTING", "price_inr": 1100.0, "price_unit": "PER_NIGHT", "description": "Overnight sitting at your home"},
                {"service_type": "DROP_IN_VISITS", "price_inr": 350.0, "price_unit": "PER_VISIT", "duration_minutes": 60, "description": "1-hour feeding & play check-in"},
            ],
        },
        {
            "email": "priya.sitter@pawcare.in",
            "full_name": "Priya Menon",
            "phone": "+91-9845033344",
            "bio": "Veterinary nursing assistant in Indiranagar offering specialized care for dogs & cats requiring medication.",
            "years_of_experience": 5,
            "locality": "Indiranagar",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "supported_species": ["DOG", "CAT"],
            "max_pet_weight_kg": 35.0,
            "special_capabilities": ["MEDICATION_ADMINISTRATION", "FIRST_AID_CERTIFIED"],
            "verification_status": "UNDER_REVIEW",
            "rating_average": 0.0,
            "review_count": 0,
            "services": [
                {"service_type": "DROP_IN_VISITS", "price_inr": 400.0, "price_unit": "PER_VISIT", "duration_minutes": 45, "description": "Medical & feeding drop-in visit"},
                {"service_type": "DAY_CARE", "price_inr": 700.0, "price_unit": "PER_DAY", "description": "Supervised day care"},
            ],
        },
    ]

    primary_caregiver_user = None
    for spec in demo_caregivers_spec:
        cg_user = user_repo.get_by_email(spec["email"])
        if cg_user is None:
            cg_user = user_repo.create_user(
                email=spec["email"],
                full_name=spec["full_name"],
                phone=spec["phone"],
                password_hash=hash_password("Password123"),
                role=UserRole.CAREGIVER.value,
            )
        if primary_caregiver_user is None:
            primary_caregiver_user = cg_user

        cg_prof = cg_repo.get_by_user_id(cg_user.id)
        if cg_prof is None:
            cg_prof = cg_repo.create_caregiver(
                user_id=cg_user.id,
                fields={
                    "bio": spec["bio"],
                    "years_of_experience": spec["years_of_experience"],
                    "experience_summary": f"{spec['years_of_experience']} years of hands-on pet care in Bengaluru.",
                    "city": "Bengaluru",
                    "locality": spec["locality"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "service_radius_km": 12.0,
                    "supported_species": spec["supported_species"],
                    "max_pet_weight_kg": spec["max_pet_weight_kg"],
                    "special_capabilities": spec["special_capabilities"],
                    "boarding_details": {
                        "home_type": "Independent House",
                        "has_fenced_yard": True,
                        "max_pets_hosted": 2,
                        "is_smoke_free": True,
                        "has_resident_pets": False,
                        "notes": "Dedicated pet play zone and 24/7 supervision",
                    },
                },
            )
            cg_repo.update_caregiver(
                cg_prof.id,
                {
                    "verification_status": spec["verification_status"],
                    "rating_average": spec["rating_average"],
                    "review_count": spec["review_count"],
                },
            )
            cg_repo.replace_services(cg_prof.id, spec["services"])
            if spec["verification_status"] == "UNDER_REVIEW":
                cg_repo.create_verification(
                    caregiver_id=cg_prof.id,
                    category="IDENTITY",
                    document_reference="verifications/priya/aadhaar_verified.pdf",
                    notes="Awaiting Admin final sign-off",
                )
            if not avail_repo.list_slots_for_caregiver(cg_prof.id, only_open=False):
                avail_repo.create_slot(
                    caregiver_id=cg_prof.id,
                    start_iso="2026-11-15T00:00:00Z",
                    end_iso="2026-12-31T23:59:00Z",
                    max_capacity=2,
                    notes="Available for November & December 2026 stays",
                )

    return {
        "status": "seeded",
        "pet_parent": {
            "email": parent.email,
            "full_name": parent.full_name,
            "role": parent.role,
            "access_token": create_jwt_token(subject=parent.id, role=parent.role, token_type="access"),
            "pet_id": bruno.id,
            "pet_name": bruno.name,
        },
        "caregiver": {
            "email": primary_caregiver_user.email,
            "full_name": primary_caregiver_user.full_name,
            "role": primary_caregiver_user.role,
            "access_token": create_jwt_token(
                subject=primary_caregiver_user.id,
                role=primary_caregiver_user.role,
                token_type="access",
            ),
        },
        "admin": {
            "email": admin.email,
            "full_name": admin.full_name,
            "role": admin.role,
            "access_token": create_jwt_token(subject=admin.id, role=admin.role, token_type="access"),
        },
    }
