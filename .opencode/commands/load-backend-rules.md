---
description: Load backend binding rules (DDD standards, architecture, coding conventions) into context. Use /load-backend-rules at the start of any backend work.
---

# Load Backend Development Rules

Read this file in full to load the complete backend development rule set
into the current session:

1. **`coding-standards-ddd.yaml`** — the authoritative DDD coding standards:
   domain entities, value objects, domain services, application services,
   architecture boundaries, error handling (result objects, not exceptions),
   forbidden patterns (no repositories, DAOs, DTOs, interfaces with single
   implementations, enterprise architectural styles), stack conventions
   (one shared serialisation module).

After reading, announce that the backend rules are active. All subsequent
backend work in this session must follow every binding rule from the file.
In particular:

- NEVER introduce Repository, DAO, or persistence abstractions — entities
  handle their own persistence.
- NEVER throw exceptions for expected conditions — return result objects
  with typed error codes instead.
- NEVER introduce interfaces with a single implementation.
- NEVER introduce DTOs with no behaviour or logic.
- NEVER use enterprise architectural styles (SOLID, Clean Architecture, hexagonal, onion).
- NEVER put HTTP/transport concerns into domain logic.
- NEVER create service classes that wrap domain logic.
- NEVER mangle code structure purely for testability.
- ALWAYS use the single shared serialisation module — do not introduce
  ad-hoc serialisation.
- PREFER rich domain models that encapsulate behaviour over anemic property bags.
- PREFER small, cohesive types over god-classes.
- ALLOW domain/application code to make outbound HTTP/RPC calls directly.
- ALLOW genuine DDD domain services (stateless, cross-aggregate, ubiquitously named).
- ALLOW genuine DDD application services (stateless workflow orchestrators).
- The AGENTS.md rules (project structure, service locator, mock policy, TDD)
  are already active from session start and do not need reloading.
