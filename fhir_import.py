import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.condition import Condition
from fhir.resources.observation import Observation
from fhir.resources.quantity import Quantity
from sqlalchemy.orm import Session

from models import (
    CareSite,
    ClinicalConcept,
    ClinicalCondition,
    ClinicalEncounter,
    ClinicalMedication,
    ClinicalObservation,
    ClinicalProcedure,
    ConceptType,
    ConditionClinicalStatus,
    ConditionVerificationStatus,
    EncounterStatus,
    MedicationRequestIntent,
    MedicationRequestStatus,
    ObservationStatus,
    ObservationValueType,
    Patient,
    ProcedureStatus,
    ServiceProvider,
    VocabularySystem,
)

_FHIR_SYSTEM_MAP: dict[str, VocabularySystem] = {
    "http://loinc.org": VocabularySystem.LOINC,
    "http://snomed.info/sct": VocabularySystem.SNOMED_CT,
    "http://www.nlm.nih.gov/research/umls/rxnorm": VocabularySystem.RxNorm,
    "http://unitsofmeasure.org": VocabularySystem.UCUM,
    "http://terminology.hl7.org/CodeSystem/v3-ActCode": VocabularySystem.V3_ACT_CODE,
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


def _get_or_create_service_provider(
    session: Session, name: str, external_id: str | None
) -> ServiceProvider:
    sp = session.query(ServiceProvider).filter_by(name=name).first()
    if sp is None:
        sp = ServiceProvider(name=name, external_id=external_id)
        session.add(sp)
        session.flush()
    return sp


def _get_or_create_care_site(
    session: Session, name: str, external_id: str | None
) -> CareSite:
    cs = session.query(CareSite).filter_by(name=name).first()
    if cs is None:
        cs = CareSite(name=name, external_id=external_id)
        session.add(cs)
        session.flush()
    return cs


class FhirResourceImporter(ABC):
    resource_type: ClassVar[str]

    @abstractmethod
    def import_entry(self, session: Session, patient_id: str, resource: dict) -> int:
        """Returns the number of DB rows inserted (may be >1 for component observations)."""


class ObservationImporter(FhirResourceImporter):
    resource_type = "Observation"

    _STATUS_MAP: ClassVar[dict[str, ObservationStatus]] = {
        "preliminary": ObservationStatus.preliminary,
        "final": ObservationStatus.final,
        "amended": ObservationStatus.amended,
        "corrected": ObservationStatus.corrected,
        "cancelled": ObservationStatus.cancelled,
        "entered-in-error": ObservationStatus.entered_in_error,
    }

    def _import_row(
        self,
        session: Session,
        patient_id: str,
        code_coding: Coding,
        effective_at: datetime,
        status: ObservationStatus,
        value_quantity: Quantity | None = None,
        value_codeable_concept: CodeableConcept | None = None,
        value_text: str | None = None,
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
        elif value_text is not None:
            row.value_type = ObservationValueType.string
            row.value_text = value_text
        else:
            raise NotImplementedError("Observation has no supported value type (valueQuantity, valueCodeableConcept, or valueString)")

        session.add(row)
        return row

    def import_entry(self, session: Session, patient_id: str, resource: dict) -> int:
        obs = Observation.model_validate(resource)
        if not obs.effectiveDateTime or not obs.status or not obs.code.coding:
            raise NotImplementedError("Only observations with effectiveDateTime, status, and coding are supported")
        effective_at: datetime = obs.effectiveDateTime
        status = self._STATUS_MAP[obs.status]

        if obs.component:
            for comp in obs.component:
                if not comp.code.coding:
                    raise NotImplementedError(
                        "Only observations with effectiveDateTime, status, and coding are supported"
                    )
                self._import_row(
                    session,
                    patient_id,
                    comp.code.coding[0],
                    effective_at,
                    status,
                    value_quantity=comp.valueQuantity,
                    value_codeable_concept=comp.valueCodeableConcept,
                    value_text=comp.valueString,
                )
            return len(obs.component)
        else:
            self._import_row(
                session,
                patient_id,
                obs.code.coding[0],
                effective_at,
                status,
                value_quantity=obs.valueQuantity,
                value_codeable_concept=obs.valueCodeableConcept,
                value_text=obs.valueString,
            )
            return 1


class ConditionImporter(FhirResourceImporter):
    resource_type = "Condition"

    _CLINICAL_STATUS_MAP: ClassVar[dict[str, ConditionClinicalStatus]] = {
        "active": ConditionClinicalStatus.active,
        "recurrence": ConditionClinicalStatus.recurrence,
        "relapse": ConditionClinicalStatus.relapse,
        "inactive": ConditionClinicalStatus.inactive,
        "remission": ConditionClinicalStatus.remission,
        "resolved": ConditionClinicalStatus.resolved,
        "unknown": ConditionClinicalStatus.unknown,
    }

    _VERIFICATION_STATUS_MAP: ClassVar[dict[str, ConditionVerificationStatus]] = {
        "unconfirmed": ConditionVerificationStatus.unconfirmed,
        "provisional": ConditionVerificationStatus.provisional,
        "differential": ConditionVerificationStatus.differential,
        "confirmed": ConditionVerificationStatus.confirmed,
        "refuted": ConditionVerificationStatus.refuted,
        "entered-in-error": ConditionVerificationStatus.entered_in_error,
    }
    # ConditionVerificationStatus.suspected has no FHIR mapping — internal use only

    def _import_row(
        self,
        session: Session,
        patient_id: str,
        code_coding: Coding,
        clinical_status: ConditionClinicalStatus,
        recorded_at: datetime,
        verification_status: ConditionVerificationStatus | None = None,
        onset_at: datetime | None = None,
        abatement_at: datetime | None = None,
    ) -> ClinicalCondition:
        concept = _get_or_create_concept(
            session,
            str(code_coding.code),
            str(code_coding.display or code_coding.code),
            str(code_coding.system),
            ConceptType.Conditions,
        )
        row = ClinicalCondition(
            patient_id=patient_id,
            concept_id=concept.id,
            clinical_status=clinical_status,
            verification_status=verification_status,
            onset_at=onset_at,
            abatement_at=abatement_at,
            recorded_at=recorded_at,
        )
        session.add(row)
        return row

    def import_entry(self, session: Session, patient_id: str, resource: dict) -> int:
        cond = Condition.model_validate(resource)

        if not cond.code or not cond.code.coding:
            raise NotImplementedError("Only Conditions with code.coding are supported")
        if not cond.clinicalStatus or not cond.clinicalStatus.coding:
            raise NotImplementedError("Only Conditions with clinicalStatus.coding are supported")

        clinical_status_code = str(cond.clinicalStatus.coding[0].code)
        clinical_status = self._CLINICAL_STATUS_MAP.get(clinical_status_code)
        if clinical_status is None:
            raise ValueError(f"Unknown Condition clinicalStatus code: {clinical_status_code!r}")

        verification_status: ConditionVerificationStatus | None = None
        if cond.verificationStatus and cond.verificationStatus.coding:
            ver_code = str(cond.verificationStatus.coding[0].code)
            verification_status = self._VERIFICATION_STATUS_MAP.get(ver_code)

        recorded_at: datetime = cond.recordedDate if cond.recordedDate is not None else datetime.now(timezone.utc)

        self._import_row(
            session,
            patient_id,
            cond.code.coding[0],
            clinical_status,
            recorded_at,
            verification_status=verification_status,
            onset_at=cond.onsetDateTime,
            abatement_at=cond.abatementDateTime,
        )
        return 1


class EncounterImporter(FhirResourceImporter):
    resource_type = "Encounter"

    _STATUS_MAP: ClassVar[dict[str, EncounterStatus]] = {
        "planned": EncounterStatus.planned,
        "arrived": EncounterStatus.arrived,
        "triaged": EncounterStatus.triaged,
        "in-progress": EncounterStatus.in_progress,
        "onleave": EncounterStatus.on_leave,
        "finished": EncounterStatus.finished,
        "cancelled": EncounterStatus.cancelled,
        "entered-in-error": EncounterStatus.entered_in_error,
        "unknown": EncounterStatus.unknown,
    }

    def _import_row(
        self,
        session: Session,
        patient_id: str,
        class_coding: Coding,
        status: EncounterStatus,
        recorded_at: datetime,
        type_coding: Coding | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        service_provider_name: str | None = None,
        service_provider_external_id: str | None = None,
        care_site_name: str | None = None,
        care_site_external_id: str | None = None,
        external_id: str | None = None,
    ) -> ClinicalEncounter:
        class_concept = _get_or_create_concept(
            session,
            str(class_coding.code),
            str(class_coding.display or class_coding.code),
            str(class_coding.system),
            ConceptType.Encounters,
        )

        type_concept_id: str | None = None
        if type_coding is not None:
            type_concept = _get_or_create_concept(
                session,
                str(type_coding.code),
                str(type_coding.display or type_coding.code),
                str(type_coding.system),
                ConceptType.Encounters,
            )
            type_concept_id = type_concept.id

        sp_id: str | None = None
        if service_provider_name is not None:
            sp_id = _get_or_create_service_provider(session, service_provider_name, service_provider_external_id).id

        cs_id: str | None = None
        if care_site_name is not None:
            cs_id = _get_or_create_care_site(session, care_site_name, care_site_external_id).id

        row = ClinicalEncounter(
            patient_id=patient_id,
            class_concept_id=class_concept.id,
            type_concept_id=type_concept_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            recorded_at=recorded_at,
            service_provider_id=sp_id,
            care_site_id=cs_id,
            external_id=external_id,
        )
        session.add(row)
        return row

    def import_entry(self, session: Session, patient_id: str, resource: dict) -> int:
        # Parse R4 Encounter fields directly — fhir.resources 8.x is R5 and rejects R4 Encounter shape
        class_raw = resource.get("class")
        if not class_raw:
            raise NotImplementedError("Only Encounters with class are supported")

        enc_status_code = resource.get("status", "")
        enc_status = self._STATUS_MAP.get(enc_status_code)
        if enc_status is None:
            raise ValueError(f"Unknown Encounter status: {enc_status_code!r}")

        period = resource.get("period", {})
        started_at: datetime | None = datetime.fromisoformat(period["start"]) if "start" in period else None
        ended_at: datetime | None = datetime.fromisoformat(period["end"]) if "end" in period else None
        recorded_at: datetime = started_at if started_at is not None else datetime.now(timezone.utc)

        class_coding = Coding(
            code=class_raw.get("code"),
            system=class_raw.get("system"),
            display=class_raw.get("display"),
        )

        type_coding: Coding | None = None
        enc_type = resource.get("type", [])
        if enc_type and enc_type[0].get("coding"):
            tc = enc_type[0]["coding"][0]
            type_coding = Coding(code=tc.get("code"), system=tc.get("system"), display=tc.get("display"))

        sp_raw: dict[str, str] = resource.get("serviceProvider") or {}
        sp_name: str | None = sp_raw.get("display")
        sp_ext_id: str | None = sp_raw.get("reference")

        cs_name: str | None = None
        cs_ext_id: str | None = None
        location_raw = resource.get("location", [])
        if location_raw:
            loc_ref = location_raw[0].get("location", {})
            cs_name = loc_ref.get("display")
            cs_ext_id = loc_ref.get("reference")

        identifiers = resource.get("identifier", [])
        ext_id: str | None = identifiers[0].get("value") if identifiers else None

        self._import_row(
            session,
            patient_id,
            class_coding,
            enc_status,
            recorded_at,
            type_coding=type_coding,
            started_at=started_at,
            ended_at=ended_at,
            service_provider_name=sp_name,
            service_provider_external_id=sp_ext_id,
            care_site_name=cs_name,
            care_site_external_id=cs_ext_id,
            external_id=ext_id,
        )
        return 1


class ProcedureImporter(FhirResourceImporter):
    resource_type = "Procedure"

    _STATUS_MAP: ClassVar[dict[str, ProcedureStatus]] = {
        "preparation": ProcedureStatus.preparation,
        "in-progress": ProcedureStatus.in_progress,
        "not-done": ProcedureStatus.not_done,
        "on-hold": ProcedureStatus.on_hold,
        "stopped": ProcedureStatus.stopped,
        "completed": ProcedureStatus.completed,
        "entered-in-error": ProcedureStatus.entered_in_error,
        "unknown": ProcedureStatus.unknown,
    }

    def import_entry(self, session: Session, patient_id: str, resource: dict) -> int:
        # Parse R4 fields directly — fhir.resources 8.x is R5, which renamed performedPeriod to occurrencePeriod
        codings = resource.get("code", {}).get("coding", [])
        if not codings:
            raise NotImplementedError("Only Procedures with code.coding are supported")

        status_code = resource.get("status", "")
        status = self._STATUS_MAP.get(status_code)
        if status is None:
            raise ValueError(f"Unknown Procedure status: {status_code!r}")

        period = resource.get("performedPeriod", {})
        performed_at: datetime | None = datetime.fromisoformat(period["start"]) if "start" in period else None
        performed_end_at: datetime | None = datetime.fromisoformat(period["end"]) if "end" in period else None
        recorded_at: datetime = performed_at if performed_at is not None else datetime.now(timezone.utc)

        c = codings[0]
        code_coding = Coding(code=c.get("code"), system=c.get("system"), display=c.get("display"))
        concept = _get_or_create_concept(
            session,
            str(code_coding.code),
            str(code_coding.display or code_coding.code),
            str(code_coding.system),
            ConceptType.Procedures,
        )
        session.add(ClinicalProcedure(
            patient_id=patient_id,
            concept_id=concept.id,
            status=status,
            performed_at=performed_at,
            performed_end_at=performed_end_at,
            recorded_at=recorded_at,
        ))
        return 1


class MedicationRequestImporter(FhirResourceImporter):
    resource_type = "MedicationRequest"

    _STATUS_MAP: ClassVar[dict[str, MedicationRequestStatus]] = {
        "active": MedicationRequestStatus.active,
        "on-hold": MedicationRequestStatus.on_hold,
        "cancelled": MedicationRequestStatus.cancelled,
        "completed": MedicationRequestStatus.completed,
        "entered-in-error": MedicationRequestStatus.entered_in_error,
        "stopped": MedicationRequestStatus.stopped,
        "draft": MedicationRequestStatus.draft,
        "unknown": MedicationRequestStatus.unknown,
    }
    _INTENT_MAP: ClassVar[dict[str, MedicationRequestIntent]] = {
        "proposal": MedicationRequestIntent.proposal,
        "plan": MedicationRequestIntent.plan,
        "order": MedicationRequestIntent.order,
        "original-order": MedicationRequestIntent.original_order,
        "reflex-order": MedicationRequestIntent.reflex_order,
        "filler-order": MedicationRequestIntent.filler_order,
        "instance-order": MedicationRequestIntent.instance_order,
        "option": MedicationRequestIntent.option,
    }

    def import_entry(self, session: Session, patient_id: str, resource: dict) -> int:
        # Parse R4 fields directly — fhir.resources 8.x is R5, which renamed medicationCodeableConcept to medication (CodeableReference)
        codings = resource.get("medicationCodeableConcept", {}).get("coding", [])
        if not codings:
            raise NotImplementedError("Only MedicationRequests with medicationCodeableConcept.coding are supported")

        status_code = resource.get("status", "")
        status = self._STATUS_MAP.get(status_code)
        if status is None:
            raise ValueError(f"Unknown MedicationRequest status: {status_code!r}")

        intent_code = resource.get("intent", "")
        intent = self._INTENT_MAP.get(intent_code)
        if intent is None:
            raise ValueError(f"Unknown MedicationRequest intent: {intent_code!r}")

        authored_on_raw: str | None = resource.get("authoredOn")
        authored_at: datetime | None = datetime.fromisoformat(authored_on_raw) if authored_on_raw else None
        recorded_at: datetime = authored_at if authored_at is not None else datetime.now(timezone.utc)

        c = codings[0]
        code_coding = Coding(code=c.get("code"), system=c.get("system"), display=c.get("display"))
        concept = _get_or_create_concept(
            session,
            str(code_coding.code),
            str(code_coding.display or code_coding.code),
            str(code_coding.system),
            ConceptType.Medications,
        )
        session.add(ClinicalMedication(
            patient_id=patient_id,
            concept_id=concept.id,
            status=status,
            intent=intent,
            authored_at=authored_at,
            recorded_at=recorded_at,
        ))
        return 1


_IMPORTERS: list[FhirResourceImporter] = [
    ObservationImporter(),
    ConditionImporter(),
    EncounterImporter(),
    ProcedureImporter(),
    MedicationRequestImporter(),
]


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

    # Some R4 bundles use a standalone Medication resource + medicationReference instead of
    # inline medicationCodeableConcept. Build an index so we can resolve those references.
    medication_index: dict[str, dict] = {
        e["fullUrl"]: e["resource"]
        for e in raw["entry"]
        if e["resource"]["resourceType"] == "Medication"
    }

    dispatch = {imp.resource_type: imp for imp in _IMPORTERS}
    count = 0
    for entry in raw["entry"]:
        resource = entry["resource"]
        if resource.get("resourceType") == "MedicationRequest" and "medicationReference" in resource:
            ref = resource["medicationReference"].get("reference", "")
            med = medication_index.get(ref)
            if med and med.get("code", {}).get("coding"):
                resource = {**resource, "medicationCodeableConcept": med["code"]}
        if importer := dispatch.get(resource["resourceType"]):
            count += importer.import_entry(session, patient_id, resource)

    session.commit()
    return count
