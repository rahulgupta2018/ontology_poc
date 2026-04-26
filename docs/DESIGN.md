# Enterprise Architecture Knowledge Graph — Design Document

**Version:** 0.1 (Draft for review)  
**Status:** In discussion  
**Authors:** TBD

---

## 1. Vision

A single, queryable knowledge graph that captures the full body of enterprise and solution architecture knowledge — documents, decisions, patterns, components, systems, teams — across all generations (past and present). Anyone in the organisation can ask architecture questions in plain English and get answers grounded in real documentation.

---

## 2. Design Principles

| # | Principle | Implication |
|---|---|---|
| 1 | **Ontology-first** | The schema is defined before ingestion. Documents are mapped *to* the ontology, not the other way around. |
| 2 | **Ontology stability** | The ontology evolves deliberately, not in response to individual documents. A document that introduces a new concept triggers a governed ontology change process, not an ad-hoc patch. |
| 3 | **Documents are evidence** | Source documents are stored as nodes (`Document`) with provenance metadata. Knowledge extracted from them is linked back with `EXTRACTED_FROM` edges. |
| 4 | **LLM assists, ontology governs** | LLMs extract and classify; the ontology validates and rejects. Humans review ambiguous extractions. |
| 5 | **Graph as single source of truth** | The Neo4j graph is the canonical knowledge store. All tools (Q&A, dashboards, reports) read from the graph. |

---

## 3. Ontology Stability Strategy

This is the central challenge: how do we load hundreds of documents without breaking the schema?

### 3.1 The Core / Extension Split

```
┌─────────────────────────────────────────────────────────┐
│  CORE ONTOLOGY  (stable — change only via governance)   │
│                                                         │
│  ArchitecturalConcept, Component, System,               │
│  ArchitecturePattern, QualityAttribute, ADR,            │
│  Team, Person, Infrastructure, TechnologyChoice ...     │
│                                                         │
│  Object properties: dependsOn, exposesAPI, ownedBy,     │
│  followsPattern, storesDataIn, publishesTo, ...         │
└─────────────────────────────────────────────────────────┘
           ↑ stable, rarely changes
           
┌─────────────────────────────────────────────────────────┐
│  EXTENSION LAYER  (flexible — grows with documents)     │
│                                                         │
│  Concrete named nodes that are INSTANCES of core        │
│  classes: specific services, teams, systems, ADRs ...   │
│                                                         │
│  Tags / free-text labels on nodes (no schema change)    │
│                                                         │
│  Document nodes with raw text + metadata                │
└─────────────────────────────────────────────────────────┘
           ↑ grows freely without touching the ontology
```

**Rule:** A new document almost never requires an ontology change. It creates new *instances* of existing classes, or adds `Document` nodes linked to existing concepts.

### 3.2 When the Ontology Does Change

Triggers for a legitimate ontology change:
- A genuinely new *category* of architectural concept appears across multiple documents
- A new relationship type is needed that cannot be expressed by existing properties

Process:
1. Ingestion pipeline flags an unresolvable concept
2. Architecture governance team reviews
3. Ontology updated in `architecture_ontology.py` (versioned in git)
4. Migration script updates Neo4j (additive — no destructive changes)
5. All downstream extractors re-run on affected documents

### 3.3 Unknown Concepts During Ingestion

When the LLM extracts something that doesn't map to an existing class:

```
Extraction: "Sidecar proxy" → not in ontology

Options:
  A. Map to nearest superclass: Component (safe default)
  B. Tag with freetext: node.tags = ["sidecar", "proxy", "infrastructure"]  
  C. Flag for governance review: UnresolvedConcept node created
  D. Reject with reason logged
```

The ingestion pipeline applies A+B immediately and creates a `UnresolvedConcept` queue for human review. No ontology changes happen at ingestion time.

---

## 4. Ontology Architecture — Modular Design

The ontology is split into **five cohesive modules**. Each module can be loaded, versioned, and governed independently. Modules build on each other via shared root classes and cross-module object properties.

### 4.1 Module Overview & Dependencies

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MODULE DEPENDENCIES                          │
│                                                                     │
│   ORG  ──────────────────────────────────────────────────────────┐  │
│   Organisation                                                   │  │
│   (OrganisationUnit, Division, Platform, Lab, Team, Person)      │  │
│         │                                                        │  │
│         ▼                                                        │  │
│   SYS  ─────────────────────────────────────────────────────┐    │  │
│   System & Platform                                         │    │  │
│   (System, Component, Database, Infrastructure…)            │    │  │
│         │                                                   │    │  │
│         ▼                                                   │    │  │
│   ART  ──────────────────────────────────────────────┐      │    │  │
│   Architecture Artefact                              │      │    │  │
│   (Document, HLD, LLD, ADR, RFC, RunBook, Standard…) │      │    │  │
│         │                                            │      │    │  │
│         ▼                                            │      │    │  │
│   DEC  ────────────────────────────────────────┐     │      │    │  │
│   Decision & Pattern                           │     │      │    │  │
│   (ArchitecturalDecision, Pattern, QA, Tech…)  │     │      │    │  │
│         │                                      │     │      │    │  │
│         ▼                                      ▼     ▼      ▼    │  │
│   GOV  ──────────────────────────────────────────────────────┘   │  │
│   Governance & Risk                                              │  │
│   (Risk, Constraint, Requirement, Capability, Domain…)          ◄┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Module Namespace Convention

