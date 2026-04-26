"""
Architecture Q&A agent — natural language → Cypher → answer.

Uses:
  - Ollama (local LLM) via langchain-ollama
  - Neo4j Python driver (no APOC plugin required)
  - Custom NL-to-Cypher chain with schema introspection via built-in procedures

Run:
    python interaction/qa_agent.py
    python interaction/qa_agent.py "Which services depend on Kafka?"

Change DEFAULT_MODEL to any model from `ollama list`.
"""

import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "rahul1234")
DEFAULT_MODEL  = os.getenv("OLLAMA_MODEL",   "qwen2.5-coder:14b")

EXAMPLE_QUESTIONS = [
    "Which services depend on Kafka?",
    "What databases does the Order Service use?",
    "Which team owns the Catalog Service?",
    "What architecture patterns does the E-Commerce Platform follow?",
    "List all accepted ADRs and who made them.",
    "Which services are deployed on Kubernetes?",
    "What quality attributes does ADR-001 address?",
    "Which microservices expose an endpoint under /api?",
]

# ── Schema introspection (no APOC needed) ────────────────────────────────────

def get_schema(driver) -> str:
    """Build a human-readable schema string using built-in Neo4j procedures."""
    with driver.session() as session:
        labels = [r["label"] for r in session.run("CALL db.labels() YIELD label")]
        rel_types = [r["relationshipType"] for r in
                     session.run("CALL db.relationshipTypes() YIELD relationshipType")]

        node_props: dict[str, list[str]] = {}
        for r in session.run(
            "CALL db.schema.nodeTypeProperties() YIELD nodeType, propertyName "
            "WITH nodeType, propertyName WHERE propertyName IS NOT NULL "
            "RETURN nodeType, propertyName"
        ):
            label = r["nodeType"].strip(":`")
            node_props.setdefault(label, []).append(r["propertyName"])

        rel_props: dict[str, list[str]] = {}
        for r in session.run(
            "CALL db.schema.relTypeProperties() YIELD relType, propertyName "
            "WITH relType, propertyName WHERE propertyName IS NOT NULL "
            "RETURN relType, propertyName"
        ):
            rel = r["relType"].strip(":`")
            rel_props.setdefault(rel, []).append(r["propertyName"])

        # Collect actual relationship patterns (src label → rel → dst label)
        patterns: list[str] = []
        for r in session.run("""
            MATCH (a)-[rel]->(b)
            WITH labels(a)[0] AS src, type(rel) AS relType, labels(b)[0] AS dst
            RETURN DISTINCT src, relType, dst
            ORDER BY relType, src
            LIMIT 80
        """):
            patterns.append(f"  (:{r['src']})-[:{r['relType']}]->(:{r['dst']})")

    lines = ["Node labels and their properties:"]
    for lbl in sorted(labels):
        props = node_props.get(lbl, [])
        lines.append(f"  (:{lbl}) {{{', '.join(props)}}}" if props else f"  (:{lbl})")

    lines.append("\nRelationship types and their properties:")
    for rel in sorted(rel_types):
        props = rel_props.get(rel, [])
        lines.append(f"  [:{rel}] {{{', '.join(props)}}}" if props else f"  [:{rel}]")

    lines.append("\nRelationship patterns in the graph:")
    lines.extend(patterns)

    return "\n".join(lines)


# ── Prompts ──────────────────────────────────────────────────────────────────

CYPHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Neo4j Cypher query writer.
Given the graph schema below, write a single valid Cypher query that answers the user's question.

Rules:
- Return ONLY the Cypher query, no explanation, no markdown fences, no code blocks.
- Use MATCH, WHERE, RETURN clauses.
- Always use DISTINCT to avoid duplicates where appropriate.
- Limit results to 25 rows unless the question implies otherwise.
- Use the EXACT relationship types from the schema — do NOT invent new ones.
- Node properties: name, description, version, language, framework, endpoint, role, status, date, title, technology.
- Use the "Relationship patterns" section to know which labels connect via which relationship.

Schema:
{schema}

Few-shot examples (use these as a guide for structure):

Q: Which services publish to Kafka?
A: MATCH (s:Component)-[:PUBLISHES_TO]->(k:Component) WHERE k.name = 'Kafka' RETURN DISTINCT s.name

Q: Which services subscribe to Kafka?
A: MATCH (s:Component)-[:SUBSCRIBES_TO]->(k:Component) WHERE k.name = 'Kafka' RETURN DISTINCT s.name

