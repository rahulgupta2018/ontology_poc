# Ontology Modules — YAML Format Guide

This directory contains the **human-readable brainstorming format** for the enterprise architecture knowledge graph ontology.

The five YAML files define the ontology **before** any Python code is written. They are the primary artefacts for discussion, review, and iteration with architects and domain experts. Once a module's YAML is reviewed and agreed, it is translated into Python (`owlready2`) and loaded into Neo4j.

---

## Files in This Directory

| File | Module ID | Description |
|---|---|---|
| [org.yaml](org.yaml) | ORG | Organisation — teams, people, reporting structure |
| [sys.yaml](sys.yaml) | SYS | Systems, components, and infrastructure |
| [art.yaml](art.yaml) | ART | Architecture artefacts — documents, ADRs, standards |
| [dec.yaml](dec.yaml) | DEC | Decisions, patterns, quality attributes, technology choices |
| [gov.yaml](gov.yaml) | GOV | Governance — risks, constraints, requirements, capabilities, domains |

All five modules load into **one unified Neo4j graph**. A node can carry labels from multiple modules (e.g. an ADR is both a Document from ART and an ArchitecturalDecision from DEC). Cross-module relationships are traversed naturally in Cypher.

---

## YAML Schema Reference

Each YAML file has six top-level sections:

```
module:          ← Module identity and metadata
classes:         ← Class hierarchy (nestable)
object_properties:  ← Relationships between nodes
data_properties:    ← Node attributes
constraints:     ← Neo4j constraints and application rules
open_questions:  ← Design decisions not yet resolved
```

---

### `module:` — Module Metadata

```yaml
module:
  id: ORG                        # Short module code (ORG | SYS | ART | DEC | GOV)
  name: Organisation Ontology    # Human name
  namespace: "http://acme.org/ontology#org"
  version: "0.1-draft"
  status: draft                  # draft | in-review | approved
  notes: >
    Free text description of what this module covers and why it exists.
```

---

### `classes:` — Class Hierarchy

Classes are the node types in the graph. They nest to express inheritance.

```yaml
classes:

  - name: OrganisationUnit
    description: "Base class for all organisational groupings."
    notes: >
      Optional longer notes — design rationale, things to be aware of.
    subclasses:

      - name: Division
        description: "Top-level business division."
        subclasses:

          - name: Platform
            description: "A product platform within a division."
```

**Rules:**
- `name` — PascalCase. Must be unique across all five modules.
- `description` — One sentence. What is an instance of this class?
- `notes` — Optional. Design rationale, cross-module links, things to watch.
- `subclasses` — Optional nested list. Depth is unlimited.
- A subclass **inherits all properties** of its parent class.

---

### `object_properties:` — Relationships Between Nodes

```yaml
object_properties:

  - name: partOf
    description: "A Team is part of a Platform or Division."
    domain: [Team]               # List of classes that are the SOURCE of this relationship
    range: [Platform, Division]  # List of classes that are the TARGET
    owl_axioms:
      - transitive: true         # partOf is transitive
      - functional: true         # A node can have only one value (single-valued)
      - inverse_of: hasMember    # Names the inverse relationship
      - anti_symmetric: true     # If A→B then B cannot→A (e.g. supersedes)
      - symmetric: true          # A→B implies B→A (e.g. relatesTo)
    notes: "Optional design notes."
```

**OWL Axioms supported:**

| Axiom | Meaning |
|---|---|
| `transitive: true` | If A→B and B→C, then A→C |
| `functional: true` | Each source node can have at most one value via this property |
| `inverse_functional: true` | Each target node can have at most one source |
| `anti_symmetric: true` | If A→B, then B cannot→A |
| `symmetric: true` | A→B implies B→A |
| `inverse_of: name` | Names the inverse relationship |

---

### `data_properties:` — Node Attributes

```yaml
data_properties:

  - name: teamType
    domain: [Team]               # Which class(es) this property applies to
    type: string                 # string | integer | float | boolean | date | list[string] | list[integer]
    enum:                        # Optional fixed set of allowed values
      - stream-aligned
      - platform
      - enabling
      - complicated-subsystem
    constraints:
      - NOT NULL                 # This property must always have a value
      - UNIQUE                   # Must be unique across all nodes of this type
    example: "platform"         # A realistic example value
    notes: "Optional design notes."
```

**Supported types:**

| Type | Example value |
|---|---|
| `string` | `"active"` |
| `integer` | `42` |
| `float` | `3.14` |
| `boolean` | `true` |
| `date` | `"2024-03-15"` |
| `list[string]` | `["prod", "staging"]` |
| `list[integer]` | `[200, 404, 500]` |