In owlready2 / OWL each module is a named ontology. In Neo4j, module membership is encoded as a node label prefix.

| Module | Prefix | OWL namespace |
|--------|--------|---------------|
| Organisation | `ORG` | `#org` |
| System & Platform | `SYS` | `#sys` |
| Architecture Artefact | `ART` | `#art` |
| Decision & Pattern | `DEC` | `#dec` |
| Governance & Risk | `GOV` | `#gov` |

A node can carry labels from multiple modules (e.g. `(:ADR:Document:ArchitecturalDecision)` spans ART and DEC).

---

## 5. Module 1 — Organisation Ontology (ORG)

### 5.1 OWL Class Hierarchy

```
ArchitecturalConcept  (root — all classes inherit from this)
└── OrganisationUnit
    ├── Division                        # Top-level business division (Retail, BCB, IP&P…)
    │   │                               # Instances live in ontology/instances/ — not subclassed here
    │   └── Platform                    # Business/product platform within a Division
    │       │                           # e.g. "Client Servicing & Engagement", "Commercial Lending"
    │       └── Lab                     # Delivery lab within a Platform, grouping related Teams
    │           │                       # e.g. "Payments & Transactions", "Digital Servicing"
    │           └── Team
    │               ├── PlatformTeam            # Infrastructure / platform engineering
    │               ├── StreamAlignedTeam       # Product / feature-focused teams
    │               ├── EnablingTeam            # Architecture, Security, Data teams
    │               └── ComplicatedSubsystemTeam  # Expert / specialist teams
    └── Person
        ├── Architect
        ├── Engineer
        └── ProductOwner
```

Key design decisions:
- The hierarchy is 4 levels: **Division → Platform → Lab → Team**. Example: `BCB → Client Servicing & Engagement → Payments & Transactions → Team A`.
- Division, Platform, and Lab names are **instance data**, not schema subclasses. They live in `ontology/instances/org_{division}.yaml` (ABox). The schema (`modules/org.yaml`) defines the classes only.
- Enabling teams (Architecture, Security) may `partOf` a Platform or Division directly, skipping the Lab level.
- `partOf` is **transitive** — a query for "all teams in BCB Division" traverses the full chain automatically.

### 5.2 Object Properties

| Property | Domain | Range | OWL Characteristics | Semantics |
|----------|--------|-------|---------------------|-----------|
| `partOf` | Team \| Lab \| Platform | Lab \| Platform \| Division | **Transitive** | Team → Lab → Platform → Division (full 4-level membership chain) |
| `owns` | Team | System \| Component | Inverse of `ownedBy` | Team is accountable owner |
| `ledBy` | Team | Person | **Functional** (max 1) | Team lead / DRI |
| `memberOf` | Person | Team | — | Person is member of this team |
| `reportsTo` | Team | OrganisationUnit | — | Organisational reporting line |

### 5.3 Data Properties

| Property | Domain | Type | Constraints | Example |
|----------|--------|------|-------------|---------|
| `name` | OrganisationUnit | string | NOT NULL, UNIQUE per label | `"Payments & Transactions"` |
| `code` | OrganisationUnit | string | — | `"BCB-CSE-PAY"` |
| `description` | OrganisationUnit | string | — | — |
| `teamType` | Team | enum | `platform \| stream-aligned \| enabling \| complicated-subsystem` | `"stream-aligned"` |
| `slackChannel` | Team | string | — | `"#bcb-pay-team-a"` |
| `contactEmail` | Team | string | — | `"bcb-pay-a@acme.com"` |
| `email` | Person | string | UNIQUE | `"jane@acme.com"` |
| `role` | Person | string | — | `"Solution Architect"` |
| `jobTitle` | Person | string | — | `"Principal Engineer"` |

---

## 6. Module 2 — System & Platform Ontology (SYS)

### 6.1 OWL Class Hierarchy

```
ArchitecturalConcept
└── System                      # Complete software system / product
└── Component                   # Deployable or logical unit within a system
    ├── Service
    │   ├── Microservice        # Fine-grained, independently deployable
    │   ├── MacroService        # Larger service (e.g. a monolith that exposes APIs)
    │   └── BackendForFrontend  # BFF — client-specific API aggregator
    ├── Library
    │   ├── SDK                 # External-facing SDK
    │   └── InternalLibrary     # Shared internal library
    ├── Database
    │   ├── RelationalDatabase  # PostgreSQL, MySQL, Oracle
    │   ├── DocumentDatabase    # MongoDB, DynamoDB, Firestore
    │   ├── GraphDatabase       # Neo4j, Neptune
    │   ├── CacheDatabase       # Redis, Memcached
    │   ├── TimeSeriesDatabase  # InfluxDB, TimescaleDB
    │   └── SearchIndex         # Elasticsearch, OpenSearch
    ├── MessageBroker           # Kafka, RabbitMQ, SQS
    ├── APIGateway              # Kong, AWS API GW, APIM
    ├── Frontend
    │   ├── WebApplication      # SPA, SSR web app
    │   └── MobileApplication   # iOS, Android
    ├── BatchJob                # Scheduled / event-triggered batch processing
    └── WorkflowEngine          # Temporal, Camunda, Step Functions
└── Infrastructure              # Physical / cloud infrastructure
    ├── CloudProvider           # AWS, Azure, GCP, OCP
    ├── ContainerOrchestrator   # Kubernetes, ECS, Nomad
    ├── CDN                     # Cloudfront, Fastly, Akamai
    ├── LoadBalancer            # ALB, NLB, HAProxy
    ├── NetworkZone             # VPC, subnet, DMZ
    └── ServiceMesh             # Istio, Linkerd, Consul Connect
```

