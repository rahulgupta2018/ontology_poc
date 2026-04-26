"""
Ingestion script: loads the architecture ontology schema and sample data into Neo4j.

Run:
    python ingestion/load_ontology.py
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER     = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "rahul1234")


# ── Ontology schema: class hierarchy as Cypher constraints & nodes ────────────

SCHEMA_QUERIES = [
    # Uniqueness constraints (one per label)
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:OntologyClass)  REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:System)         REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Component)      REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Team)           REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Person)         REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ADR)            REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Pattern)        REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:QualityAttr)    REQUIRE n.name IS UNIQUE",
]

# ── Class hierarchy as meta-nodes (the ontology schema itself) ────────────────

CLASS_HIERARCHY = [
    # (child_label, parent_label, description)
    ("System",                  "ArchitecturalConcept", "A complete software system"),
    ("Component",               "ArchitecturalConcept", "A deployable or logical unit"),
    ("Service",                 "Component",            "A network-addressable component"),
    ("Microservice",            "Service",              "Fine-grained independently deployable service"),
    ("Library",                 "Component",            "Reusable code package"),
    ("Database",                "Component",            "Data storage component"),
    ("RelationalDatabase",      "Database",             "SQL-based relational database"),
    ("GraphDatabase",           "Database",             "Graph-based database"),
    ("DocumentDatabase",        "Database",             "Document-oriented database"),
    ("MessageBroker",           "Component",            "Async messaging infrastructure"),
    ("APIGateway",              "Component",            "Entry point for routing and auth"),
    ("Frontend",                "Component",            "User interface layer"),
    ("Infrastructure",          "ArchitecturalConcept", "Physical or cloud infrastructure"),
    ("CloudProvider",           "Infrastructure",       "Cloud platform provider"),
    ("ContainerOrchestrator",   "Infrastructure",       "Container orchestration platform"),
    ("CDN",                     "Infrastructure",       "Content delivery network"),
    ("LoadBalancer",            "Infrastructure",       "Traffic distribution component"),
    ("ArchitecturePattern",     "ArchitecturalConcept", "Named reusable architecture style"),
    ("Microservices",           "ArchitecturePattern",  "Microservices architecture pattern"),
    ("Monolith",                "ArchitecturePattern",  "Monolithic architecture pattern"),
    ("EventDriven",             "ArchitecturePattern",  "Event-driven architecture pattern"),
    ("CQRS",                    "ArchitecturePattern",  "Command Query Responsibility Segregation"),
    ("Hexagonal",               "ArchitecturePattern",  "Hexagonal / ports and adapters pattern"),
    ("LayeredArchitecture",     "ArchitecturePattern",  "Layered / n-tier architecture"),
    ("ServerlessPattern",       "ArchitecturePattern",  "Serverless architecture pattern"),
    ("ArchitectureDecisionRecord", "ArchitecturalConcept", "A documented architecture decision"),
    ("TechnologyChoice",        "ArchitecturalConcept", "A selected technology"),
    ("TechnologyCategory",      "ArchitecturalConcept", "Category of technology"),
    ("QualityAttribute",        "ArchitecturalConcept", "Non-functional requirement"),
    ("Scalability",             "QualityAttribute",     "Ability to scale under load"),
    ("Reliability",             "QualityAttribute",     "System dependability"),
    ("Security",                "QualityAttribute",     "Protection against threats"),
    ("Performance",             "QualityAttribute",     "Speed and throughput"),
    ("Maintainability",         "QualityAttribute",     "Ease of change and upkeep"),
    ("Observability",           "QualityAttribute",     "Ability to monitor and debug"),
    ("Team",                    "ArchitecturalConcept", "An engineering team"),
    ("Person",                  "ArchitecturalConcept", "An individual contributor"),
]

# ── Sample architecture data ──────────────────────────────────────────────────

SAMPLE_DATA = """
// ── Teams ────────────────────────────────────────────────────────────────────
MERGE (t1:Team {name: 'Platform Team'})
  SET t1.description = 'Owns core infrastructure and shared services'
MERGE (t2:Team {name: 'Order Team'})
  SET t2.description = 'Owns order processing domain'
MERGE (t3:Team {name: 'Catalog Team'})
  SET t3.description = 'Owns product catalog domain'

// ── People ───────────────────────────────────────────────────────────────────
MERGE (p1:Person {name: 'Alice'})  SET p1.role = 'Principal Architect'
MERGE (p2:Person {name: 'Bob'})    SET p2.role = 'Tech Lead'
MERGE (p3:Person {name: 'Carol'})  SET p3.role = 'Senior Engineer'

