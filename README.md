# Architecture Ontology POC

A software architecture knowledge graph you can query in plain English.

**Stack:** Python · owlready2 · Neo4j · Ollama (local LLM) · LangChain

```
Natural language question
        ↓
  Cypher query (LLM)
        ↓
   Neo4j graph DB
        ↓
  [self-correct if empty]
        ↓
  Plain English answer
```

---

## Project structure

```
ontology_poc/
├── ontology/
│   └── architecture_ontology.py   # OWL ontology definition (owlready2)
├── ingestion/
│   └── load_ontology.py           # Load ontology + sample data into Neo4j
├── interaction/
│   └── qa_agent.py                # NL → Cypher → answer (Ollama + LangChain)
├── data/
│   ├── architecture.owl           # Generated OWL/RDF file
│   └── architecture.ttl           # Generated Turtle file (for VS Code Mentor)
├── .env                           # Neo4j credentials (git-ignored)
├── requirements.txt
└── README.md
```

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.9+ | [python.org](https://www.python.org) |
| Neo4j | 2026.x | `brew install neo4j` |
| Ollama | any | [ollama.com](https://ollama.com) |

---

## Setup

### 1. Clone and create virtual environment

```bash
cd ontology_poc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env   # or create .env manually
```

`.env` contents:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
OLLAMA_MODEL=qwen2.5-coder:14b   # optional — override default model
```

### 3. Start Neo4j

```bash
/opt/homebrew/opt/neo4j/bin/neo4j start
```

Verify it's running:

```bash
cypher-shell -u neo4j -p your-password "RETURN 1"
```

The Neo4j Browser is available at <http://localhost:7474>.

> **Note:** `brew services start neo4j` and `neo4j status` can be unreliable on Apple Silicon. Use the direct binary path above.

### 4. Pull an Ollama model

```bash
ollama pull qwen2.5-coder:14b   # recommended — best Cypher generation
# or a lighter alternative:
ollama pull llama3.1:8b
```

---

## Running

### Step 1 — Generate the OWL ontology files

Only needed if you want to regenerate `data/architecture.owl` and `data/architecture.ttl`:

```bash
source .venv/bin/activate
python ontology/architecture_ontology.py
```

Output: 38 classes, 14 object properties, 8 data properties.

### Step 2 — Load the graph into Neo4j

```bash
source .venv/bin/activate
python ingestion/load_ontology.py
```

This creates:
- 38 **OntologyClass** nodes (the schema hierarchy)
- 15 **Component** nodes (services, databases, infrastructure)
- Teams, People, Patterns, ADRs, Quality attributes
- 80 relationships

Run it again safely — all writes use `MERGE` (idempotent).

### Step 3 — Query in natural language

**Interactive mode:**

```bash
source .venv/bin/activate
python interaction/qa_agent.py
```

```
Ask> Which team owns the Catalog Service?
Ask> What databases does the Order Service use?
Ask> List all accepted ADRs and who made them.
Ask> examples     ← show 8 sample questions
Ask> quit
```

**Single question mode:**

```bash
python interaction/qa_agent.py "Which services are deployed on Kubernetes?"
```

---

## Sample questions

| Question | Tests |
|---|---|
| Which services depend on Kafka? | PUBLISHES_TO / SUBSCRIBES_TO |
| What databases does the Order Service use? | STORES_DATA_IN |
| Which team owns the Catalog Service? | OWNED_BY |
| What architecture patterns does the E-Commerce Platform follow? | FOLLOWS_PATTERN |
| List all accepted ADRs and who made them. | ADR status filter + MADE_BY |
| Which services are deployed on Kubernetes? | DEPLOYED_ON |
| What quality attributes does ADR-001 address? | ADDRESSES_QUALITY |
| Which microservices expose an endpoint under /api? | property filter |

---

## Exploring the graph directly

Open <http://localhost:7474> and run Cypher queries directly.

**See the full graph:**
```cypher
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100
```

**Explore the ontology class hierarchy:**
```cypher
MATCH p=(c:OntologyClass)-[:SUBCLASS_OF*]->(root) RETURN p
```

**Find all services and their dependencies:**
```cypher
MATCH (s:Microservice)-[r]->(t)
RETURN s.name AS service, type(r) AS relationship, t.name AS target
ORDER BY s.name
```

**See which team owns what:**
```cypher
MATCH (c:Component)-[:OWNED_BY]->(t:Team)
RETURN t.name AS team, collect(c.name) AS components
```

---

## Changing the LLM model

Set `OLLAMA_MODEL` in `.env` or pass it at runtime:

```bash
OLLAMA_MODEL=gemma4:latest python interaction/qa_agent.py
```

Any model from `ollama list` works. `qwen2.5-coder:14b` gives the best Cypher generation quality.

---

## How the Q&A agent works

1. **Schema introspection** — reads labels, relationship types, and actual graph patterns from Neo4j (no APOC plugin required)
2. **Cypher generation** — sends the schema + few-shot examples + your question to the LLM
3. **Execution** — runs the generated Cypher against Neo4j
4. **Self-correction** — if 0 rows returned, sends the failed query back to the LLM for a corrected attempt
5. **Answer synthesis** — a second LLM call turns the raw results into a plain English answer
