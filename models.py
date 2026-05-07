import enum
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


class CodeSystem(Base):
    __tablename__ = "code_systems"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String, nullable=False)


class ClinicalConcept(Base):
    __tablename__ = "clinical_concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    display: Mapped[str] = mapped_column(String, nullable=False)
    vocabulary_system_id: Mapped[str] = mapped_column(ForeignKey("code_systems.id"), nullable=False)
    concept_type: Mapped[ConceptType] = mapped_column(Enum(ConceptType), nullable=False)
    standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ConceptMapping(Base):
    __tablename__ = "concept_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_concept_id: Mapped[int] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    standard_concept_id: Mapped[int] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
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


class ClinicalObservation(Base):
    __tablename__ = "clinical_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False)

    concept_id: Mapped[int] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=False)
    source_concept_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    value_type: Mapped[ObservationValueType] = mapped_column(Enum(ObservationValueType), nullable=False)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_integer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    value_concept_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    unit_concept_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_concepts.id"), nullable=True)

    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[ObservationStatus] = mapped_column(Enum(ObservationStatus), nullable=False)

    concept: Mapped["ClinicalConcept"] = relationship(foreign_keys=[concept_id])