---

### `constraints:` — Neo4j Constraints and Application Rules

Two types of constraint are recorded here:

**Graph-level constraints** — enforced by Neo4j:
```yaml
constraints:
  - id: C1
    type: uniqueness       # uniqueness | existence | node_key
    label: System          # The Neo4j label
    property: systemId     # The property being constrained
    cypher: "CREATE CONSTRAINT ..."   # The Cypher to apply it
```

**Application-layer constraints** — enforced by validation code:
```yaml
  - id: I1
    type: application_layer
    description: "Every System must belong to exactly one Domain."
    validation: >
      MATCH (s:System)
      WHERE NOT EXISTS { (s)-[:BELONGS_TO_DOMAIN]->(:Domain) }
      RETURN s.name AS systemWithoutDomain
```

**Index definitions:**
```yaml
  - id: I2
    type: fulltext_index
    labels: [System, Component]
    properties: [name, description]
    cypher: "CREATE FULLTEXT INDEX ..."
```

---

### `open_questions:` — Unresolved Design Decisions

```yaml
open_questions:
  - id: OQ-ORG-1                # Unique ID: OQ-{MODULE}-{NUMBER}
    question: >
      Should there be a root 'Enterprise' node above Division?
    options:
      - "Yes — makes cross-division traversal queries simpler"
      - "No — add a flag to Division to mark the top-level"
    recommended: "Yes — a single Enterprise root keeps the graph clean"
    status: open               # open | in-review | resolved
    resolution: ""             # Fill when resolved
```

Open questions are intentional — they capture the decisions we haven't made yet. Do not resolve them by guessing; discuss with the relevant domain expert.

---

## How to Use These Files

### Reviewing an Existing Module

1. Read the `module.notes` to understand the purpose.
2. Walk the `classes` hierarchy — does the nesting reflect how the organisation thinks?
3. Review `object_properties` — do the `domain` and `range` make sense?
4. Review `data_properties` — are the enums complete? Are constraints correct?
5. Review `open_questions` — can you answer any of them?

### Proposing a Change

Edit the YAML directly. You do not need to understand Python or Neo4j to propose:
- A new class (add a `- name:` entry under the right parent)
- A new property (add a `- name:` entry in `data_properties`)
- A new relationship (add to `object_properties`)
- A design question (add to `open_questions`)

**Do not rename classes** without checking whether they are referenced by other modules (the cross-module reference comments at the top of each file list these).

### Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Class name | PascalCase | `StreamAlignedTeam` |
| Property name | camelCase | `teamType`, `riskLevel` |
| Enum value | kebab-case | `stream-aligned`, `in-review` |
| Constraint ID | `C` + number | `C1`, `C2` |
| Index ID | `I` + number | `I1`, `I2` |
| Open question ID | `OQ-{MODULE}-{N}` | `OQ-GOV-3` |
| Relationship (Neo4j) | SCREAMING_SNAKE_CASE | `BELONGS_TO_DOMAIN` |

Neo4j relationship names are derived automatically from property names by converting camelCase to `SCREAMING_SNAKE_CASE` (e.g. `partOf` → `PART_OF`).

---

## Module Dependency Map

```
ORG  ←──────────────────────────┐
 ↑                              │
SYS  ← ART                     │
 ↑         ↘                   │
DEC          (dual-labelled    │
 ↑            ADR node)        │
GOV ──────────────────────────→┘
```

- **ORG** is referenced by all other modules (Person, Team)
- **SYS** is referenced by ART, DEC, GOV (System, Component)
- **ART** + **DEC** share the ADR node (dual-labelled in Neo4j)
- **GOV** sits atop — references ORG, SYS, DEC (QualityAttribute)

Circular references in YAML are fine — they are resolved when loaded into Neo4j as a unified graph.

---

## Implementation Status

| Module | YAML | Python (owlready2) | Neo4j loaded |
|---|---|---|---|
| ORG | ✅ draft | ❌ pending | ❌ pending |
| SYS | ✅ draft | ❌ pending | ❌ pending |
| ART | ✅ draft | ❌ pending | ❌ pending |
| DEC | ✅ draft | ❌ pending | ❌ pending |
| GOV | ✅ draft | ❌ pending | ❌ pending |

The next step after YAML review is to translate each module into Python (`owlready2`) and apply the Neo4j constraints/indexes in `docs/DESIGN.md §11.2`.
