# Schema

```mermaid
erDiagram
    code_systems {
        string id PK
        string name
        string url
    }
    clinical_concepts {
        string id PK
        string code
        string display
        string vocabulary_system_id FK
        enum concept_type
        boolean standard
    }
    concept_mappings {
        string id PK
        string source_concept_id FK
        string standard_concept_id FK
        enum relationship
    }
    patients {
        string id PK
        string name
    }
    clinical_observations {
        string id PK
        string patient_id FK
        string concept_id FK
        string source_concept_id FK
        enum value_type
        float value_number
        int value_integer
        string value_text
        boolean value_boolean
        datetime value_datetime
        string value_concept_id FK
        string unit_concept_id FK
        datetime effective_at
        enum status
    }
    clinical_conditions {
        string id PK
        string patient_id FK
        string concept_id FK
        string source_concept_id FK
        enum clinical_status
        enum verification_status
        datetime onset_at
        datetime abatement_at
        datetime recorded_at
    }
    clinical_procedures {
        string id PK
        string patient_id FK
        string concept_id FK
        string source_concept_id FK
        enum status
        datetime performed_at
        datetime performed_end_at
        datetime recorded_at
    }
    clinical_medications {
        string id PK
        string patient_id FK
        string concept_id FK
        string source_concept_id FK
        enum status
        enum intent
        datetime authored_at
        datetime recorded_at
    }
    service_providers {
        string id PK
        string name
        string external_id
    }
    care_sites {
        string id PK
        string name
        string external_id
    }
    clinical_encounters {
        string id PK
        string patient_id FK
        string class_concept_id FK
        string type_concept_id FK
        string source_concept_id FK
        enum status
        datetime started_at
        datetime ended_at
        datetime recorded_at
        string service_provider_id FK
        string care_site_id FK
        string external_id
    }

    code_systems ||--o{ clinical_concepts : "vocabulary_system"
    clinical_concepts ||--o{ concept_mappings : "source_concept"
    clinical_concepts ||--o{ concept_mappings : "standard_concept"

    patients ||--o{ clinical_observations : ""
    clinical_concepts ||--o{ clinical_observations : "concept"
    clinical_concepts |o--o{ clinical_observations : "source_concept"
    clinical_concepts |o--o{ clinical_observations : "value_concept"
    clinical_concepts |o--o{ clinical_observations : "unit_concept"

    patients ||--o{ clinical_conditions : ""
    clinical_concepts ||--o{ clinical_conditions : "concept"
    clinical_concepts |o--o{ clinical_conditions : "source_concept"

    patients ||--o{ clinical_procedures : ""
    clinical_concepts ||--o{ clinical_procedures : "concept"
    clinical_concepts |o--o{ clinical_procedures : "source_concept"

    patients ||--o{ clinical_medications : ""
    clinical_concepts ||--o{ clinical_medications : "concept"
    clinical_concepts |o--o{ clinical_medications : "source_concept"

    patients ||--o{ clinical_encounters : ""
    clinical_concepts ||--o{ clinical_encounters : "class_concept"
    clinical_concepts |o--o{ clinical_encounters : "type_concept"
    clinical_concepts |o--o{ clinical_encounters : "source_concept"
    service_providers |o--o{ clinical_encounters : ""
    care_sites |o--o{ clinical_encounters : ""
```

---

# Sample Queries

Run raw SQL query joining patient, observations, and concepts

```sql
SELECT
    p.name                          AS patient,
    obs_c.code                      AS concept_code,
    obs_c.display                   AS concept_display,
    cs.name                         AS vocabulary,
    co.value_type,
    co.value_number,
    val_c.display                   AS value_concept,
    unit_c.code                     AS unit,
    co.effective_at,
    co.status
FROM clinical_observations co
JOIN patients p              ON p.id = co.patient_id
JOIN clinical_concepts obs_c ON obs_c.id = co.concept_id
JOIN code_systems cs         ON cs.id = obs_c.vocabulary_system_id
LEFT JOIN clinical_concepts val_c  ON val_c.id = co.value_concept_id
LEFT JOIN clinical_concepts unit_c ON unit_c.id = co.unit_concept_id;
```