### 6.2 Object Properties

| Property | Domain | Range | OWL Characteristics | Semantics |
|----------|--------|-------|---------------------|-----------|
| `belongsTo` | Component | System | Inverse of `composedOf` | Component is part of a system |
| `composedOf` | System | Component | Inverse of `belongsTo` | System contains this component |
| `dependsOn` | Component | Component | **Transitive** | Runtime / compile-time dependency |
| `exposesAPI` | Service | Component | — | Service provides an API endpoint |
| `consumesAPI` | Component | Service | — | Component calls this service's API |
| `storesDataIn` | Service | Database | — | Service's primary data store |
| `publishesTo` | Service | MessageBroker | — | Service produces events to broker |
| `subscribesTo` | Service | MessageBroker | — | Service consumes events from broker |
| `deployedOn` | Component | Infrastructure | — | Where component runs |
| `hostedOn` | System | Infrastructure | — | System's infrastructure home |
| `ownedBy` | Component \| System | Team | Inverse of `owns` (ORG) | Ownership link |

### 6.3 Data Properties

| Property | Domain | Type | Constraints | Example |
|----------|--------|------|-------------|---------|
| `systemId` | System | string | UNIQUE | `"SYS-001"` |
| `status` | System \| Component | enum | `active \| deprecated \| decommissioned` | `"active"` |
| `tier` | System | enum | `critical \| standard \| low` | `"critical"` |
| `classification` | System \| Component | enum | `public \| internal \| restricted` | `"internal"` |
| `version` | Component | string | — | `"2.3.1"` |
| `language` | Component | string | — | `"Python"` |
| `framework` | Component | string | — | `"FastAPI"` |
| `repositoryUrl` | Component | string | — | `"github.com/acme/order-svc"` |
| `hasEndpoint` | Service | string | — | `"https://api.acme.com/orders"` |
| `healthCheckUrl` | Service | string | — | `"/health"` |
| `dbEngine` | Database | string | — | `"PostgreSQL 16"` |
| `hostingType` | Database | enum | `managed \| self-hosted` | `"managed"` |
| `provider` | Infrastructure | string | — | `"AWS"` |
| `region` | Infrastructure | string | — | `"eu-west-1"` |
| `environment` | Infrastructure | enum | `prod \| staging \| dev \| dr` | `"prod"` |

---

## 7. Module 3 — Architecture Artefact Ontology (ART)

### 7.1 OWL Class Hierarchy

```
ArchitecturalConcept
└── Document                    # Root for all architecture documents
    ├── HighLevelDesign         # HLD — system-level architecture
    ├── LowLevelDesign          # LLD — component-level design
    ├── ArchitectureDecisionRecord  # ADR — also extends DEC module's ArchitecturalDecision
    ├── RequestForComments      # RFC — proposal seeking feedback
    ├── RunBook                 # Operational runbook / playbook
    ├── TechnologyRadar         # Tech radar / standards register
    ├── RiskRegister            # Consolidated risk register document
    ├── Standard
    │   ├── TechnologyStandard  # Approved technology choices
    │   └── CodingStandard      # Coding / style standards
    ├── PatternCatalogue        # Approved pattern library
    ├── DataModel               # Data model / schema documentation
    ├── APIContract             # OpenAPI / AsyncAPI contract
    └── SecurityReview          # Security design review / threat model
```

> `ArchitectureDecisionRecord` is both an **artefact** (Document, with source URL, approval date) and a **decision** (ArchitecturalDecision in Module 4, with status, rationale, consequences). In Neo4j, ADR nodes carry labels from both modules.

### 7.2 Object Properties

| Property | Domain | Range | OWL Characteristics | Semantics |
|----------|--------|-------|---------------------|-----------|
| `supersedesDocument` | Document | Document | **Anti-symmetric** | This doc replaces an older version |
| `authoredBy` | Document | Person | — | Primary author |
| `approvedBy` | Document | Person | — | Who approved the document |
| `documentsSystem` | Document | System | — | Which system this document describes |
| `documentsComponent` | Document | Component | — | Which component this document describes |
| `relatesTo` | Document | Document | **Symmetric** | Cross-reference between documents |
| `extractedFrom` | ArchitecturalConcept | Document | — | This knowledge fact was extracted from this doc |

### 7.3 Data Properties

| Property | Domain | Type | Constraints | Example |
|----------|--------|------|-------------|---------|
| `documentType` | Document | enum | `HLD \| LLD \| ADR \| RFC \| RunBook \| Standard \| Radar \| RiskRegister \| Pattern \| DataModel \| APIContract \| SecurityReview`, NOT NULL | `"HLD"` |
| `documentStatus` | Document | enum | `draft \| in-review \| approved \| superseded \| archived`, NOT NULL | `"approved"` |
| `version` | Document | string | — | `"2.1"` |
| `effectiveDate` | Document | date | — | `"2024-06-01"` |
| `expiryDate` | Document | date | — | `"2025-06-01"` |
| `sourceUrl` | Document | string | UNIQUE | `"https://confluence.acme.com/..."` |
| `confidentiality` | Document | enum | `public \| internal \| restricted` | `"internal"` |
| `tags` | Document | list[string] | — | `["payments","kafka","migration"]` |
| `ingestionStatus` | Document | enum | `pending \| in-progress \| complete \| failed` | `"complete"` |
| `lastIngestedAt` | Document | datetime | — | `"2025-04-01T09:00:00Z"` |
| `chunkCount` | Document | integer | — | `14` |

