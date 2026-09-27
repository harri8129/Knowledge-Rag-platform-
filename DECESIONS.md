# Architecture Decisions

## ADR-001: Django

Decision:
Use Django + Django REST Framework as the backend.

Reason:
The project requires a structured backend with ORM,
authentication, APIs, admin functionality, and PostgreSQL
integration.

---

## ADR-002: PostgreSQL

Decision:
Use PostgreSQL as the primary application database.

PostgreSQL stores:
- documents
- document metadata
- chunks metadata
- conversations
- messages
- citations
- evaluations

---

## ADR-003: Qdrant

Decision:
Use Qdrant as the vector/retrieval database.

Qdrant stores:
- embeddings
- sparse vectors
- retrieval payload
- vector indexes

---

## ADR-004: Redis

Decision:
Redis is NOT part of Phase 0.

Redis will only be introduced when the application
has a demonstrated requirement for:
- caching
- background jobs
- temporary state
- rate limiting

---

## ADR-005: No Multi-tenancy

Decision:
Multi-tenancy is explicitly out of scope for V1.

Reason:
The primary goal is learning and implementing
advanced RAG retrieval correctly.