MERGE (p1)-[:MEMBER_OF]->(t1)
MERGE (p2)-[:MEMBER_OF]->(t2)
MERGE (p3)-[:MEMBER_OF]->(t3)

// ── Systems ──────────────────────────────────────────────────────────────────
MERGE (sys:System {name: 'E-Commerce Platform'})
  SET sys.description = 'Core e-commerce system'

// ── Infrastructure ────────────────────────────────────────────────────────────
MERGE (k8s:ContainerOrchestrator:Component {name: 'Kubernetes'})
  SET k8s.version = '1.29'
MERGE (aws:CloudProvider:Component {name: 'AWS'})
MERGE (cf:CDN:Component {name: 'CloudFront'})
MERGE (lb:LoadBalancer:Component {name: 'AWS ALB'})

// ── API Gateway ───────────────────────────────────────────────────────────────
MERGE (gw:APIGateway:Component {name: 'API Gateway'})
  SET gw.description = 'Kong API Gateway', gw.version = '3.4'

// ── Services ──────────────────────────────────────────────────────────────────
MERGE (os:Microservice:Component {name: 'Order Service'})
  SET os.language = 'Java', os.framework = 'Spring Boot',
      os.version = '2.1.0', os.endpoint = '/api/orders'

MERGE (cs:Microservice:Component {name: 'Catalog Service'})
  SET cs.language = 'Python', cs.framework = 'FastAPI',
      cs.version = '1.3.0', cs.endpoint = '/api/catalog'

MERGE (us:Microservice:Component {name: 'User Service'})
  SET us.language = 'Go', us.framework = 'Gin',
      us.version = '1.0.0', us.endpoint = '/api/users'

MERGE (ns:Microservice:Component {name: 'Notification Service'})
  SET ns.language = 'Node.js', ns.framework = 'Express',
      ns.version = '0.9.0', ns.endpoint = '/api/notifications'

MERGE (fe:Frontend:Component {name: 'Web App'})
  SET fe.language = 'TypeScript', fe.framework = 'React', fe.version = '18.0'

// ── Databases ─────────────────────────────────────────────────────────────────
MERGE (odb:RelationalDatabase:Component {name: 'Orders DB'})
  SET odb.technology = 'PostgreSQL', odb.version = '15'

MERGE (cdb:DocumentDatabase:Component {name: 'Catalog DB'})
  SET cdb.technology = 'MongoDB', cdb.version = '7.0'

MERGE (udb:RelationalDatabase:Component {name: 'Users DB'})
  SET udb.technology = 'PostgreSQL', udb.version = '15'

MERGE (cache:Component {name: 'Redis Cache'})
  SET cache.technology = 'Redis', cache.version = '7.2'

// ── Message Broker ────────────────────────────────────────────────────────────
MERGE (kafka:MessageBroker:Component {name: 'Kafka'})
  SET kafka.version = '3.6'

// ── Patterns ──────────────────────────────────────────────────────────────────
MERGE (ms_pat:Microservices:Pattern {name: 'Microservices'})
MERGE (ed_pat:EventDriven:Pattern  {name: 'EventDriven'})
MERGE (cq_pat:CQRS:Pattern         {name: 'CQRS'})

// ── Quality Attributes ────────────────────────────────────────────────────────
MERGE (sc:Scalability:QualityAttr  {name: 'Scalability'})
MERGE (re:Reliability:QualityAttr  {name: 'Reliability'})
MERGE (se:Security:QualityAttr     {name: 'Security'})
MERGE (ob:Observability:QualityAttr {name: 'Observability'})

// ── ADRs ──────────────────────────────────────────────────────────────────────
MERGE (adr1:ADR {name: 'ADR-001'})
  SET adr1.title = 'Adopt Microservices Architecture',
      adr1.status = 'accepted', adr1.date = '2024-01-15',
      adr1.description = 'Decompose monolith into microservices for independent scaling'

MERGE (adr2:ADR {name: 'ADR-002'})
  SET adr2.title = 'Use Kafka for async communication',
      adr2.status = 'accepted', adr2.date = '2024-02-10',
      adr2.description = 'Event-driven communication between services via Kafka'

MERGE (adr3:ADR {name: 'ADR-003'})
  SET adr3.title = 'Adopt CQRS for Order Service',
      adr3.status = 'proposed', adr3.date = '2024-03-01',
      adr3.description = 'Separate read and write models for high-throughput order processing'