---

## 8. Module 4 — Decision & Pattern Ontology (DEC)

### 8.1 OWL Class Hierarchy

```
ArchitecturalConcept
└── ArchitecturalDecision
    └── ArchitectureDecisionRecord  # Extends Document (ART) — an ADR is both
└── ArchitecturePattern
    ├── [Structural]
    │   ├── Monolith
    │   ├── Microservices
    │   ├── ModularMonolith
    │   └── StranglerFig
    ├── [Integration]
    │   ├── EventDriven
    │   ├── RequestResponse
    │   ├── Choreography
    │   └── Orchestration
    ├── [Data]
    │   ├── CQRS
    │   ├── EventSourcing
    │   └── Saga
    ├── [Infrastructure]
    │   ├── Serverless
    │   ├── ContainerBased
    │   └── ServiceMeshPattern
    └── [Application]
        ├── HexagonalArchitecture
        ├── LayeredArchitecture
        ├── CleanArchitecture
        └── DomainDrivenDesign
└── TechnologyChoice
    ├── TechnologyStandard      # Org-approved / on technology radar
    └── DeprecatedTechnology    # Scheduled for removal
└── TechnologyCategory          # language | framework | database | messaging | observability
└── QualityAttribute
    ├── Scalability
    ├── Reliability
    ├── Security
    ├── Performance
    ├── Maintainability
    ├── Observability
    ├── Availability
    ├── Portability
    ├── Testability
    ├── Deployability
    └── Interoperability
```

### 8.2 Object Properties

| Property | Domain | Range | OWL Characteristics | Semantics |
|----------|--------|-------|---------------------|-----------|
| `addressesQuality` | ArchitecturalDecision \| ArchitecturePattern | QualityAttribute | — | Decision / pattern targets this quality |
| `followsPattern` | System \| Component | ArchitecturePattern | — | Architecture style applied |
| `madeBy` | ArchitecturalDecision | Person | — | Decision author / decision-maker |
| `affects` | ArchitecturalDecision | Component \| System | — | What the decision impacts |
| `supersedes` | ArchitecturalDecision | ArchitecturalDecision | **Anti-symmetric** | New decision replaces old decision |
| `usedBy` | TechnologyChoice | System \| Component | — | Technology is used in this system |
| `categorisedAs` | TechnologyChoice | TechnologyCategory | — | Technology category assignment |
| `replacedBy` | DeprecatedTechnology | TechnologyChoice | — | Migration target technology |

### 8.3 Data Properties

| Property | Domain | Type | Constraints | Example |
|----------|--------|------|-------------|---------|
| `decisionStatus` | ArchitecturalDecision | enum | `proposed \| accepted \| rejected \| deprecated \| superseded`, NOT NULL | `"accepted"` |
| `decisionDate` | ArchitecturalDecision | date | — | `"2024-03-15"` |
| `context` | ArchitecturalDecision | string | — | `"We need to handle..."` |
| `decision` | ArchitecturalDecision | string | NOT NULL | `"We will use Kafka for..."` |
| `consequences` | ArchitecturalDecision | string | — | `"Teams must learn..."` |
| `rationale` | ArchitecturalDecision | string | — | `"Because it gives us..."` |
| `patternCategory` | ArchitecturePattern | enum | `structural \| integration \| data \| infrastructure \| application` | `"integration"` |
| `vendor` | TechnologyChoice | string | — | `"Confluent"` |
| `licenceType` | TechnologyChoice | enum | `open-source \| commercial \| proprietary \| freemium` | `"open-source"` |
| `maturityLevel` | TechnologyChoice | enum | `emerging \| trial \| adopted \| hold` | `"adopted"` |
| `endOfSupportDate` | TechnologyChoice | date | — | `"2027-12-31"` |
| `targetValue` | QualityAttribute | string | — | `"p99 < 200ms"` |
| `measurementMethod` | QualityAttribute | string | — | `"APM traces via Datadog"` |

---

## 9. Module 5 — Governance & Risk Ontology (GOV)

### 9.1 OWL Class Hierarchy

```
ArchitecturalConcept
└── Risk
    ├── TechnicalRisk           # Scalability, reliability, performance risk
    ├── SecurityRisk            # Attack surface, data exposure, auth weakness
    ├── ComplianceRisk          # Regulatory / policy violation
    └── OperationalRisk         # Deployment, operational stability risk
└── Constraint
    ├── RegulatoryConstraint    # GDPR, PCI-DSS, FCA, SOX
    ├── TechnicalConstraint     # Latency SLA, resource limits, compatibility
    └── BudgetConstraint        # Cost ceiling, licensing cap
└── Assumption                  # Stated assumption in a design document
└── Requirement
    ├── FunctionalRequirement
    └── NonFunctionalRequirement
└── Capability
    ├── BusinessCapability      # e.g. "Process Payment", "Manage Identity"
    └── TechnicalCapability     # e.g. "Horizontal Scaling", "Multi-Region HA"
└── Domain                      # Business domain: Payments | Identity | Lending | Orders
└── BusinessProcess             # Process the architecture supports
└── SecurityControl             # WAF | mTLS | OAuth2 | MFA | Encryption at Rest
└── Compliance                  # Compliance framework: PCI-DSS | GDPR | SOC2 | ISO27001
└── UnresolvedConcept           # Review queue — extracted concept not yet mapped to ontology
└── OntologyChangeRequest       # Governance artefact for proposing ontology additions
```

