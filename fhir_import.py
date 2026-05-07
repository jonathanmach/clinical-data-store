import json
from datetime import datetime
from pathlib import Path

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.observation import Observation
from fhir.resources.quantity import Quantity
from sqlalchemy.orm import Session

from models import (
    ClinicalConcept,
    ClinicalObservation,
    ConceptType,
    ObservationStatus,
    ObservationValueType,
    Patient,
    VocabularySystem,
)

_FHIR_SYSTEM_MAP: dict[str, VocabularySystem] = {
    "http://loinc.org": VocabularySystem.LOINC,
    "http://snomed.info/sct": VocabularySystem.SNOMED_CT,
    "http://www.nlm.nih.gov/research/umls/rxnorm": VocabularySystem.RxNorm,
    "http://unitsofmeasure.org": VocabularySystem.UCUM,
}

_FHIR_STATUS_MAP: dict[str, ObservationStatus] = {
    "preliminary": ObservationStatus.preliminary,
    "final": ObservationStatus.final,
    "amended": ObservationStatus.amended,
    "corrected": ObservationStatus.corrected,
    "cancelled": ObservationStatus.cancelled,
    "entered-in-error": ObservationStatus.entered_in_error,
}


def _get_or_create_concept(
    session: Session, code: str, display: str, system_url: str, concept_type: ConceptType
) -> ClinicalConcept:
    vocab = _FHIR_SYSTEM_MAP.get(system_url, VocabularySystem.LOCAL)
    concept = session.query(ClinicalConcept).filter_by(code=code, vocabulary_system_id=vocab.value).first()
    if concept is None:
        concept = ClinicalConcept(
            code=code,
            display=display,
            vocabulary_system_id=vocab.value,
            concept_type=concept_type,
            standard=vocab != VocabularySystem.LOCAL,
        )
        session.add(concept)
        session.flush()
    return concept


def _import_observation_row(
    session: Session,
    patient_id: str,
    code_coding: Coding,
    effective_at: datetime,
    status: ObservationStatus,
    value_quantity: Quantity | None = None,
    value_codeable_concept: CodeableConcept | None = None,
) -> ClinicalObservation:
    concept = _get_or_create_concept(
        session,
        str(code_coding.code),
        str(code_coding.display or code_coding.code),
        str(code_coding.system),
        ConceptType.Observations,
    )

    row = ClinicalObservation(
        patient_id=patient_id,
        concept_id=concept.id,
        effective_at=effective_at,
        status=status,
    )

    if value_quantity is not None:
        row.value_type = ObservationValueType.quantity
        row.value_number = float(value_quantity.value) if value_quantity.value is not None else None
        if value_quantity.code:
            unit = _get_or_create_concept(
                session,
                str(value_quantity.code),
                str(value_quantity.unit or value_quantity.code),
                "http://unitsofmeasure.org",
                ConceptType.Units,
            )
            row.unit_concept_id = unit.id
    elif value_codeable_concept is not None and value_codeable_concept.coding:
        row.value_type = ObservationValueType.concept
        coding = value_codeable_concept.coding[0]
        val_concept = _get_or_create_concept(
            session,
            str(coding.code),
            str(coding.display or coding.code),
            str(coding.system),
            ConceptType.Observations,
        )
        row.value_concept_id = val_concept.id
    else:
        row.value_type = ObservationValueType.string

    session.add(row)
    return row


def import_fhir_bundle(session: Session, bundle_path: str | Path) -> int:
    with open(bundle_path) as f:
        raw = json.load(f)

    patient_raw = next(e["resource"] for e in raw["entry"] if e["resource"]["resourceType"] == "Patient")
    patient_id = patient_raw["id"]

    if session.get(Patient, patient_id) is None:
        session.add(
            Patient(
                id=patient_id,
                name=f"{patient_raw['name'][0]['family']}, {patient_raw['name'][0]['given'][0]}",
            )
        )
        session.flush()

    count = 0
    for entry in raw["entry"]:
        resource = entry["resource"]
        if resource["resourceType"] != "Observation":
            continue

        obs = Observation.model_validate(resource)
        if not obs.effectiveDateTime or not obs.status or not obs.code.coding:
            raise NotImplementedError("Only observations with effectiveDateTime, status, and coding are supported")
        effective_at: datetime = obs.effectiveDateTime
        status = _FHIR_STATUS_MAP[obs.status]

        if obs.component:
            for comp in obs.component:
                if not comp.code.coding:
                    raise NotImplementedError(
                        "Only observations with effectiveDateTime, status, and coding are supported"
                    )
                _import_observation_row(
                    session,
                    patient_id,
                    comp.code.coding[0],
                    effective_at,
                    status,
                    value_quantity=comp.valueQuantity,
                    value_codeable_concept=comp.valueCodeableConcept,
                )
                count += 1
        else:
            _import_observation_row(
                session,
                patient_id,
                obs.code.coding[0],
                effective_at,
                status,
                value_quantity=obs.valueQuantity,
                value_codeable_concept=obs.valueCodeableConcept,
            )
            count += 1

    session.commit()
    return count
