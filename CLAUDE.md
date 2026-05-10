# Enterprise Architecture Knowledge Graph — CLAUDE.md

## Project Vision
A queryable knowledge graph capturing the full body of enterprise and solution architecture knowledge (documents, decisions, patterns, components, systems, teams) across all generations. Users ask architecture questions in plain English and get answers grounded in real documentation.

**Source repo:** `ontology_poc/` (the working codebase — this folder is the new home once Phase 2 begins)

---

## Semantic Knowledge Pipeline

This project builds knowledge in six progressive layers. Every layer below depends on the one above it:

1. **Controlled Vocabulary** — Foundation of all semantic knowledge. Reconciles synonyms (e.g. "microservice" = "micro-service" = "service"), clarifies ambiguous terms, and establishes the canonical names used throughout the ontology.

2. **Metadata Standards** — Schema-based control over how knowledge is described. Covers structural metadata (what type of thing is this?), descriptive metadata (what does it do?), and administrative metadata (who owns it, when was it approved?).

3. **Taxonomy** — Structures the controlled vocabulary into a hierarchy using parent–child relations. Example: `Component → Service → Microservice`. Enables inheritance and classification queries.

4. **Thesaurus** — Extends the taxonomy by reconciling synonyms and related terms across the hierarchy. Allows the system to understand that "BFF" and "BackendForFrontend" refer to the same concept.

5. **Ontology** — Introduces logical reasoning. Defines classes, relations (object properties), data properties, and OWL axioms (transitive, functional, inverse, disjoint). The ontology *validates* — it rejects knowledge that doesn't conform to the schema.

6. **Knowledge Graph** — The complete realisation of all pipeline stages in Neo4j. Provides a visual and queryable representation of all semantic relations across the enterprise architecture corpus.

---

## Architecture Principles (Non-Negotiable)

- **Ontology-first:** Schema is defined before ingestion. Documents are mapped *to* the ontology, never the other way around.
- **Ontology stability:** The ontology evolves deliberately via a governance process. Individual documents do not trigger ad-hoc schema changes.
- **Documents are evidence:** Source docs are stored as `Document` nodes with provenance metadata; extracted knowledge links back via `EXTRACTED_FROM` edges.
- **LLM assists, ontology governs:** LLMs extract and classify; the ontology validates and rejects. Humans review ambiguous extractions.
- **Graph as single source of truth:** Neo4j is the canonical knowledge store. All tools (Q&A, dashboards) read from the graph.

---

## Codebase Structure

```
ontology_poc/                        ← working codebase
├── ontology/
│   ├── architecture_ontology.py     ← Phase 1 monolithic ontology (being replaced)
│   ├── modules/                     ← Phase 2: 5 YAML module definitions (all Done)
│   │   ├── org.yaml                 ← Organisation module
│   │   ├── sys.yaml                 ← System & Platform module
│   │   ├── art.yaml                 ← Architecture Artefact module
│   │   ├── dec.yaml                 ← Decision & Pattern module
│   │   └── gov.yaml                 ← Governance & Risk module
│   └── instances/                   ← ABox (instance data, not schema)
│       ├── org_bcb.yaml             ← BCB division teams/labs/platforms (Done)
│       ├── org_group.yaml           ← Group enabling teams (Done)
│       └── org_retail.yaml          ← Retail division (template only)
├── ingestion/
│   └── load_ontology.py             ← Loads ontology into Neo4j
├── interaction/
│   ├── qa_agent.py                  ← NL→Cypher Q&A agent (Done)
│   ├── server.py                    ← FastAPI + SSE server (Done)
│   └── chat.html                    ← Web UI (Done)
├── data/
│   ├── architecture.owl             ← OWL export
│   └── architecture.ttl             ← Turtle RDF export
└── docs/
    ├── DESIGN.md                    ← Full design document (source of truth)
    └── architecture.drawio          ← Architecture diagram
```

---

## 5-Module Ontology Design

The ontology is split into five modules with a strict dependency order: ORG → SYS → ART → DEC → GOV.

| Module | Prefix | Key Classes |
|--------|--------|-------------|
| Organisation (ORG) | `#org` | Division, Platform, Lab, Team, Person |
| System & Platform (SYS) | `#sys` | System, Component, Service, Database, Infrastructure |
| Architecture Artefact (ART) | `#art` | Document, HLD, LLD, ADR, RFC, RunBook, Standard |
| Decision & Pattern (DEC) | `#dec` | ArchitecturalDecision, ArchitecturePattern, QualityAttribute, TechnologyChoice |
| Governance & Risk (GOV) | `#gov` | Risk, Constraint, Capability, Domain, SecurityControl, UnresolvedConcept |