### 9.2 Object Properties

| Property | Domain | Range | OWL Characteristics | Semantics |
|----------|--------|-------|---------------------|-----------|
| `mitigates` | Component \| Pattern \| SecurityControl | Risk | — | Architecture choice reduces this risk |
| `satisfies` | Component \| System | Requirement | — | Component fulfils this requirement |
| `complianceWith` | System \| Component | Constraint \| Compliance | — | System adheres to this constraint |
| `belongsToDomain` | System \| Component | Domain | — | Business domain ownership |
| `implementsCapability` | Component \| System | Capability | — | Component delivers this capability |
| `supportsProcess` | System \| Component | BusinessProcess | — | System enables this business process |
| `appliesControl` | SecurityControl | Component \| System | — | Security control is applied to system |
| `replacedBy` | DeprecatedComponent | Component | — | Migration target component |
| `raisedBy` | Risk \| Assumption | Person | — | Who identified this risk / assumption |
| `constrainedBy` | System \| Component | Constraint | — | System must respect this constraint |
| `ownedBy` | Domain \| Capability | Team | — | Domain / capability accountability |
| `partOf` | BusinessCapability | BusinessCapability | **Transitive** | Capability hierarchy (sub-capabilities) |

### 9.3 Data Properties

| Property | Domain | Type | Constraints | Example |
|----------|--------|------|-------------|---------|
| `riskLevel` | Risk | enum | `low \| medium \| high \| critical`, NOT NULL | `"high"` |
| `likelihood` | Risk | enum | `unlikely \| possible \| likely \| certain` | `"possible"` |
| `impact` | Risk | enum | `low \| medium \| high \| critical` | `"high"` |
| `riskStatus` | Risk | enum | `open \| mitigated \| accepted \| closed` | `"open"` |
| `riskId` | Risk | string | UNIQUE | `"RISK-2024-012"` |
| `constraintType` | Constraint | string | — | `"Data residency"` |
| `regulatoryBody` | RegulatoryConstraint | string | — | `"FCA"` |
| `enforcementDate` | Constraint | date | — | `"2024-09-01"` |
| `validUntil` | Assumption | date | — | `"2025-12-31"` |
| `validatedBy` | Assumption | string | — | `"jane@acme.com"` |
| `requirementId` | Requirement | string | UNIQUE | `"REQ-FUNC-001"` |
| `priority` | Requirement | enum | `must \| should \| could \| wont` (MoSCoW) | `"must"` |
| `requirementSource` | Requirement | string | — | `"Product brief v2.3"` |
| `capabilityLevel` | Capability | enum | `strategic \| core \| support` | `"core"` |
| `maturityScore` | Capability | integer | 1–5 | `3` |
| `controlFramework` | SecurityControl | string | — | `"NIST CSF"` |
| `controlId` | SecurityControl | string | — | `"PR.AC-1"` |

---

## 10. Object Properties — Cross-Module Index

Complete inventory of all 30 object properties across the five modules:

| Property | From Module | Domain | Range | OWL Axioms |
|----------|------------|--------|-------|------------|
| `partOf` | ORG | Team \| Lab \| Platform \| BusinessCapability | Lab \| Platform \| Division \| BusinessCapability | **Transitive** |
| `owns` | ORG | Team | System \| Component | Inv: `ownedBy` |
| `ledBy` | ORG | Team | Person | **Functional** |
| `memberOf` | ORG | Person | Team | — |
| `reportsTo` | ORG | Team | OrganisationUnit | — |
| `belongsTo` | SYS | Component | System | Inv: `composedOf` |
| `composedOf` | SYS | System | Component | Inv: `belongsTo` |
| `dependsOn` | SYS | Component | Component | **Transitive** |
| `exposesAPI` | SYS | Service | Component | — |
| `consumesAPI` | SYS | Component | Service | — |
| `storesDataIn` | SYS | Service | Database | — |
| `publishesTo` | SYS | Service | MessageBroker | — |
| `subscribesTo` | SYS | Service | MessageBroker | — |
| `deployedOn` | SYS | Component | Infrastructure | — |
| `hostedOn` | SYS | System | Infrastructure | — |
| `ownedBy` | SYS/ORG | Component \| System \| Domain \| Capability | Team | Inv: `owns` |
| `supersedesDocument` | ART | Document | Document | **Anti-symmetric** |
| `authoredBy` | ART | Document | Person | — |
| `approvedBy` | ART | Document | Person | — |
| `documentsSystem` | ART | Document | System | — |
| `documentsComponent` | ART | Document | Component | — |
| `relatesTo` | ART | Document | Document | **Symmetric** |
| `extractedFrom` | ART | ArchitecturalConcept | Document | — |
| `addressesQuality` | DEC | ArchitecturalDecision \| ArchitecturePattern | QualityAttribute | — |
| `followsPattern` | DEC | System \| Component | ArchitecturePattern | — |
| `madeBy` | DEC | ArchitecturalDecision | Person | — |
| `affects` | DEC | ArchitecturalDecision | Component \| System | — |
| `supersedes` | DEC | ArchitecturalDecision | ArchitecturalDecision | **Anti-symmetric** |
| `usedBy` | DEC | TechnologyChoice | System \| Component | — |
| `categorisedAs` | DEC | TechnologyChoice | TechnologyCategory | — |
| `replacedBy` | DEC/GOV | DeprecatedTechnology \| DeprecatedComponent | TechnologyChoice \| Component | — |
| `mitigates` | GOV | Component \| Pattern \| SecurityControl | Risk | — |
| `satisfies` | GOV | Component \| System | Requirement | — |
| `complianceWith` | GOV | System \| Component | Constraint \| Compliance | — |
| `belongsToDomain` | GOV | System \| Component | Domain | — |
| `implementsCapability` | GOV | Component \| System | Capability | — |
| `supportsProcess` | GOV | System \| Component | BusinessProcess | — |
| `appliesControl` | GOV | SecurityControl | Component \| System | — |
| `raisedBy` | GOV | Risk \| Assumption | Person | — |
| `constrainedBy` | GOV | System \| Component | Constraint | — |

