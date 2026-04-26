# Org Instance Data (ABox)

This directory contains per-division instance data for the Organisation ontology.
The schema (TBox — classes, properties, constraints) lives in `ontology/modules/org.yaml`.
These files are the **ABox** — the actual nodes to load into Neo4j.

## Structure

```
ontology/instances/
  org_bcb.yaml        ← Business & Commercial Banking
  org_retail.yaml     ← Retail Banking
  org_ipp.yaml        ← IP&P (template — fill in)
  org_group.yaml      ← Group-level enabling functions (Architecture, Security, etc.)
```

## File Format

Each instance file follows the same structure:

```yaml
division:
  name: "..."
  code: "..."
  platforms:
    - name: "..."
      code: "..."
      labs:
        - name: "..."
          code: "..."
          teams:
            - name: "..."
              code: "..."
              teamType: stream-aligned | platform | enabling | complicated-subsystem
              slackChannel: "#..."
              contactEmail: "..."
```

## Loading

Instance files are loaded by `ingestion/load_org_instances.py` (to be implemented).
All divisions load into the **same** Neo4j graph — the schema is shared.
Cross-division relationships (e.g. a shared platform team) are expressed via
`partOf` edges that cross division boundaries.