**Organisation hierarchy (4 levels):** Division → Platform → Lab → Team. The `partOf` relation is **transitive** — queries for "all teams in BCB" traverse all 4 levels automatically.

**A node can carry labels from multiple modules.** An ADR node is simultaneously `(:ADR:Document:ArchitecturalDecision)` — it spans ART and DEC.

### Key OWL Axioms to preserve
- **Transitive:** `partOf` (org chain), `dependsOn` (component dependencies), `partOf` (capability hierarchy)
- **Functional:** `ledBy` (a Team has exactly one lead)
- **Inverse pairs:** `belongsTo` ↔ `composedOf`, `owns` ↔ `ownedBy`
- **Anti-symmetric:** `supersedesDocument`, `supersedes` (decisions)
- **Disjoint:** `{Division, Team, Person}`, `{System, Component, Infrastructure}`, `{Document, ArchitecturePattern, QualityAttribute}`

---

## Unknown Concepts During Ingestion

When the LLM extracts something not in the ontology:
- **Auto:** Map to nearest superclass (safe default) + tag with freetext
- **Queue:** Create `UnresolvedConcept` node for human review
- **Never:** Change the ontology at ingestion time

Confidence thresholds: `>0.85` auto-merge with existing node | `0.5–0.85` human review | `<0.5` new node created | `<0.5` LLM confidence → route to `UnresolvedConcept`, do not write to main graph.

---

## Technology Stack

| Component | Choice |
|-----------|--------|
| Ontology definition | `owlready2` (Python, code-first) |
| Graph database | Neo4j (local) |
| LLM (extraction + Q&A) | Ollama (local — no data leaves org) |
| Embedding model | `nomic-embed-text` via Ollama |
| Ingestion framework | Python + LangChain |
| Document parsing | `pypdf`, `python-docx`, `markdownify` |
| Web UI | FastAPI + vanilla JS (SSE for streaming) |
| Source connectors | Confluence REST API, SharePoint Graph API (not started) |

---

## Implementation Status

| Phase | Status |
|-------|--------|
| Phase 1 — Core ontology, Neo4j, NL Q&A CLI, Chat Web UI | ✅ Complete |
| Phase 2 — 5-Module Python implementation + Neo4j constraints | 🔄 Next (YAML Done, Python not started) |
| Phase 3 — Document ingestion pipeline + validation rules R1–R10 | ❌ Not started |
| Phase 4 — Source connectors (Git ADR, Confluence, SharePoint, PDF) | ❌ Not started |
| Phase 5 — Semantic search + hybrid GraphRAG retrieval | ❌ Not started |
| Phase 6 — Governance, audit log, data quality dashboard | ❌ Not started |

**Current focus: Phase 2.** Refactor `architecture_ontology.py` into 5 module files (`org.py`, `sys.py`, `art.py`, `dec.py`, `gov.py`), apply Neo4j constraints/indexes from DESIGN.md §11.2, and refresh sample data.

---

## Coding Conventions

- Python 3.12, owlready2 for ontology, neo4j Python driver for graph writes
- Module files live in `ontology/modules/` (YAML schema) and will have matching `ontology/modules/*.py` (owlready2 implementation)
- Instance data (ABox) lives in `ontology/instances/*.yaml` — never hardcoded in Python
- All Neo4j writes go through the ingestion layer — never direct writes from the Q&A agent
- Application-layer validation rules R1–R10 (see DESIGN.md §11.3) run before any Neo4j write
- Ontology changes must be versioned in git and accompanied by a migration script (additive only — no destructive changes)

---

## Key Files to Know

- `docs/DESIGN.md` — complete design spec (classes, properties, Cypher constraints, validation rules, phases)
- `ontology/architecture_ontology.py` — Phase 1 monolithic ontology being replaced
- `ontology/modules/*.yaml` — authoritative schema definitions for all 5 modules
- `interaction/qa_agent.py` — NL→Cypher agent (needs schema update for 5-module label set)
- `ingestion/load_ontology.py` — Neo4j loader

---

## Do Not

- Add ontology classes or properties without updating the relevant `ontology/modules/*.yaml` first
- Write instance data (specific teams, systems, ADRs) into module Python files — put it in `ontology/instances/`
- Change `decisionStatus` backward (`accepted` cannot go back to `proposed`)
- Delete approved Documents — transition to `superseded` instead
- Run LLM-extracted entities directly into Neo4j without the validation pipeline