---

## 11. Ontology Rules & Constraints

### 11.1 OWL Axioms

**Transitive properties** — reasoners can infer indirect relationships:
- `partOf`: Team → Lab → Platform → Division (team is transitively part of its division across all 4 levels)
- `dependsOn`: A → B → C implies A indirectly depends on C (full dependency tree)
- `partOf` (Capability hierarchy): sub-capabilities compose into parent capabilities

**Functional properties** — single-valued (at most one value):
- `ledBy`: a Team has exactly one lead Person
- `hasName`: an entity has exactly one name

**Inverse pairs** — asserting one direction asserts the other:
- `belongsTo` ↔ `composedOf`
- `owns` ↔ `ownedBy`
- `memberOf` ↔ `hasMember` *(implied inverse)*

**Anti-symmetric properties** — cannot hold in both directions:
- `supersedesDocument`: if A supersedes B, B cannot supersede A
- `supersedes` (decision): same constraint

**Disjoint classes** — no individual can be an instance of both:
- `{Division, Team, Person}` — no OrganisationUnit is simultaneously a Division and a Team
- `{System, Component, Infrastructure}` — systems contain components; they are different things
- `{Document, ArchitecturePattern, QualityAttribute}` — artefacts, patterns, and attributes are distinct

**Cardinality restrictions:**
- `Team` — exactly 1 `partOf` a Lab (or Platform/Division for enabling teams that skip the Lab level)
- `Lab` — exactly 1 `partOf` a Platform
- `Platform` — exactly 1 `partOf` a Division
- `ArchitecturalDecision` — exactly 1 `decisionStatus` data property
- `Component` — min 1 `ownedBy` Team (every component has an owner)
- `System` — min 1 `belongsToDomain` Domain (every system maps to a domain)
- `Risk` with `riskLevel='critical'` — min 1 `mitigates` relationship (critical risks must be mitigated)

### 11.2 Neo4j Schema Constraints (Cypher)

**Uniqueness constraints:**
```cypher
CREATE CONSTRAINT org_unit_name_unique IF NOT EXISTS
  FOR (n:OrganisationUnit) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT system_id_unique IF NOT EXISTS
  FOR (n:System) REQUIRE n.systemId IS UNIQUE;

CREATE CONSTRAINT document_url_unique IF NOT EXISTS
  FOR (n:Document) REQUIRE n.sourceUrl IS UNIQUE;

CREATE CONSTRAINT person_email_unique IF NOT EXISTS
  FOR (n:Person) REQUIRE n.email IS UNIQUE;

CREATE CONSTRAINT risk_id_unique IF NOT EXISTS
  FOR (n:Risk) REQUIRE n.riskId IS UNIQUE;

CREATE CONSTRAINT requirement_id_unique IF NOT EXISTS
  FOR (n:Requirement) REQUIRE n.requirementId IS UNIQUE;
```

**Existence (NOT NULL) constraints:**
```cypher
CREATE CONSTRAINT component_name_exists IF NOT EXISTS
  FOR (n:Component) REQUIRE n.name IS NOT NULL;

CREATE CONSTRAINT document_type_exists IF NOT EXISTS
  FOR (n:Document) REQUIRE n.documentType IS NOT NULL;

CREATE CONSTRAINT document_status_exists IF NOT EXISTS
  FOR (n:Document) REQUIRE n.documentStatus IS NOT NULL;

CREATE CONSTRAINT decision_status_exists IF NOT EXISTS
  FOR (n:ArchitecturalDecision) REQUIRE n.decisionStatus IS NOT NULL;

CREATE CONSTRAINT risk_level_exists IF NOT EXISTS
  FOR (n:Risk) REQUIRE n.riskLevel IS NOT NULL;

CREATE CONSTRAINT team_name_exists IF NOT EXISTS
  FOR (n:Team) REQUIRE n.name IS NOT NULL;
```

**Performance indexes:**
```cypher
CREATE INDEX component_name_idx IF NOT EXISTS
  FOR (n:Component) ON (n.name);

CREATE INDEX system_domain_idx IF NOT EXISTS
  FOR (n:System) ON (n.systemId);

CREATE INDEX document_status_idx IF NOT EXISTS
  FOR (n:Document) ON (n.documentStatus);

CREATE INDEX risk_level_idx IF NOT EXISTS
  FOR (n:Risk) ON (n.riskLevel);

CREATE FULLTEXT INDEX concept_search IF NOT EXISTS
  FOR (n:ArchitecturalConcept) ON EACH [n.name, n.description];
```

### 11.3 Application-Layer Validation Rules

These run in the ingestion pipeline *before* any write to Neo4j. Violations do not block the whole document — they route the affected entity to the review queue.

