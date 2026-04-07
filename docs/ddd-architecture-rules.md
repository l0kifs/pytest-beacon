# DDD Architecture Rules

> **Version:** 1.0.0
> **Purpose:** Rules for Python projects using DDD principles with a focus on simplicity and maintainability. Works for HTTP APIs, CLI tools, background workers, libraries, etc.

---

## 🎯 Core Rules

1. **Domain = Business Logic** (pure Python, no frameworks, Pydantic allowed for validation, standard library logging allowed)
2. **Infrastructure = Technical Details** (database, external APIs, file system)
3. **Entry Points = Interface Layer** (CLI, HTTP API, workers, etc.)
4. **Dependencies point inward:** Entry Points → Infrastructure → Domain
5. **All Python packages require `__init__.py`** (directories with code must have `__init__.py`, can only contain docstrings)

---

## 📁 Project Structure

```
src/<package_name>/
├── config/                    # Settings ONLY (no technical implementation)
│   ├── settings.py            # Application settings (env vars, constants)
│   └── logging.py             # Logging configuration
├── domains/                   # Business logic (pure Python)
│   └── <domain>/              
│       ├── models.py          # Entities (with business logic)
│       ├── exceptions.py      # Domain exceptions
│       └── services.py        # Application services (use cases)
├── infrastructure/            
│   ├── database/              
│   │   ├── database.py        # DB engine, session, type decorators
│   │   ├── models.py          # SQLAlchemy models (if using DB)
│   │   └── repositories.py   # Repository implementations
│   ├── observability/         # Logging adapters, tracing helpers, metrics emitters
│   ├── clients/               # External API clients, URL providers
│   └── storage/               # File system, cloud storage, etc.
└── entry_points/              # Application entry points
    ├── main.py                # Entry point, dependency wiring
    ├── cli/                   # CLI commands (if CLI app)
    ├── api/                   # HTTP endpoints (if web app)
    ├── web/                   # Web pages (if web app)
    │   ├── pages/             # Web page handlers
    │   ├── static/            # CSS, JS, images
    │   └── templates/         # HTML templates
    └── workers/               # Background workers (if async jobs)
```

**CRITICAL - config/ folder rules:**
- ✅ **Belongs in config/:** Settings classes, environment variables, constants, logging configuration
- ❌ **Does NOT belong in config/:** Database engines/sessions, API clients, URL providers, any technical implementation
- 🔀 **If unsure:** Technical implementation = Infrastructure layer

**Note:** Include only layers you need. For example:
- **CLI tool:** `entry_points/cli/` + `entry_points/main.py` only
- **Web API:** `entry_points/api/` + `entry_points/main.py` only
- **Web app with UI:** `entry_points/web/` (including static/templates) + `entry_points/main.py`
- **Library:** No entry points, just `domains/` and `infrastructure/`

**Important:** 
- `main.py` should be in `entry_points/` (application bootstrap)
- `static/` and `templates/` should be in `entry_points/web/` (web presentation layer)
- All application interface code belongs in `entry_points/`

---

## 🏗️ Three Layers

### Domain Layer (`domains/<domain>/`)

**Rules:**
- ✅ Business logic only
- ✅ Pure Python (no framework imports, Pydantic and standard library logging allowed)
- ✅ Can use Pydantic models for data validation
- ✅ Can use standard library logging
- ❌ No `infrastructure/` or `entry_points/` imports
- ❌ No framework-specific imports (FastAPI, SQLAlchemy, etc.)

**Example:**
```python
# domains/tasks/models.py
from pydantic import BaseModel, field_validator
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class Task(BaseModel):
    """Domain entity with business logic."""
    id: UUID
    status: str
    description: str
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status value."""
        valid_statuses = {"PENDING", "ACTIVE", "COMPLETED"}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v
    
    def complete(self) -> None:
        """Business rule: only active tasks can be completed."""
        if self.status != "ACTIVE":
            logger.warning("Cannot complete task: invalid status", task_id=self.id, status=self.status)
            raise InvalidStatusError()
        logger.info("Task completed", task_id=self.id)
        self.status = "COMPLETED"
    
    class Config:
        frozen = True  # Immutable entity

# domains/tasks/services.py
import logging

logger = logging.getLogger(__name__)

class TaskService:
    def __init__(self, repository):
        self._repository = repository
    
    def create_task(self, description: str) -> Task:
        task = Task(id=uuid4(), status="PENDING", description=description)
        self._repository.save(task)
        logger.info("Created task", task_id=task.id)
        return task
```

**Note:** Pydantic in domain models is useful for:
- Data validation with `@field_validator`
- Type safety and documentation
- Serialization/deserialization
- Immutability with `frozen=True`

**Note:** standard library logging is useful for:
- Tracking business operations and decisions
- Debugging domain logic
- Auditing important business events

Use regular Python classes if you don't need validation or prefer simpler approach.

### Infrastructure Layer (`infrastructure/`)

**Rules:**
- ✅ Database engines, sessions, connection management
- ✅ Database models (if using database)
- ✅ Repository implementations
- ✅ External API clients, URL providers
- ✅ File system operations
- ✅ Observability helpers (logging adapters, tracing utilities, metrics emitters)
- ✅ Any technical implementation details
- ❌ No business logic

**Example:**
```python
# infrastructure/database/models.py
class TaskDBModel(Base):
    __tablename__ = "tasks"
    id = Column(UUID, primary_key=True)
    status = Column(String)
    description = Column(String)

# infrastructure/database/repositories.py
class TaskRepository:
    def __init__(self, session):
        self._session = session
    
    def save(self, task: Task) -> None:
        db_model = TaskDBModel(id=task.id, status=task.status, description=task.description)
        self._session.add(db_model)
        self._session.commit()
    
    def find_by_id(self, task_id: UUID) -> Task | None:
        db_model = self._session.query(TaskDBModel).filter_by(id=task_id).first()
        if not db_model:
            return None
        return Task(id=db_model.id, status=db_model.status, description=db_model.description)
```