// ── Relationships ─────────────────────────────────────────────────────────────

// Belong to system
MERGE (gw)-[:BELONGS_TO]->(sys)
MERGE (os)-[:BELONGS_TO]->(sys)
MERGE (cs)-[:BELONGS_TO]->(sys)
MERGE (us)-[:BELONGS_TO]->(sys)
MERGE (ns)-[:BELONGS_TO]->(sys)
MERGE (fe)-[:BELONGS_TO]->(sys)

// Ownership
MERGE (os)-[:OWNED_BY]->(t2)
MERGE (cs)-[:OWNED_BY]->(t3)
MERGE (us)-[:OWNED_BY]->(t1)
MERGE (ns)-[:OWNED_BY]->(t1)
MERGE (k8s)-[:OWNED_BY]->(t1)

// Service dependencies
MERGE (fe)-[:DEPENDS_ON]->(gw)
MERGE (gw)-[:DEPENDS_ON]->(os)
MERGE (gw)-[:DEPENDS_ON]->(cs)
MERGE (gw)-[:DEPENDS_ON]->(us)
MERGE (os)-[:DEPENDS_ON]->(cache)

// Data storage
MERGE (os)-[:STORES_DATA_IN]->(odb)
MERGE (cs)-[:STORES_DATA_IN]->(cdb)
MERGE (us)-[:STORES_DATA_IN]->(udb)

// Messaging
MERGE (os)-[:PUBLISHES_TO]->(kafka)
MERGE (ns)-[:SUBSCRIBES_TO]->(kafka)
MERGE (cs)-[:SUBSCRIBES_TO]->(kafka)

// Deployed on
MERGE (os)-[:DEPLOYED_ON]->(k8s)
MERGE (cs)-[:DEPLOYED_ON]->(k8s)
MERGE (us)-[:DEPLOYED_ON]->(k8s)
MERGE (ns)-[:DEPLOYED_ON]->(k8s)
MERGE (k8s)-[:DEPLOYED_ON]->(aws)
MERGE (fe)-[:DEPLOYED_ON]->(cf)
MERGE (lb)-[:DEPLOYED_ON]->(aws)

// Follows patterns
MERGE (sys)-[:FOLLOWS_PATTERN]->(ms_pat)
MERGE (sys)-[:FOLLOWS_PATTERN]->(ed_pat)
MERGE (os)-[:FOLLOWS_PATTERN]->(cq_pat)

// ADR relationships
MERGE (adr1)-[:ADDRESSES_QUALITY]->(sc)
MERGE (adr1)-[:ADDRESSES_QUALITY]->(re)
MERGE (adr1)-[:MADE_BY]->(p1)

MERGE (adr2)-[:ADDRESSES_QUALITY]->(re)
MERGE (adr2)-[:ADDRESSES_QUALITY]->(ob)
MERGE (adr2)-[:MADE_BY]->(p1)

MERGE (adr3)-[:ADDRESSES_QUALITY]->(sc)
MERGE (adr3)-[:MADE_BY]->(p2)
"""


def run(driver, query, params=None):
    with driver.session() as session:
        session.run(query, params or {})


def load_schema(driver):
    print("Creating constraints...")
    for q in SCHEMA_QUERIES:
        run(driver, q)

    print("Loading ontology class hierarchy...")
    for child, parent, desc in CLASS_HIERARCHY:
        run(driver, """
            MERGE (child:OntologyClass {name: $child})
              SET child.description = $desc
            MERGE (parent:OntologyClass {name: $parent})
            MERGE (child)-[:SUBCLASS_OF]->(parent)
        """, {"child": child, "parent": parent, "desc": desc})

    print(f"  Loaded {len(CLASS_HIERARCHY)} ontology classes.")


def load_sample_data(driver):
    print("Loading sample architecture data...")
    with driver.session() as session:
        session.run(SAMPLE_DATA)
    print("  Sample data loaded.")


def print_summary(driver):
    with driver.session() as session:
        result = session.run("""
            MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
        """)
        print("\nGraph summary:")
        for r in result:
            print(f"  {r['label']:30s} {r['count']} nodes")

        result = session.run("MATCH ()-[r]->() RETURN count(r) AS total")
        print(f"  {'Total relationships':30s} {result.single()['total']}")


if __name__ == "__main__":
    print(f"Connecting to {URI}...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print("Connected.\n")

    load_schema(driver)
    load_sample_data(driver)
    print_summary(driver)

    driver.close()
    print("\nDone. Open http://localhost:7474 to explore the graph.")