| # | Rule | Trigger | Action on Violation |
|---|------|---------|---------------------|
| R1 | A `Document` with `documentStatus='approved'` cannot be deleted | DELETE attempt | Reject — must transition to `superseded` instead |
| R2 | A `Component` cannot `dependsOn` itself | Relationship write | Reject self-loop with error |
| R3 | An `ArchitecturalDecision` with `decisionStatus='accepted'` must have ≥1 `addressesQuality` edge | Status → accepted | Block acceptance until QualityAttribute is linked |
| R4 | A `DeprecatedComponent` must have a `replacedBy` edge | Node creation | Warn immediately; hard block after 30-day grace period |
| R5 | A `Risk` with `riskLevel='critical'` must have ≥1 `mitigates` edge | Risk creation | Flag for immediate architecture governance review |
| R6 | Every `Component` must have exactly 1 `ownedBy` Team | Nightly validation | Report orphaned components |
| R7 | Every `System` must have ≥1 `belongsToDomain` Domain | System creation | Warn; add to review queue |
| R8 | `decisionStatus` transitions are one-directional: `proposed → accepted/rejected`; `accepted → deprecated/superseded` | Status update | Reject illegal state transitions |
| R9 | LLM ontology class mapping confidence < 0.5 | Entity extraction | Route entity to `UnresolvedConcept` queue; do not write to main graph |
| R10 | Entity name similarity against existing graph: >0.85 → auto-merge; 0.5–0.85 → human review; <0.5 → new node | Entity creation | Apply per confidence band |

---

## 12. Graph Model Patterns

### 12.1 Document Provenance Pattern

Every fact extracted from a document carries a back-link:

```cypher
(OrderService:Component {name: 'Order Service'})
  -[:EXTRACTED_FROM {confidence: 0.92, chunk: 3}]->
(doc:Document {name: 'Order Domain HLD v2', documentType: 'HLD', effectiveDate: '2024-06-01'})
```

Query: *"Where did this fact come from?"* or *"Which documents mention this component?"*

### 12.2 Temporal / Versioning Pattern

```cypher
(hld_v2:Document)-[:SUPERSEDES_DOCUMENT]->(hld_v1:Document)
(adr_new:ArchitecturalDecision)-[:SUPERSEDES]->(adr_old:ArchitecturalDecision)
```

Query: *"What was the architecture of the Order domain before the 2024 migration?"*

### 12.3 Decision Impact Pattern

```cypher
(adr:ArchitecturalDecision)-[:AFFECTS]->(c:Component)
(adr)-[:ADDRESSES_QUALITY]->(qa:QualityAttribute)
(adr)-[:MADE_BY]->(p:Person)
```

Query: *"Which ADRs affect the Payment Service and what quality attributes do they target?"*

### 12.4 Domain / Capability / Team Map

```cypher
(c:Component)-[:IMPLEMENTS_CAPABILITY]->(cap:Capability)
(cap)-[:BELONGS_TO_DOMAIN]->(d:Domain)     ← not yet — Domain ownedBy Team
(d:Domain)-[:OWNED_BY]->(t:Team)
```

Query: *"Which teams own components that implement the Identity Management capability?"*

### 12.5 Organisation Ownership Chain

```cypher
// 4-level hierarchy: Team → Lab → Platform → Division
(t:Team)-[:PART_OF]->(l:Lab)-[:PART_OF]->(p:Platform)-[:PART_OF]->(d:Division)
(t)-[:OWNS]->(s:System)-[:COMPOSED_OF]->(c:Component)

// Transitive query — find all teams in BCB Division regardless of depth
MATCH (t:Team)-[:PART_OF*]->(d:Division {name: 'Business & Commercial Banking'})
RETURN t.name
```

Query: *"Which systems does the BCB Division own?"* (answered via transitive `partOf` across all 4 levels)

---

## 13. What We Have vs What Remains