### Entry Points Layer (`entry_points/`)

**Purpose:** Application interfaces (CLI, HTTP API, background workers, etc.)

**Rules:**
- ✅ Handle input/output for specific interface
- ✅ Validate input
- ✅ Call services, convert responses
- ❌ No business logic
- ❌ No direct database access

**Examples:**

**CLI:**
```python
# entry_points/cli/task_cli.py
import click
from domains.tasks.services import TaskService

@click.command()
@click.argument('description')
def create_task(description: str, service: TaskService):
    """Create a new task."""
    task = service.create_task(description)
    click.echo(f"Created task: {task.id}")
```

**HTTP API:**
```python
# entry_points/api/task_api.py
from fastapi import APIRouter, Depends
from domains.tasks.services import TaskService

router = APIRouter()

@router.post("/tasks")
async def create_task(
    request: TaskCreateRequest,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    task = service.create_task(request.description)
    return TaskResponse.from_entity(task)
```

**Background Worker:**
```python
# entry_points/workers/task_worker.py
from domains.tasks.services import TaskService

def process_task_queue(service: TaskService):
    """Process tasks from queue."""
    while True:
        task = get_next_task_from_queue()
        if task:
            service.complete_task(task.id)
```

---

## 🔄 Dependency Injection

**Pattern:** Factory functions in `entry_points/main.py` or dedicated module, inject via constructor.

```python
# entry_points/main.py (or config/dependencies.py)
def get_task_repository() -> TaskRepository:
    return TaskRepository(get_db_session())

def get_task_service() -> TaskService:
    return TaskService(get_task_repository())

# Entry point usage examples:

# CLI
def main():
    service = get_task_service()
    create_task_cli(service)

# HTTP API
@router.post("/tasks")
async def create_task(service: TaskService = Depends(get_task_service)):
    return service.create_task(request.description)

# Worker
def run_worker():
    service = get_task_service()
    process_task_queue(service)
```

---

## 🚫 Common Mistakes

### ❌ Business Logic in Entry Points
```python
# BAD
@router.post("/tasks")
async def create_task(request: TaskCreateRequest):
    task = Task(...)  # Business logic here!
    session.add(TaskDBModel(...))

# GOOD
@router.post("/tasks")
async def create_task(service: TaskService = Depends(...)):
    return service.create_task(request.description)
```

### ❌ Database Models in Domain
```python
# BAD
from sqlalchemy import Column  # Infrastructure import!
class Task:
    id = Column(UUID)

# GOOD: Pure Python or Pydantic (standard logging is also OK)
import logging

logger = logging.getLogger(__name__)

class Task(BaseModel):  # Pydantic is OK
    id: UUID
    status: str
    
    def complete(self):
        # Business logic here with logging
        logger.info("Completing task", task_id=self.id)
        pass
```

### ❌ Anemic Domain Model
```python
# BAD: Just data, no business logic
class Task(BaseModel):
    id: UUID
    status: str
    # No business logic methods

# GOOD: With business logic (Pydantic or regular class)
class Task(BaseModel):
    id: UUID
    status: str
    
    def complete(self):
        """Business rule: only active tasks can be completed."""
        if self.status != "ACTIVE":
            raise InvalidStatusError()
        self.status = "COMPLETED"
```

---

## ✅ Quick Checklist

- [ ] Domain has no `infrastructure/` or `entry_points/` imports
- [ ] Entities contain business logic (not just data)
- [ ] Services orchestrate, don't contain business logic
- [ ] Entry points only handle I/O (call services)
- [ ] Dependencies injected via constructor
- [ ] **Config has NO technical implementation** (database engines, API clients, URL providers → infrastructure/)
- [ ] Max 300 lines per file

---

## 📚 Quick Reference

**File Structure:**
```
config/settings.py                  # Settings and configuration ONLY
domains/<domain>/models.py          # Entities with business logic
domains/<domain>/services.py        # Application services
domains/<domain>/exceptions.py      # Domain exceptions
infrastructure/database/database.py # DB engine, session, types
infrastructure/database/models.py   # Database models (if using DB)
infrastructure/database/repositories.py  # Repositories
infrastructure/observability/logging.py  # Logging adapters and observability helpers
infrastructure/clients/             # API clients, URL providers
entry_points/main.py                # Entry point, dependency wiring
entry_points/cli/                   # CLI commands (if CLI app)
entry_points/api/                   # HTTP endpoints (if web app)
entry_points/web/                   # Web UI (if web app with UI)
entry_points/web/static/            # CSS, JS, images (if web app)
entry_points/web/templates/         # HTML templates (if web app)
entry_points/workers/               # Background workers (if async jobs)
```

**Import Rules:**
- Config: NO imports from infrastructure or entry_points
- Domain: Standard library + Pydantic (for validation) + logging (for logging)
- Infrastructure: Can import Domain
- Entry Points: Can import Domain and Infrastructure

**Dependency Flow:**
```
Entry Point → Service → Entity → Repository → Database/Storage
```

---

## 🎯 When to Add Complexity

**Start Simple:**
- Single `models.py` per domain
- Concrete repositories (no interfaces)
- Services in `services.py`

**Add Only When Needed:**
- Value objects → Complex validation needed
- Repository interfaces → Multiple implementations needed
- Domain services → Logic spans multiple entities
- Events → Event-driven architecture needed

**Principle:** YAGNI - add complexity only when you actually need it.

---

**Remember:** Keep it simple. Start with basic structure, add complexity only when needed.
