import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class VocabularySystem(enum.Enum):
    SNOMED_CT = "snomed-ct"
    LOINC = "loinc"
    RxNorm = "rxnorm"
    ICD11 = "icd-11"
    UCUM = "ucum"
    LOCAL = "sano-local"
    V3_ACT_CODE = "hl7-v3-act-code"


class MappingRelationship(enum.Enum):
    exact = "exact"
    equivalent = "equivalent"
    broader = "broader"
    narrower = "narrower"


class ConceptType(enum.Enum):
    Observations = "observations"
    Conditions = "conditions"
    Medications = "medications"
    Procedures = "procedures"
    Units = "units"
    Encounters = "encounters"


class CodeSystem(Base):
    __tablename__ = "code_systems"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String, nullable=False)


class ClinicalConcept(Base):
    __tablename__ = "clinical_concepts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String, nullable=False)
    display: Mapped[str] = mapped_column(String, nullable=False)
    vocabulary_system_id: Mapped[str] = mapped_column(ForeignKey("code_systems.id"), nullable=False)
    concept_type: Mapped[ConceptType] = mapped_column(Enum(ConceptType), nullable=False)
    standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ConceptMapping(Base):
    __tablename__ = "concept_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    standard_concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    relationship: Mapped[MappingRelationship] = mapped_column(Enum(MappingRelationship), nullable=False)


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


"""
Observations
"""


class ObservationValueType(enum.Enum):
    quantity = "quantity"
    concept = "concept"
    string = "string"
    boolean = "boolean"
    datetime = "datetime"
    integer = "integer"


class ObservationStatus(enum.Enum):
    preliminary = "preliminary"
    final = "final"
    amended = "amended"
    corrected = "corrected"
    cancelled = "cancelled"
    entered_in_error = "entered_in_error"


class ConditionClinicalStatus(enum.Enum):
    active = "active"
    recurrence = "recurrence"
    relapse = "relapse"
    inactive = "inactive"
    remission = "remission"
    resolved = "resolved"
    unknown = "unknown"


class ConditionVerificationStatus(enum.Enum):
    unconfirmed = "unconfirmed"
    provisional = "provisional"
    differential = "differential"
    confirmed = "confirmed"
    refuted = "refuted"
    entered_in_error = "entered_in_error"
    suspected = "suspected"  # internal use only; no FHIR equivalent


class ClinicalObservation(Base):
    __tablename__ = "clinical_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    # source_concept_id: Optional reference to the original source concept for provenance/audit purposes. This allows us to retain the original code even if we later map it to a different standard concept.
    source_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    value_type: Mapped[ObservationValueType] = mapped_column(Enum(ObservationValueType), nullable=False)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_integer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    value_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    unit_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[ObservationStatus] = mapped_column(Enum(ObservationStatus), nullable=False)

    concept: Mapped["ClinicalConcept"] = relationship(foreign_keys=[concept_id])


"""
Conditions
"""


class ClinicalCondition(Base):
    __tablename__ = "clinical_conditions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    source_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    clinical_status: Mapped[ConditionClinicalStatus] = mapped_column(Enum(ConditionClinicalStatus), nullable=False)
    verification_status: Mapped[ConditionVerificationStatus | None] = mapped_column(
        Enum(ConditionVerificationStatus), nullable=True
    )

    onset_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    abatement_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    concept: Mapped["ClinicalConcept"] = relationship(foreign_keys=[concept_id])


"""
Procedures
"""


class ProcedureStatus(enum.Enum):
    preparation = "preparation"
    in_progress = "in_progress"
    not_done = "not_done"
    on_hold = "on_hold"
    stopped = "stopped"
    completed = "completed"
    entered_in_error = "entered_in_error"
    unknown = "unknown"


class ClinicalProcedure(Base):
    __tablename__ = "clinical_procedures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    source_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    status: Mapped[ProcedureStatus] = mapped_column(Enum(ProcedureStatus), nullable=False)

    performed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    performed_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    concept: Mapped["ClinicalConcept"] = relationship(foreign_keys=[concept_id])


"""
Medications
"""


class MedicationRequestStatus(enum.Enum):
    active = "active"
    on_hold = "on_hold"
    cancelled = "cancelled"
    completed = "completed"
    entered_in_error = "entered_in_error"
    stopped = "stopped"
    draft = "draft"
    unknown = "unknown"


class MedicationRequestIntent(enum.Enum):
    proposal = "proposal"
    plan = "plan"
    order = "order"
    original_order = "original_order"
    reflex_order = "reflex_order"
    filler_order = "filler_order"
    instance_order = "instance_order"
    option = "option"


class ClinicalMedication(Base):
    __tablename__ = "clinical_medications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    source_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    status: Mapped[MedicationRequestStatus] = mapped_column(Enum(MedicationRequestStatus), nullable=False)
    intent: Mapped[MedicationRequestIntent] = mapped_column(Enum(MedicationRequestIntent), nullable=False)

    authored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    concept: Mapped["ClinicalConcept"] = relationship(foreign_keys=[concept_id])


"""
Encounters
"""


class EncounterStatus(enum.Enum):
    planned = "planned"
    arrived = "arrived"
    triaged = "triaged"
    in_progress = "in_progress"
    on_leave = "on_leave"
    finished = "finished"
    cancelled = "cancelled"
    entered_in_error = "entered_in_error"
    unknown = "unknown"


class ServiceProvider(Base):
    __tablename__ = "service_providers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)


class CareSite(Base):
    __tablename__ = "care_sites"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)


class ClinicalEncounter(Base):
    __tablename__ = "clinical_encounters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    class_concept_id: Mapped[str] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    type_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    status: Mapped[EncounterStatus] = mapped_column(Enum(EncounterStatus), nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    service_provider_id: Mapped[str | None] = mapped_column(ForeignKey("service_providers.id"), nullable=True)
    care_site_id: Mapped[str | None] = mapped_column(ForeignKey("care_sites.id"), nullable=True)

    source_concept_id: Mapped[str | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)

    concept: Mapped["ClinicalConcept"] = relationship(foreign_keys=[class_concept_id])


# TODO: Provenance tables to track source of data, transformations, etc.