| Layer | Status | Notes |
|---|---|---|
| **Ontology — Schema (TBox)** | | |
| Core ontology v1 (38 classes, owlready2) | ✅ Done | Single-module — being replaced by 5-module design |
| 5-module ontology design (this document) | ✅ Designed | Implement in Python after YAML review |
| ORG module YAML (`ontology/modules/org.yaml`) | ✅ Done | 4-level hierarchy: Division→Platform→Lab→Team |
| SYS module YAML (`ontology/modules/sys.yaml`) | ✅ Done | System, Component, Infrastructure hierarchy |
| ART module YAML (`ontology/modules/art.yaml`) | ✅ Done | Document subtypes, ADR dual-module node |
| DEC module YAML (`ontology/modules/dec.yaml`) | ✅ Done | Pattern, QA, TechnologyChoice, ArchitecturalDecision |
| GOV module YAML (`ontology/modules/gov.yaml`) | ✅ Done | Risk, Constraint, Capability, Domain, SecurityControl |
| Python implementation (owlready2 per module) | ❌ Not started | After YAML review/sign-off |
| **Ontology — Instance Data (ABox)** | | |
| BCB division instance data (`ontology/instances/org_bcb.yaml`) | ✅ Done | Platforms, Labs, Teams for BCB |
| Retail division instance data (`ontology/instances/org_retail.yaml`) | 🔄 Template only | Platforms/Labs to be filled in |
| Group enabling functions (`ontology/instances/org_group.yaml`) | ✅ Done | Architecture, Cloud, Security, DX teams |
| Other divisions (IP&P, etc.) | ❌ Not started | Copy `org_retail.yaml` template |
| **Graph & Storage** | | |
| Neo4j running + basic schema | ✅ Done | Constraints + indexes from §11.2 to add |
| Sample data loaded | ✅ Done | Needs refresh against new schema |
| Neo4j constraints + indexes (§11.2) | ❌ Not applied | Cypher scripts ready in design doc |
| **Query & Interface** | | |
| NL→Cypher Q&A CLI | ✅ Done | Works on current sample data |
| Chat web UI (FastAPI + SSE) | ✅ Done | — |
| Q&A agent schema introspection | 🔄 Needs update | Must reflect 5-module label set |
| **Ingestion** | | |
| Document ingestion pipeline | ❌ Not started | Core Phase 3 build |
| LLM entity extraction with ontology mapping | ❌ Not started | Structured output + validation |
| Ontology validator (pre-Neo4j write) | ❌ Not started | Application-layer rules R1–R10 |
| Deduplication / fuzzy merge | ❌ Not started | Name matching against graph |
| UnresolvedConcept review queue | ❌ Not started | Simple UI or CSV export |
| Instance data loader (`ingestion/load_org_instances.py`) | ❌ Not started | Load `ontology/instances/*.yaml` into Neo4j |
| **Source Connectors** | | |
| Confluence API connector | ❌ Not started | Requires API token |
| SharePoint connector | ❌ Not started | Requires Graph API access |
| Git/Markdown ADR scanner | ❌ Not started | Low effort — high value |
| PDF / DOCX loader | ❌ Not started | `pypdf`, `python-docx` |
| **Search & Retrieval** | | |
| Embedding + vector search | ❌ Not started | `nomic-embed-text` via Ollama |
| Hybrid Cypher + semantic retrieval | ❌ Not started | GraphRAG pattern |
| **Governance & Operations** | | |
| Ontology change request workflow | ❌ Not started | Git PR process |
| Ingestion audit log | ❌ Not started | `OntologyChangeRequest` node |
| Data quality dashboard | ❌ Not started | Orphan components, unresolved concepts |

---

## 14. Technology Choices

| Component | Choice | Rationale |
|---|---|---|
| Ontology definition | owlready2 (Python) | Code-first, version-controlled, no GUI required |
| Graph database | Neo4j | Native graph, Cypher, mature ecosystem |
| LLM (extraction + Q&A) | Ollama (local) | No data leaves the org; model swap is trivial |
| Embedding model | `nomic-embed-text` (Ollama) | Already installed, good quality, local |
| Ingestion framework | Python + LangChain | Already in stack |
| Document parsing | `pypdf`, `python-docx`, `markdownify` | Lightweight, no cloud dependency |
| Web UI | FastAPI + vanilla JS | Zero frontend build tooling |
| Source connectors | Confluence REST API, SharePoint Graph API | Standard enterprise APIs |

---

## 15. Open Questions for Review

1. **Ontology governance:** Who approves ontology changes? Architecture review board? Single architect?
2. **Confidentiality:** How do we handle restricted documents? Node-level security in Neo4j Enterprise, or filter at application layer?
3. **Document sources:** Confluence and SharePoint — do we have API access? Is there an existing search index we can tap?
4. **Deduplication threshold:** 0.85 confidence for auto-merge — is this too aggressive or too conservative?
5. **Embedding search vs Cypher:** For some questions, semantic similarity over document chunks may give better results than graph traversal. Do we want a hybrid retrieval (GraphRAG)?
6. **Multi-tenancy:** Single graph for the whole organisation, or per-domain sub-graphs?
7. **Historical data:** How far back do we ingest? All documents, or only approved/current?
8. **Review queue:** Who processes `UnresolvedConcept` flags, and how quickly must they be resolved?

---

## 16. Proposed Implementation Phases

### Phase 1 — Foundation ✅ (Complete)
- Core ontology (single-module), Neo4j, NL Q&A CLI, Chat Web UI

### Phase 2 — 5-Module Ontology Implementation (Next)
- Refactor `architecture_ontology.py` into 5 module files (`org.py`, `sys.py`, `art.py`, `dec.py`, `gov.py`)
- Implement all classes, object properties, and data properties per this design
- Apply Neo4j schema constraints and indexes from §11.2
- Refresh sample data to exercise all 5 modules (sample Division → Platform → Team → System → Component → ADR → Risk chain)
- Update Q&A agent schema introspection to handle all labels

### Phase 3 — Document Ingestion Pipeline
- PDF / DOCX / Markdown document loader
- LLM entity extraction with ontology-mapped structured output
- Application-layer validation rules R1–R10
- Fuzzy deduplication / merge logic
- `UnresolvedConcept` review queue

### Phase 4 — Source Connectors
- Git/Markdown ADR scanner (lowest effort)
- Confluence REST API connector
- PDF upload endpoint (to existing FastAPI server)
- SharePoint connector (requires Graph API access)

### Phase 5 — Semantic Search + Hybrid Retrieval
- Embed document chunks with `nomic-embed-text` (Ollama, already installed)
- Store vectors alongside graph nodes (Neo4j vector index)
- Hybrid query: Cypher for structured facts + vector similarity for document excerpts

### Phase 6 — Governance & Operations
- Ontology change request workflow (Git PR process + `OntologyChangeRequest` nodes)
- Ingestion audit log
- Data quality dashboard (orphaned components, unresolved concepts, stale documents)
- Role-based access control (application layer)
