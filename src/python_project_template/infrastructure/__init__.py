"""
Infrastructure layer containing technical implementation details.

Rules:
- Implements interfaces defined in the domain or supports domain logic.
- Contains database repositories, API clients, file storage, etc.
- Handles interactions with external systems (SQLAlchemy, httpx, etc.).
- Can import from domains.
- No business logic.
"""
