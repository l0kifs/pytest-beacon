"""
Application entry points (CLI, API, workers).

Rules:
- Handles application bootstrapping and dependency injection.
- Contains controllers/handlers for external interfaces.
- Orchestrates interaction between outer world and domain layer.
- Can import from domains and infrastructure.
- No business logic.
"""
