"""
Software Architecture Ontology
Defines classes, relationships, and individuals using owlready2.
Exported as OWL/XML for use with WebProtégé or import into Neo4j via n10s.
"""

from owlready2 import *
import os

ONTOLOGY_IRI = "http://example.org/software-architecture-ontology"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/architecture.owl")


def build_ontology() -> Ontology:
    onto = get_ontology(ONTOLOGY_IRI)

    with onto:

        # ── Core Classes ─────────────────────────────────────────────────────

        class ArchitecturalConcept(Thing):
            """Root class for all architectural concepts."""

        class System(ArchitecturalConcept):
            """A complete software system or application."""

        class Component(ArchitecturalConcept):
            """A deployable or logical unit within a system (service, module, library)."""

        class Service(Component):
            """A network-addressable component exposing an API."""

        class Microservice(Service):
            """A fine-grained, independently deployable service."""

        class Library(Component):
            """A reusable code package consumed at build time."""

        class Database(Component):
            """A data storage component."""

        class RelationalDatabase(Database):
            pass

        class GraphDatabase(Database):
            pass

        class DocumentDatabase(Database):
            pass

        class MessageBroker(Component):
            """Async communication infrastructure (Kafka, RabbitMQ, etc.)."""

        class APIGateway(Component):
            """Entry point that routes, authenticates, and rate-limits requests."""

        class Frontend(Component):
            """User interface layer (web, mobile, desktop)."""

        class Infrastructure(ArchitecturalConcept):
            """Physical or cloud infrastructure elements."""

        class CloudProvider(Infrastructure):
            pass

        class ContainerOrchestrator(Infrastructure):
            """e.g. Kubernetes, ECS."""

        class CDN(Infrastructure):
            pass

        class LoadBalancer(Infrastructure):
            pass

        # ── Architecture Patterns ─────────────────────────────────────────────

        class ArchitecturePattern(ArchitecturalConcept):
            """A named, reusable architecture style or pattern."""

        class Microservices(ArchitecturePattern):
            pass

        class Monolith(ArchitecturePattern):
            pass

        class EventDriven(ArchitecturePattern):
            pass

        class CQRS(ArchitecturePattern):
            pass

        class Hexagonal(ArchitecturePattern):
            pass

        class LayeredArchitecture(ArchitecturePattern):
            pass

        class ServerlessPattern(ArchitecturePattern):
            pass

        # ── Architecture Decisions ────────────────────────────────────────────

        class ArchitectureDecisionRecord(ArchitecturalConcept):
            """A documented architecture decision (ADR)."""

        class TechnologyChoice(ArchitecturalConcept):
            """A selected technology for a specific concern."""

        class TechnologyCategory(ArchitecturalConcept):
            """Category of technology (language, framework, database, etc.)."""

        # ── Quality Attributes ────────────────────────────────────────────────

        class QualityAttribute(ArchitecturalConcept):
            """Non-functional requirement / quality attribute (NFR)."""

        class Scalability(QualityAttribute):
            pass

        class Reliability(QualityAttribute):
            pass

        class Security(QualityAttribute):
            pass

        class Performance(QualityAttribute):
            pass

        class Maintainability(QualityAttribute):
            pass

        class Observability(QualityAttribute):
            pass

        # ── Teams & Ownership ─────────────────────────────────────────────────

        class Team(ArchitecturalConcept):
            """An engineering team owning one or more components."""

        class Person(ArchitecturalConcept):
            """An individual (architect, engineer, lead)."""

        # ── Object Properties (Relationships) ─────────────────────────────────

        class dependsOn(ObjectProperty, TransitiveProperty):
            """Component A depends on Component B."""
            domain = [Component]
            range = [Component]

        class exposesAPI(ObjectProperty):
            """A service exposes an API."""
            domain = [Service]
            range = [Component]

        class consumesAPI(ObjectProperty):
            """A component consumes an API from another."""
            domain = [Component]
            range = [Service]

        class belongsTo(ObjectProperty):
            """A component belongs to a system."""
            domain = [Component]
            range = [System]

        class ownedBy(ObjectProperty):
            """A component or system is owned by a team."""
            domain = [Component]
            range = [Team]

        class followsPattern(ObjectProperty):
            """A system or component follows an architecture pattern."""
            domain = [ArchitecturalConcept]
            range = [ArchitecturePattern]

        class usedBy(ObjectProperty):
            """A technology/component is used by a system."""
            domain = [Component]
            range = [System]

        class storesDataIn(ObjectProperty):
            """A service stores data in a database."""
            domain = [Service]
            range = [Database]

        class publishesTo(ObjectProperty):
            """A service publishes events to a message broker."""
            domain = [Service]
            range = [MessageBroker]

        class subscribesTo(ObjectProperty):
            """A service subscribes to a message broker."""
            domain = [Service]
            range = [MessageBroker]

        class addressesQuality(ObjectProperty):
            """An architectural decision addresses a quality attribute."""
            domain = [ArchitectureDecisionRecord]
            range = [QualityAttribute]

        class madeBy(ObjectProperty):
            """An ADR was made by a person."""
            domain = [ArchitectureDecisionRecord]
            range = [Person]

        class memberOf(ObjectProperty):
            """A person is a member of a team."""
            domain = [Person]
            range = [Team]

        class deployedOn(ObjectProperty):
            """A component is deployed on infrastructure."""
            domain = [Component]
            range = [Infrastructure]

        # ── Data Properties ────────────────────────────────────────────────────

        class hasName(DataProperty, FunctionalProperty):
            domain = [ArchitecturalConcept]
            range = [str]

        class hasDescription(DataProperty):
            domain = [ArchitecturalConcept]
            range = [str]

        class hasVersion(DataProperty):
            domain = [Component]
            range = [str]

        class hasEndpoint(DataProperty):
            domain = [Service]
            range = [str]

        class hasLanguage(DataProperty):
            domain = [Component]
            range = [str]

        class hasFramework(DataProperty):
            domain = [Component]
            range = [str]

        class hasStatus(DataProperty):
            """e.g. proposed, accepted, deprecated"""
            domain = [ArchitectureDecisionRecord]
            range = [str]

        class hasDate(DataProperty):
            domain = [ArchitectureDecisionRecord]
            range = [str]

    return onto


def save_ontology(onto: Ontology, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    onto.save(file=path, format="rdfxml")
    print(f"Ontology saved to: {path}")


if __name__ == "__main__":
    onto = build_ontology()
    save_ontology(onto, OUTPUT_PATH)

    # Quick summary
    print(f"\nClasses defined: {len(list(onto.classes()))}")
    print(f"Object properties: {len(list(onto.object_properties()))}")
    print(f"Data properties: {len(list(onto.data_properties()))}")
    print("\nTop-level classes:")
    for cls in onto.classes():
        if cls.is_a == [Thing]:
            print(f"  - {cls.name}")
