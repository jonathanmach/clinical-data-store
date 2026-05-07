from database import SessionLocal
from models import (
    ClinicalConcept,
    CodeSystem,
    ConceptMapping,
    ConceptType,
    MappingRelationship,
    VocabularySystem,
)

_FHIR_URLS: dict[VocabularySystem, str] = {
    VocabularySystem.SNOMED_CT: "http://snomed.info/sct",
    VocabularySystem.LOINC: "http://loinc.org",
    VocabularySystem.RxNorm: "http://www.nlm.nih.gov/research/umls/rxnorm",
    VocabularySystem.ICD11: "http://id.who.int/icd/release/11/mms",
    VocabularySystem.UCUM: "http://unitsofmeasure.org",
    VocabularySystem.LOCAL: "urn:local",
}


def seed_reference_data() -> None:
    session = SessionLocal()
    try:
        for vs in VocabularySystem:
            if not session.get(CodeSystem, vs.value):
                session.add(CodeSystem(id=vs.value, name=vs.name, url=_FHIR_URLS[vs]))
        session.commit()
    finally:
        session.close()


def seed_data() -> None:
    session = SessionLocal()
    try:
        diabetes_snomed = ClinicalConcept(
            code="73211009",
            display="Diabetes mellitus",
            vocabulary_system_id=VocabularySystem.SNOMED_CT.value,
            concept_type=ConceptType.Conditions,
            standard=True,
        )
        diabetes_icd11 = ClinicalConcept(
            code="5A1",
            display="Diabetes mellitus",
            vocabulary_system_id=VocabularySystem.ICD11.value,
            concept_type=ConceptType.Conditions,
            standard=False,
        )
        session.add_all([diabetes_snomed, diabetes_icd11])
        session.flush()

        session.add(ConceptMapping(
            source_concept_id=diabetes_icd11.id,
            standard_concept_id=diabetes_snomed.id,
            relationship=MappingRelationship.equivalent,
        ))
        session.commit()
    finally:
        session.close()