Q: What databases does the Order Service use?
A: MATCH (s:Component)-[:STORES_DATA_IN]->(db:Component) WHERE s.name = 'Order Service' RETURN DISTINCT db.name, db.technology

Q: Which team owns the Catalog Service?
A: MATCH (s:Component)-[:OWNED_BY]->(t:Team) WHERE s.name = 'Catalog Service' RETURN t.name

Q: Which services are deployed on Kubernetes?
A: MATCH (s:Component)-[:DEPLOYED_ON]->(k:Component) WHERE k.name = 'Kubernetes' RETURN DISTINCT s.name
"""),
    ("human", "{question}"),
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful software architecture assistant.
Given a question and the raw results from a Neo4j graph query, provide a concise,
human-friendly answer. Do not invent facts not present in the results.
If the results are empty, say so clearly."""),
    ("human", "Question: {question}\n\nGraph query results:\n{results}"),
])

RETRY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Neo4j Cypher query writer.
The previous Cypher query you wrote returned zero results. 
Analyse why it may have been wrong and write a corrected query.

Schema:
{schema}

Previous (failed) Cypher:
{failed_cypher}

Rules:
- Return ONLY the corrected Cypher query, no explanation, no markdown fences.
- Use the EXACT relationship types from the schema — do NOT invent new ones.
- "depend on" or "use" Kafka means a service PUBLISHES_TO or SUBSCRIBES_TO it.
- Check all relationship types in the schema before choosing one.
- If the question asks about two possible directions, use OR or two MATCH clauses with UNION.
"""),
    ("human", "Original question: {question}"),
])


class ArchitectureQAAgent:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.driver.verify_connectivity()

        self.schema = get_schema(self.driver)
        llm = ChatOllama(model=model, temperature=0)
        parser = StrOutputParser()

        self.cypher_chain = CYPHER_PROMPT | llm | parser
        self.retry_chain  = RETRY_PROMPT  | llm | parser
        self.answer_chain = ANSWER_PROMPT | llm | parser

    def _run_cypher(self, cypher: str) -> list[dict]:
        with self.driver.session() as session:
            return [dict(r) for r in session.run(cypher)]

    def ask(self, question: str, verbose: bool = True) -> str:
        # Step 1: generate Cypher
        cypher = self.cypher_chain.invoke({
            "schema": self.schema,
            "question": question,
        }).strip()

        if verbose:
            print(f"\nGenerated Cypher:\n  {cypher}")

        # Step 2: execute Cypher (with one self-correction retry on empty results)
        max_attempts = 2
        results = []
        for attempt in range(max_attempts):
            try:
                results = self._run_cypher(cypher)
            except Exception as e:
                if verbose:
                    print(f"  Cypher error: {e}")
                results = []

            if verbose:
                print(f"Results ({len(results)} rows): {results[:5]}")

            if results or attempt == max_attempts - 1:
                break

            # Retry: feed failed Cypher back to LLM for self-correction
            if verbose:
                print("\nNo results — asking LLM to self-correct...")
            cypher = self.retry_chain.invoke({
                "schema": self.schema,
                "failed_cypher": cypher,
                "question": question,
            }).strip()
            if verbose:
                print(f"Corrected Cypher:\n  {cypher}")

        # Step 3: natural-language answer
        answer = self.answer_chain.invoke({
            "question": question,
            "results": results,
        })
        return answer

    def close(self):
        self.driver.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def interactive_loop(agent: ArchitectureQAAgent):
    print("\nArchitecture Q&A  (type 'quit' to exit, 'examples' for sample questions)")
    while True:
        try:
            question = input("\nAsk> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            break
        if question.lower() == "examples":
            for i, q in enumerate(EXAMPLE_QUESTIONS, 1):
                print(f"  {i}. {q}")
            continue
        print(f"\n{'─'*60}")
        answer = agent.ask(question)
        print(f"\nA: {answer}")
        print("─" * 60)


if __name__ == "__main__":
    print(f"Connecting to Neo4j at {NEO4J_URI}...")
    print(f"Using LLM: {DEFAULT_MODEL} (via Ollama)\n")

    agent = ArchitectureQAAgent()
    print("Schema loaded.\n")

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"Q: {question}")
        print("─" * 60)
        answer = agent.ask(question)
        print(f"\nA: {answer}")
    else:
        interactive_loop(agent)

    agent.close()
