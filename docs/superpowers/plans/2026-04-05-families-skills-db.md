# Families & Skills DB-backed Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote families and skills from JSON-only seed files to first-class DB entities with relational integrity, full CRUD, and a clean idempotent bootstrap.

**Architecture:** New SQLAlchemy models (FamilyDefinition, SkillDefinition, SkillFamily, AgentSkill) with composite PK join tables. AgentDefinition gets a FK `family_id` and loses the JSONB `skills` column. An auto-seed at startup upserts from JSON. All runtime reads go through the DB, never JSON files.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL (SQLite in tests), Next.js 15 / React 19 / Tailwind CSS (frontend)

---

## File Map

### Backend — New files
| File | Responsibility |
|------|---------------|
| `app/models/family.py` | FamilyDefinition + SkillFamily + AgentSkill ORM models |
| `app/models/skill.py` | SkillDefinition ORM model |
| `app/schemas/family.py` | Pydantic schemas for Family CRUD |
| `app/services/family_service.py` | Family CRUD business logic |
| `app/services/skill_service.py` | Skill CRUD business logic (replaces skill_registry_service) |
| `app/services/seed_service.py` | Idempotent bootstrap from JSON |
| `app/api/routes/families.py` | Family API endpoints |
| `migrations/versions/004_families_skills_agent_skill.py` | Alembic migration |
| `tests/test_api_families.py` | Family endpoint tests |
| `tests/test_api_skills.py` | Skill endpoint tests |

### Backend — Modified files
| File | Change |
|------|--------|
| `app/models/registry.py` | Replace `family` str + `skills` JSONB with `family_id` FK + relationships |
| `app/models/__init__.py` | Import new models |
| `app/schemas/agent.py` | `family` → `family_id`, `skills` → `skill_ids` |
| `app/schemas/skill.py` | Add `allowed_families`, `SkillCreate`, `SkillUpdate` |
| `app/services/agent_registry_service.py` | Use DB for family/skill validation + AgentSkill joins |
| `app/api/routes/agents.py` | Adapt filter param, error codes |
| `app/api/routes/skills.py` | Rework to use skill_service (DB) |
| `app/main.py` | Replace `skill_registry_service.load_skills()` with `seed_service.seed_all()` |

### Frontend — New files
| File | Responsibility |
|------|---------------|
| `frontend/src/lib/families/types.ts` | Family + Skill TypeScript types |
| `frontend/src/lib/families/service.ts` | Family + Skill API client |
| `frontend/src/app/agents/families/page.tsx` | Families admin page |
| `frontend/src/components/agents/family-form-modal.tsx` | Create/edit family modal |
| `frontend/src/components/agents/skill-form-modal.tsx` | Create/edit skill modal |

### Frontend — Modified files
| File | Change |
|------|--------|
| `frontend/src/lib/agent-registry/types.ts` | `family` → `family_id`, `skills` → `skill_ids` |
| `frontend/src/lib/agent-registry/service.ts` | Update payloads, add family/skill fetchers |
| `frontend/src/components/agents/agent-form.tsx` | Family dropdown from API, skills filtered by family |
| `frontend/src/app/agents/page.tsx` | Family filter from API |
| `frontend/src/app/agents/new/page.tsx` | Load families |
| `frontend/src/app/agents/[id]/edit/page.tsx` | Load families |
| `frontend/src/app/agents/[id]/page.tsx` | Show family label |
| `frontend/src/app/agents/skills/page.tsx` | Full skills admin page |
| `frontend/src/components/layout/sidebar.tsx` | Add Families nav link |
| `frontend/src/components/agents/generate-agent-modal.tsx` | Use family_id |

---

## Task 1: DB Models — FamilyDefinition, SkillDefinition, SkillFamily, AgentSkill

**Files:**
- Create: `app/models/family.py`
- Create: `app/models/skill.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Create `app/models/skill.py`**

```python
"""SkillDefinition entity."""

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SkillDefinition(BaseModel):
    __tablename__ = "skill_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_templates: Mapped[list] = mapped_column(JSONB, default=list)
    output_guidelines: Mapped[list] = mapped_column(JSONB, default=list)

    # Relationships
    skill_families = relationship("SkillFamily", back_populates="skill", cascade="all, delete-orphan")
    agent_skills = relationship("AgentSkill", back_populates="skill")
```

- [ ] **Step 2: Create `app/models/family.py`**

```python
"""FamilyDefinition, SkillFamily, and AgentSkill entities."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.core.database import Base


class FamilyDefinition(BaseModel):
    __tablename__ = "family_definitions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    skill_families = relationship("SkillFamily", back_populates="family", cascade="all, delete-orphan")
    agents = relationship("AgentDefinition", back_populates="family_rel")


class SkillFamily(Base):
    """Join table: which skills are allowed for which families."""
    __tablename__ = "skill_families"

    skill_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("skill_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    family_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("family_definitions.id", ondelete="CASCADE"), primary_key=True
    )

    skill = relationship("SkillDefinition", back_populates="skill_families")
    family = relationship("FamilyDefinition", back_populates="skill_families")


class AgentSkill(Base):
    """Join table: which skills an agent uses."""
    __tablename__ = "agent_skills"

    agent_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("agent_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("skill_definitions.id", ondelete="RESTRICT"), primary_key=True
    )

    agent = relationship("AgentDefinition", back_populates="agent_skills")
    skill = relationship("SkillDefinition", back_populates="agent_skills")
```

- [ ] **Step 3: Update `app/models/__init__.py`**

Add imports for the new models:

```python
"""Import all models so Alembic can discover them."""

from app.models.request import Request
from app.models.case import Case
from app.models.workflow import WorkflowDefinition
from app.models.plan import OrchestrationPlan
from app.models.run import Run, RunNode
from app.models.invocation import SubagentInvocation, MCPInvocation
from app.models.control import ControlDecision
from app.models.approval import ApprovalRequest
from app.models.audit import AuditEvent, EvidenceRecord, ReplayBundle
from app.models.registry import AgentDefinition, MCPDefinition
from app.models.mcp_catalog import OrkestraMCPBinding
from app.models.settings import PolicyProfile, BudgetProfile
from app.models.family import FamilyDefinition, SkillFamily, AgentSkill
from app.models.skill import SkillDefinition

__all__ = [
    "Request", "Case", "WorkflowDefinition", "OrchestrationPlan",
    "Run", "RunNode", "SubagentInvocation", "MCPInvocation",
    "ControlDecision", "ApprovalRequest", "AuditEvent", "EvidenceRecord",
    "ReplayBundle", "AgentDefinition", "MCPDefinition",
    "OrkestraMCPBinding",
    "PolicyProfile", "BudgetProfile",
    "FamilyDefinition", "SkillFamily", "AgentSkill", "SkillDefinition",
]
```

- [ ] **Step 4: Commit**

```bash
git add app/models/family.py app/models/skill.py app/models/__init__.py
git commit -m "feat: add FamilyDefinition, SkillDefinition, SkillFamily, AgentSkill models"
```

---

## Task 2: Modify AgentDefinition — FK family_id + relationships

**Files:**
- Modify: `app/models/registry.py:13-39`

- [ ] **Step 1: Update AgentDefinition model**

Replace the `family` and `skills` columns, add FK and relationships:

```python
"""AgentDefinition and MCPDefinition entities."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import AgentStatus, MCPStatus


class AgentDefinition(BaseModel):
    __tablename__ = "agent_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    family_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("family_definitions.id"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_hints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    allowed_mcps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    forbidden_effects: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    input_contract_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_contract_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), default="medium")
    cost_profile: Mapped[str] = mapped_column(String(20), default="medium")
    limitations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    prompt_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_status: Mapped[str] = mapped_column(String(30), default="not_tested")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    status: Mapped[str] = mapped_column(String(20), default=AgentStatus.DRAFT)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    family_rel = relationship("FamilyDefinition", back_populates="agents")
    agent_skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")
```

Note: `family` column is renamed to `family_id` and gains a FK. `skills` JSONB column is removed — replaced by `agent_skills` relationship.

- [ ] **Step 2: Commit**

```bash
git add app/models/registry.py
git commit -m "feat: replace agent family/skills with FK and join table relationships"
```

---

## Task 3: Alembic Migration

**Files:**
- Create: `migrations/versions/004_families_skills_agent_skill.py`

- [ ] **Step 1: Write the migration**

This migration must:
1. Create `family_definitions`, `skill_definitions`, `skill_families`, `agent_skills` tables
2. Insert seed data from JSON files (families first, then skills + skill_families)
3. Migrate existing agent data: populate `agent_skills` from JSONB `skills`, rename `family` → `family_id`
4. Add FK constraint on `family_id`
5. Drop old `skills` column

```python
"""Add FamilyDefinition, SkillDefinition, SkillFamily, AgentSkill tables.
Migrate AgentDefinition: family -> family_id FK, skills JSONB -> agent_skills join.

Revision ID: 004
Revises: 003
Create Date: 2026-04-05
"""

import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create new tables
    op.create_table(
        "family_definitions",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("behavior_templates", JSONB(), nullable=False, server_default="[]"),
        sa.Column("output_guidelines", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "skill_families",
        sa.Column("skill_id", sa.String(100), sa.ForeignKey("skill_definitions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("family_id", sa.String(50), sa.ForeignKey("family_definitions.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "agent_skills",
        sa.Column("agent_id", sa.String(100), sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skill_id", sa.String(100), sa.ForeignKey("skill_definitions.id", ondelete="RESTRICT"), primary_key=True),
    )

    # 2. Seed families from JSON
    config_dir = Path(__file__).parent.parent.parent / "app" / "config"

    families_path = config_dir / "families.seed.json"
    if families_path.exists():
        families_data = json.loads(families_path.read_text(encoding="utf-8"))
        families_table = sa.table(
            "family_definitions",
            sa.column("id", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.Text),
        )
        for f in families_data.get("families", []):
            op.execute(
                families_table.insert().values(
                    id=f["family_id"], label=f["label"], description=f.get("description")
                )
            )

    # 3. Seed skills + skill_families from JSON
    skills_path = config_dir / "skills.seed.json"
    if skills_path.exists():
        skills_data = json.loads(skills_path.read_text(encoding="utf-8"))
        skills_table = sa.table(
            "skill_definitions",
            sa.column("id", sa.String),
            sa.column("label", sa.String),
            sa.column("category", sa.String),
            sa.column("description", sa.Text),
            sa.column("behavior_templates", JSONB),
            sa.column("output_guidelines", JSONB),
        )
        sf_table = sa.table(
            "skill_families",
            sa.column("skill_id", sa.String),
            sa.column("family_id", sa.String),
        )
        for s in skills_data.get("skills", []):
            op.execute(
                skills_table.insert().values(
                    id=s["skill_id"],
                    label=s["label"],
                    category=s["category"],
                    description=s.get("description"),
                    behavior_templates=json.dumps(s.get("behavior_templates", [])),
                    output_guidelines=json.dumps(s.get("output_guidelines", [])),
                )
            )
            for fam_id in s.get("allowed_families", []):
                op.execute(sf_table.insert().values(skill_id=s["skill_id"], family_id=fam_id))

    # 4. Migrate agent data
    conn = op.get_bind()

    # Migrate skills JSONB -> agent_skills rows
    agents = conn.execute(sa.text("SELECT id, skills FROM agent_definitions WHERE skills IS NOT NULL"))
    agent_skills_table = sa.table(
        "agent_skills",
        sa.column("agent_id", sa.String),
        sa.column("skill_id", sa.String),
    )
    for row in agents:
        agent_id = row[0]
        skills_json = row[1]
        if isinstance(skills_json, str):
            skills_list = json.loads(skills_json)
        else:
            skills_list = skills_json or []
        for skill_id in skills_list:
            sid = skill_id.strip()
            if sid:
                # Only insert if skill exists in skill_definitions (skip unknown)
                exists = conn.execute(
                    sa.text("SELECT 1 FROM skill_definitions WHERE id = :sid"), {"sid": sid}
                ).fetchone()
                if exists:
                    op.execute(agent_skills_table.insert().values(agent_id=agent_id, skill_id=sid))

    # 5. Rename family -> family_id on agent_definitions
    op.alter_column("agent_definitions", "family", new_column_name="family_id")

    # 6. Add FK constraint
    op.create_foreign_key(
        "fk_agent_family_id",
        "agent_definitions",
        "family_definitions",
        ["family_id"],
        ["id"],
    )

    # 7. Drop old skills JSONB column
    op.drop_column("agent_definitions", "skills")


def downgrade() -> None:
    # Re-add skills column
    op.add_column("agent_definitions", sa.Column("skills", JSONB(), nullable=True))

    # Populate skills from agent_skills join
    conn = op.get_bind()
    agents = conn.execute(sa.text("SELECT DISTINCT agent_id FROM agent_skills"))
    for row in agents:
        agent_id = row[0]
        skill_rows = conn.execute(
            sa.text("SELECT skill_id FROM agent_skills WHERE agent_id = :aid"),
            {"aid": agent_id},
        )
        skill_ids = [r[0] for r in skill_rows]
        conn.execute(
            sa.text("UPDATE agent_definitions SET skills = :skills WHERE id = :aid"),
            {"skills": json.dumps(skill_ids), "aid": agent_id},
        )

    # Drop FK, rename back
    op.drop_constraint("fk_agent_family_id", "agent_definitions", type_="foreignkey")
    op.alter_column("agent_definitions", "family_id", new_column_name="family")

    # Drop new tables (reverse order)
    op.drop_table("agent_skills")
    op.drop_table("skill_families")
    op.drop_table("skill_definitions")
    op.drop_table("family_definitions")
```

- [ ] **Step 2: Verify migration compiles**

Run: `cd /Users/mbensass/projetPreso/multiAgents/orkestra && python -c "import migrations.versions.004_families_skills_agent_skill"`
Expected: no import errors

- [ ] **Step 3: Commit**

```bash
git add migrations/versions/004_families_skills_agent_skill.py
git commit -m "feat: add migration 004 — family/skill tables + agent data migration"
```

---

## Task 4: Pydantic Schemas — Family + updated Skill + updated Agent

**Files:**
- Create: `app/schemas/family.py`
- Modify: `app/schemas/skill.py:1-80`
- Modify: `app/schemas/agent.py:1-164`

- [ ] **Step 1: Create `app/schemas/family.py`**

```python
"""Family schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import OrkBaseSchema


class FamilyCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class FamilyUpdate(OrkBaseSchema):
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None


class FamilyOut(OrkBaseSchema):
    id: str
    label: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class FamilyDetail(FamilyOut):
    """Family with associated skills."""
    skills: list["SkillOutBrief"] = Field(default_factory=list)
    agent_count: int = 0


class SkillOutBrief(OrkBaseSchema):
    """Minimal skill info for family detail."""
    skill_id: str
    label: str
    category: str
```

- [ ] **Step 2: Update `app/schemas/skill.py`**

Add `allowed_families`, `SkillCreate`, `SkillUpdate`, and `created_at/updated_at` to `SkillOut`:

```python
"""Skill schemas — first-class skill definitions backed by the database."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from app.schemas.common import OrkBaseSchema


class SkillContent(OrkBaseSchema):
    """The actual skill payload consumed by agents."""

    description: str
    behavior_templates: list[str] = Field(..., min_length=1)
    output_guidelines: list[str] = Field(..., min_length=1)


class SkillRef(OrkBaseSchema):
    """Minimal skill reference used in AgentOut.skills_resolved."""

    skill_id: str
    label: str
    category: str
    skills_content: SkillContent


class SkillCreate(OrkBaseSchema):
    """Input schema for creating a skill."""
    skill_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    label: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    behavior_templates: list[str] = Field(..., min_length=1)
    output_guidelines: list[str] = Field(..., min_length=1)
    allowed_families: list[str] = Field(..., min_length=1)


class SkillUpdate(OrkBaseSchema):
    """Input schema for updating a skill."""
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    behavior_templates: Optional[list[str]] = None
    output_guidelines: Optional[list[str]] = None
    allowed_families: Optional[list[str]] = None


class SkillOut(OrkBaseSchema):
    """Full skill as exposed by the API."""

    skill_id: str
    label: str
    category: str
    description: Optional[str] = None
    behavior_templates: list[str]
    output_guidelines: list[str]
    allowed_families: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentSummary(OrkBaseSchema):
    """Minimal agent info for skill->agents listing."""

    agent_id: str
    label: str


class SkillWithAgents(OrkBaseSchema):
    """Skill enriched with the list of agents that use it."""

    skill_id: str
    label: str
    category: str
    description: Optional[str] = None
    allowed_families: list[str] = Field(default_factory=list)
    agents: list[AgentSummary]


class SkillSeedEntry(OrkBaseSchema):
    """Schema for a single entry in skills.seed.json."""

    skill_id: str
    label: str
    category: str
    description: str
    behavior_templates: list[str] = Field(..., min_length=1)
    output_guidelines: list[str] = Field(..., min_length=1)
    allowed_families: list[str] = Field(default_factory=list)

    @field_validator("behavior_templates", "output_guidelines")
    @classmethod
    def reject_empty_lists(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("must be a non-empty list")
        return v


class SkillSeedPayload(OrkBaseSchema):
    """Root schema for skills.seed.json."""

    schema_version: int = Field(default=1)
    skills: list[SkillSeedEntry] = Field(..., min_length=1)
```

- [ ] **Step 3: Update `app/schemas/agent.py`**

Replace `family` with `family_id`, `skills` with `skill_ids`:

```python
"""Agent registry schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, Field

from app.schemas.common import OrkBaseSchema
from app.schemas.family import FamilyOut
from app.schemas.skill import SkillRef


class AgentCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    family_id: str = Field(..., min_length=1, max_length=50)
    purpose: str = Field(..., min_length=1)
    description: Optional[str] = None
    skill_ids: Optional[list[str]] = None
    selection_hints: Optional[dict[str, str | list[str] | bool]] = None
    allowed_mcps: Optional[list[str]] = None
    forbidden_effects: Optional[list[str]] = None
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: str = "medium"
    cost_profile: str = "medium"
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    prompt_content: Optional[str] = None
    skills_ref: Optional[str] = None
    skills_content: Optional[str] = None
    version: str = "1.0.0"
    status: str = "draft"
    owner: Optional[str] = None
    last_test_status: str = "not_tested"
    last_validated_at: Optional[datetime] = None
    usage_count: int = 0


class AgentUpdate(OrkBaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    family_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    purpose: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    skill_ids: Optional[list[str]] = None
    selection_hints: Optional[dict[str, str | list[str] | bool]] = None
    allowed_mcps: Optional[list[str]] = None
    forbidden_effects: Optional[list[str]] = None
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: Optional[str] = None
    cost_profile: Optional[str] = None
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    prompt_content: Optional[str] = None
    skills_ref: Optional[str] = None
    skills_content: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    last_test_status: Optional[str] = None
    last_validated_at: Optional[datetime] = None
    usage_count: Optional[int] = None


class AgentOut(OrkBaseSchema):
    id: str
    name: str
    family_id: str
    family: Optional[FamilyOut] = None
    purpose: str
    description: Optional[str]
    skill_ids: list[str] = Field(default_factory=list)
    skills_resolved: Optional[list[SkillRef]] = None
    selection_hints: Optional[dict[str, str | list[str] | bool]]
    allowed_mcps: Optional[list[str]]
    forbidden_effects: Optional[list[str]]
    input_contract_ref: Optional[str]
    output_contract_ref: Optional[str]
    criticality: str
    cost_profile: str
    limitations: Optional[list[str]]
    prompt_ref: Optional[str]
    prompt_content: Optional[str]
    skills_ref: Optional[str]
    skills_content: Optional[str]
    version: str
    status: str
    owner: Optional[str]
    last_test_status: str
    last_validated_at: Optional[datetime]
    usage_count: int
    created_at: datetime
    updated_at: datetime


class AgentStatusUpdate(OrkBaseSchema):
    status: str
    reason: Optional[str] = None


class AgentRegistryStats(OrkBaseSchema):
    total_agents: int
    active_agents: int
    tested_agents: int
    deprecated_agents: int
    current_workflow_agents: int


class McpCatalogSummary(OrkBaseSchema):
    id: str
    name: str
    purpose: str
    effect_type: str
    criticality: str
    approval_required: bool = False
    obot_state: str
    orkestra_state: str


class AgentGenerationRequest(OrkBaseSchema):
    intent: str = Field(..., min_length=10)
    use_case: Optional[str] = None
    target_workflow: Optional[str] = None
    criticality_target: Optional[str] = None
    preferred_family: Optional[str] = None
    preferred_output_style: Optional[str] = None
    preferred_mcp_scope: Optional[str] = None
    constraints: Optional[str] = None
    owner: Optional[str] = None


class GeneratedAgentDraft(OrkBaseSchema):
    agent_id: str = Field(..., validation_alias=AliasChoices("agent_id", "id"))
    name: str
    family_id: str = Field(..., validation_alias=AliasChoices("family_id", "family"))
    purpose: str
    description: str
    skill_ids: list[str] = Field(default_factory=list, validation_alias=AliasChoices("skill_ids", "skills"))
    selection_hints: dict[str, str | list[str] | bool]
    allowed_mcps: list[str]
    forbidden_effects: list[str]
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: str
    cost_profile: str
    limitations: list[str]
    prompt_content: str
    skills_content: str
    owner: Optional[str] = None
    version: str = "1.0.0"
    status: str = "draft"
    suggested_missing_mcps: list[str] = Field(default_factory=list)
    mcp_rationale: dict[str, str] = Field(default_factory=dict)


class AgentGenerationResponse(OrkBaseSchema):
    draft: GeneratedAgentDraft
    available_mcps: list[McpCatalogSummary]
    source: str


class SaveGeneratedDraftRequest(OrkBaseSchema):
    draft: GeneratedAgentDraft
```

- [ ] **Step 4: Commit**

```bash
git add app/schemas/family.py app/schemas/skill.py app/schemas/agent.py
git commit -m "feat: add family schemas, update skill/agent schemas for DB-backed model"
```

---

## Task 5: Seed Service — idempotent bootstrap from JSON

**Files:**
- Create: `app/services/seed_service.py`

- [ ] **Step 1: Create seed service**

```python
"""Seed service — idempotent bootstrap from JSON files into DB."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import FamilyDefinition, SkillFamily
from app.models.skill import SkillDefinition

logger = logging.getLogger("orkestra.seed")

CONFIG_DIR = Path(__file__).parent.parent / "config"


async def seed_all(db: AsyncSession) -> None:
    """Run the full idempotent seed: families first, then skills."""
    f_created, f_updated = await _seed_families(db)
    s_created, s_updated = await _seed_skills(db)
    await db.commit()
    logger.info(
        f"Seed complete — families: {f_created} created, {f_updated} updated | "
        f"skills: {s_created} created, {s_updated} updated"
    )


async def _seed_families(db: AsyncSession) -> tuple[int, int]:
    path = CONFIG_DIR / "families.seed.json"
    if not path.exists():
        logger.warning(f"families.seed.json not found at {path}, skipping family seed")
        return 0, 0

    data = json.loads(path.read_text(encoding="utf-8"))
    created, updated = 0, 0

    for entry in data.get("families", []):
        fid = entry["family_id"]
        existing = await db.get(FamilyDefinition, fid)
        if existing:
            existing.label = entry["label"]
            existing.description = entry.get("description")
            updated += 1
        else:
            db.add(FamilyDefinition(
                id=fid,
                label=entry["label"],
                description=entry.get("description"),
            ))
            created += 1

    await db.flush()
    return created, updated


async def _seed_skills(db: AsyncSession) -> tuple[int, int]:
    path = CONFIG_DIR / "skills.seed.json"
    if not path.exists():
        logger.warning(f"skills.seed.json not found at {path}, skipping skill seed")
        return 0, 0

    data = json.loads(path.read_text(encoding="utf-8"))
    created, updated = 0, 0

    for entry in data.get("skills", []):
        sid = entry["skill_id"]
        existing = await db.get(SkillDefinition, sid)
        if existing:
            existing.label = entry["label"]
            existing.category = entry["category"]
            existing.description = entry.get("description")
            existing.behavior_templates = entry.get("behavior_templates", [])
            existing.output_guidelines = entry.get("output_guidelines", [])
            updated += 1
        else:
            db.add(SkillDefinition(
                id=sid,
                label=entry["label"],
                category=entry["category"],
                description=entry.get("description"),
                behavior_templates=entry.get("behavior_templates", []),
                output_guidelines=entry.get("output_guidelines", []),
            ))
            created += 1

        await db.flush()

        # Sync SkillFamily entries
        allowed = set(entry.get("allowed_families", []))
        existing_sf = await db.execute(
            select(SkillFamily).where(SkillFamily.skill_id == sid)
        )
        current_families = {sf.family_id for sf in existing_sf.scalars().all()}

        # Remove families no longer in allowed
        to_remove = current_families - allowed
        if to_remove:
            await db.execute(
                delete(SkillFamily).where(
                    SkillFamily.skill_id == sid,
                    SkillFamily.family_id.in_(to_remove),
                )
            )

        # Add new families
        to_add = allowed - current_families
        for fam_id in to_add:
            db.add(SkillFamily(skill_id=sid, family_id=fam_id))

    await db.flush()
    return created, updated
```

- [ ] **Step 2: Commit**

```bash
git add app/services/seed_service.py
git commit -m "feat: add idempotent seed service for families and skills"
```

---

## Task 6: Family Service — CRUD

**Files:**
- Create: `app/services/family_service.py`

- [ ] **Step 1: Create family service**

```python
"""Family service — CRUD with business guards."""

from __future__ import annotations

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.family import FamilyDefinition, SkillFamily, AgentSkill
from app.models.registry import AgentDefinition
from app.schemas.family import FamilyCreate, FamilyUpdate

logger = logging.getLogger("orkestra.families")


async def list_families(db: AsyncSession) -> list[FamilyDefinition]:
    result = await db.execute(
        select(FamilyDefinition).order_by(FamilyDefinition.label)
    )
    return list(result.scalars().all())


async def get_family(db: AsyncSession, family_id: str) -> FamilyDefinition | None:
    return await db.get(FamilyDefinition, family_id)


async def get_family_detail(db: AsyncSession, family_id: str) -> dict | None:
    """Get family with associated skills and agent count."""
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        return None

    # Get skills for this family via SkillFamily join
    from app.models.skill import SkillDefinition
    result = await db.execute(
        select(SkillDefinition)
        .join(SkillFamily, SkillFamily.skill_id == SkillDefinition.id)
        .where(SkillFamily.family_id == family_id)
        .order_by(SkillDefinition.label)
    )
    skills = list(result.scalars().all())

    # Count agents in this family
    agent_count_result = await db.execute(
        select(func.count()).select_from(AgentDefinition).where(AgentDefinition.family_id == family_id)
    )
    agent_count = agent_count_result.scalar() or 0

    return {
        "id": family.id,
        "label": family.label,
        "description": family.description,
        "created_at": family.created_at,
        "updated_at": family.updated_at,
        "skills": [{"skill_id": s.id, "label": s.label, "category": s.category} for s in skills],
        "agent_count": agent_count,
    }


async def create_family(db: AsyncSession, data: FamilyCreate) -> FamilyDefinition:
    existing = await db.get(FamilyDefinition, data.id)
    if existing:
        raise ValueError(f"Family '{data.id}' already exists")

    family = FamilyDefinition(
        id=data.id,
        label=data.label,
        description=data.description,
    )
    db.add(family)
    await db.flush()
    return family


async def update_family(db: AsyncSession, family_id: str, data: FamilyUpdate) -> FamilyDefinition:
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise ValueError(f"Family '{family_id}' not found")

    updates = data.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(family, field, value)

    await db.flush()
    return family


async def delete_family(db: AsyncSession, family_id: str) -> None:
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise ValueError(f"Family '{family_id}' not found")

    # Guard: check agents using this family
    agent_result = await db.execute(
        select(AgentDefinition.id, AgentDefinition.name)
        .where(AgentDefinition.family_id == family_id)
        .limit(10)
    )
    agents = agent_result.all()
    if agents:
        names = ", ".join(f"{a.name} ({a.id})" for a in agents)
        raise ValueError(f"Cannot delete family '{family_id}': used by agents: {names}")

    # Guard: check skills referencing this family
    sf_result = await db.execute(
        select(SkillFamily.skill_id).where(SkillFamily.family_id == family_id).limit(10)
    )
    skill_ids = [row[0] for row in sf_result.all()]
    if skill_ids:
        raise ValueError(
            f"Cannot delete family '{family_id}': referenced by skills: {', '.join(skill_ids)}"
        )

    await db.delete(family)
    await db.flush()
```

- [ ] **Step 2: Commit**

```bash
git add app/services/family_service.py
git commit -m "feat: add family service with CRUD and deletion guards"
```

---

## Task 7: Skill Service — CRUD (replaces skill_registry_service)

**Files:**
- Create: `app/services/skill_service.py`

- [ ] **Step 1: Create skill service**

```python
"""Skill service — DB-backed CRUD, replaces skill_registry_service."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import SkillFamily, AgentSkill
from app.models.registry import AgentDefinition
from app.models.skill import SkillDefinition
from app.schemas.skill import SkillContent, SkillCreate, SkillRef, SkillUpdate

logger = logging.getLogger("orkestra.skills")


async def list_skills(db: AsyncSession) -> list[dict]:
    """Return all skills with allowed_families."""
    result = await db.execute(select(SkillDefinition).order_by(SkillDefinition.label))
    skills = list(result.scalars().all())
    out = []
    for s in skills:
        families = await _get_allowed_families(db, s.id)
        out.append(_skill_to_dict(s, families))
    return out


async def get_skill(db: AsyncSession, skill_id: str) -> dict | None:
    skill = await db.get(SkillDefinition, skill_id)
    if not skill:
        return None
    families = await _get_allowed_families(db, skill_id)
    return _skill_to_dict(skill, families)


async def get_skills_for_family(db: AsyncSession, family_id: str) -> list[dict]:
    """Return skills allowed for a given family."""
    result = await db.execute(
        select(SkillDefinition)
        .join(SkillFamily, SkillFamily.skill_id == SkillDefinition.id)
        .where(SkillFamily.family_id == family_id)
        .order_by(SkillDefinition.label)
    )
    skills = list(result.scalars().all())
    out = []
    for s in skills:
        families = await _get_allowed_families(db, s.id)
        out.append(_skill_to_dict(s, families))
    return out


async def create_skill(db: AsyncSession, data: SkillCreate) -> dict:
    existing = await db.get(SkillDefinition, data.skill_id)
    if existing:
        raise ValueError(f"Skill '{data.skill_id}' already exists")

    # Validate allowed_families exist
    await _validate_family_ids(db, data.allowed_families)

    skill = SkillDefinition(
        id=data.skill_id,
        label=data.label,
        category=data.category,
        description=data.description,
        behavior_templates=data.behavior_templates,
        output_guidelines=data.output_guidelines,
    )
    db.add(skill)
    await db.flush()

    # Insert SkillFamily entries
    for fam_id in data.allowed_families:
        db.add(SkillFamily(skill_id=data.skill_id, family_id=fam_id))
    await db.flush()

    return _skill_to_dict(skill, data.allowed_families)


async def update_skill(db: AsyncSession, skill_id: str, data: SkillUpdate) -> dict:
    skill = await db.get(SkillDefinition, skill_id)
    if not skill:
        raise ValueError(f"Skill '{skill_id}' not found")

    updates = data.model_dump(exclude_none=True)

    # Handle allowed_families separately
    new_families = updates.pop("allowed_families", None)

    # Update scalar fields
    for field, value in updates.items():
        setattr(skill, field, value)

    # Sync allowed_families if provided
    if new_families is not None:
        await _validate_family_ids(db, new_families)

        # Check if removing a family would break existing agents
        current_families = set(await _get_allowed_families(db, skill_id))
        removed_families = current_families - set(new_families)
        if removed_families:
            # Check if any agents with those families use this skill
            for fam_id in removed_families:
                result = await db.execute(
                    select(AgentDefinition.id, AgentDefinition.name)
                    .join(AgentSkill, AgentSkill.agent_id == AgentDefinition.id)
                    .where(AgentSkill.skill_id == skill_id, AgentDefinition.family_id == fam_id)
                    .limit(5)
                )
                conflicting = result.all()
                if conflicting:
                    names = ", ".join(f"{a.name} ({a.id})" for a in conflicting)
                    raise ValueError(
                        f"Cannot remove family '{fam_id}' from skill '{skill_id}': "
                        f"used by agents in that family: {names}"
                    )

        # Sync
        await db.execute(delete(SkillFamily).where(SkillFamily.skill_id == skill_id))
        for fam_id in new_families:
            db.add(SkillFamily(skill_id=skill_id, family_id=fam_id))

    await db.flush()

    # Regenerate skills_content for agents using this skill
    await _cascade_skills_content(db, skill_id)

    families = await _get_allowed_families(db, skill_id)
    return _skill_to_dict(skill, families)


async def delete_skill(db: AsyncSession, skill_id: str) -> None:
    skill = await db.get(SkillDefinition, skill_id)
    if not skill:
        raise ValueError(f"Skill '{skill_id}' not found")

    # Guard: check agents using this skill
    result = await db.execute(
        select(AgentDefinition.id, AgentDefinition.name)
        .join(AgentSkill, AgentSkill.agent_id == AgentDefinition.id)
        .where(AgentSkill.skill_id == skill_id)
        .limit(10)
    )
    agents = result.all()
    if agents:
        names = ", ".join(f"{a.name} ({a.id})" for a in agents)
        raise ValueError(f"Cannot delete skill '{skill_id}': used by agents: {names}")

    await db.delete(skill)
    await db.flush()


async def resolve_skills(db: AsyncSession, skill_ids: list[str]) -> tuple[list[SkillRef], list[str]]:
    """Validate and resolve skill_ids against the DB."""
    resolved: list[SkillRef] = []
    unresolved: list[str] = []
    for sid in skill_ids:
        skill = await db.get(SkillDefinition, sid)
        if not skill:
            unresolved.append(sid)
            continue
        resolved.append(SkillRef(
            skill_id=skill.id,
            label=skill.label,
            category=skill.category,
            skills_content=SkillContent(
                description=skill.description or "",
                behavior_templates=skill.behavior_templates or [],
                output_guidelines=skill.output_guidelines or [],
            ),
        ))
    return resolved, unresolved


async def build_skills_content(db: AsyncSession, skill_ids: list[str]) -> str:
    """Build the JSON string stored in AgentDefinition.skills_content."""
    resolved, _ = await resolve_skills(db, skill_ids)
    content = {
        ref.skill_id: {
            "description": ref.skills_content.description,
            "behavior_templates": ref.skills_content.behavior_templates,
            "output_guidelines": ref.skills_content.output_guidelines,
        }
        for ref in resolved
    }
    return json.dumps(content, indent=2)


async def validate_skills_for_family(
    db: AsyncSession, skill_ids: list[str], family_id: str
) -> list[str]:
    """Return list of skill_ids that are NOT allowed for the given family."""
    incompatible = []
    for sid in skill_ids:
        result = await db.execute(
            select(SkillFamily).where(
                SkillFamily.skill_id == sid,
                SkillFamily.family_id == family_id,
            )
        )
        if not result.scalar_one_or_none():
            incompatible.append(sid)
    return incompatible


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

async def _get_allowed_families(db: AsyncSession, skill_id: str) -> list[str]:
    result = await db.execute(
        select(SkillFamily.family_id).where(SkillFamily.skill_id == skill_id)
    )
    return [row[0] for row in result.all()]


async def _validate_family_ids(db: AsyncSession, family_ids: list[str]) -> None:
    from app.models.family import FamilyDefinition
    for fid in family_ids:
        if not await db.get(FamilyDefinition, fid):
            raise ValueError(f"Family '{fid}' not found")


async def _cascade_skills_content(db: AsyncSession, skill_id: str) -> None:
    """Regenerate skills_content for all agents using this skill."""
    result = await db.execute(
        select(AgentDefinition)
        .join(AgentSkill, AgentSkill.agent_id == AgentDefinition.id)
        .where(AgentSkill.skill_id == skill_id)
    )
    agents = list(result.scalars().all())
    for agent in agents:
        # Get all skill_ids for this agent
        sk_result = await db.execute(
            select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent.id)
        )
        all_skill_ids = [row[0] for row in sk_result.all()]
        agent.skills_content = await build_skills_content(db, all_skill_ids)
    await db.flush()


def _skill_to_dict(skill: SkillDefinition, families: list[str]) -> dict:
    return {
        "skill_id": skill.id,
        "label": skill.label,
        "category": skill.category,
        "description": skill.description,
        "behavior_templates": skill.behavior_templates or [],
        "output_guidelines": skill.output_guidelines or [],
        "allowed_families": families,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }
```

- [ ] **Step 2: Commit**

```bash
git add app/services/skill_service.py
git commit -m "feat: add DB-backed skill service with CRUD and compatibility guards"
```

---

## Task 8: Refactor Agent Registry Service

**Files:**
- Modify: `app/services/agent_registry_service.py:1-390`

- [ ] **Step 1: Rewrite agent_registry_service.py**

Replace all references to `skill_registry_service` with DB-backed `skill_service`. Replace `family`/`skills` field handling with `family_id`/`skill_ids` + join tables.

```python
"""Agent registry service — governed CRUD, filters, stats and draft save."""

from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import AgentSkill, FamilyDefinition
from app.models.registry import AgentDefinition
from app.schemas.agent import (
    AgentCreate,
    AgentRegistryStats,
    AgentUpdate,
    GeneratedAgentDraft,
)
from app.services import obot_catalog_service, skill_service
from app.services.event_service import emit_event
from app.state_machines.agent_lifecycle_sm import AgentLifecycleStateMachine


_AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,99}$")


def _dedupe_str_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = raw.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


async def validate_agent_definition(db: "AsyncSession", data: AgentCreate) -> list[str]:
    errors: list[str] = []

    if not _AGENT_ID_RE.match(data.id):
        errors.append("id must match ^[a-z0-9][a-z0-9_-]{1,99}$")
    if not data.name or len(data.name.strip()) < 2:
        errors.append("name must be at least 2 characters")
    if not data.purpose or len(data.purpose.strip()) < 10:
        errors.append("purpose must be at least 10 characters")

    if data.prompt_content is not None and not data.prompt_content.strip():
        errors.append("prompt_content cannot be empty when provided")
    if data.skills_content is not None and not data.skills_content.strip():
        errors.append("skills_content cannot be empty when provided")

    # Validate family_id exists in DB
    family = await db.get(FamilyDefinition, data.family_id)
    if not family:
        errors.append(f"family_id '{data.family_id}' not found")

    # Validate skill_ids exist in DB
    if data.skill_ids:
        _, unresolved = await skill_service.resolve_skills(db, data.skill_ids)
        for sid in unresolved:
            errors.append(f"agent references unknown skill_id: '{sid}'")

        # Validate skills are compatible with the family
        if family:
            incompatible = await skill_service.validate_skills_for_family(
                db, data.skill_ids, data.family_id
            )
            for sid in incompatible:
                errors.append(f"skill '{sid}' is not allowed for family '{data.family_id}'")

    return errors


async def _sync_agent_skills(db: "AsyncSession", agent_id: str, skill_ids: list[str]) -> None:
    """Replace all AgentSkill rows for an agent."""
    await db.execute(delete(AgentSkill).where(AgentSkill.agent_id == agent_id))
    for sid in skill_ids:
        db.add(AgentSkill(agent_id=agent_id, skill_id=sid))
    await db.flush()


async def _get_agent_skill_ids(db: "AsyncSession", agent_id: str) -> list[str]:
    result = await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent_id)
    )
    return [row[0] for row in result.all()]


async def _apply_create_payload(db: "AsyncSession", agent: AgentDefinition, payload: AgentCreate) -> None:
    agent.name = payload.name
    agent.family_id = payload.family_id
    agent.purpose = payload.purpose
    agent.description = payload.description
    agent.selection_hints = payload.selection_hints
    agent.allowed_mcps = _dedupe_str_list(payload.allowed_mcps)
    agent.forbidden_effects = _dedupe_str_list(payload.forbidden_effects)
    agent.input_contract_ref = payload.input_contract_ref
    agent.output_contract_ref = payload.output_contract_ref
    agent.criticality = payload.criticality
    agent.cost_profile = payload.cost_profile
    agent.limitations = _dedupe_str_list(payload.limitations)
    agent.prompt_ref = payload.prompt_ref
    agent.prompt_content = payload.prompt_content
    agent.skills_ref = payload.skills_ref

    # Auto-generate skills_content from resolved skill_ids if not explicitly provided
    skill_ids = _dedupe_str_list(payload.skill_ids)
    if skill_ids and not payload.skills_content:
        agent.skills_content = await skill_service.build_skills_content(db, skill_ids)
    else:
        agent.skills_content = payload.skills_content

    agent.version = payload.version
    agent.status = payload.status
    agent.owner = payload.owner
    agent.last_test_status = payload.last_test_status
    agent.last_validated_at = payload.last_validated_at
    agent.usage_count = payload.usage_count


async def create_agent(db: "AsyncSession", data: AgentCreate) -> AgentDefinition:
    errors = await validate_agent_definition(db, data)
    if errors:
        raise ValueError(f"Validation errors: {'; '.join(errors)}")

    existing = await db.get(AgentDefinition, data.id)
    if existing:
        raise ValueError(f"Agent {data.id} already exists")

    agent = AgentDefinition(id=data.id)
    await _apply_create_payload(db, agent, data)
    db.add(agent)
    await db.flush()

    # Sync AgentSkill join rows
    skill_ids = _dedupe_str_list(data.skill_ids)
    await _sync_agent_skills(db, agent.id, skill_ids)

    await emit_event(
        db,
        "agent.registered",
        "system",
        "agent_registry",
        payload={"agent_id": agent.id, "status": agent.status},
    )
    return agent


async def update_agent(db: "AsyncSession", agent_id: str, data: AgentUpdate) -> AgentDefinition:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    updates = data.model_dump(exclude_none=True)
    if "name" in updates and len(updates["name"].strip()) < 2:
        raise ValueError("name must be at least 2 characters")
    if "purpose" in updates and len(updates["purpose"].strip()) < 10:
        raise ValueError("purpose must be at least 10 characters")

    new_family_id = updates.pop("family_id", None)
    new_skill_ids = updates.pop("skill_ids", None)

    # Determine effective family_id and skill_ids
    effective_family_id = new_family_id or agent.family_id
    effective_skill_ids = (
        _dedupe_str_list(new_skill_ids) if new_skill_ids is not None
        else await _get_agent_skill_ids(db, agent_id)
    )

    # Validate family exists
    if new_family_id:
        family = await db.get(FamilyDefinition, new_family_id)
        if not family:
            raise ValueError(f"family_id '{new_family_id}' not found")
        agent.family_id = new_family_id

    # Validate skill_ids
    if new_skill_ids is not None:
        _, unresolved = await skill_service.resolve_skills(db, effective_skill_ids)
        if unresolved:
            raise ValueError(f"agent references unknown skill_ids: {unresolved}")

    # Validate compatibility
    if new_family_id or new_skill_ids is not None:
        incompatible = await skill_service.validate_skills_for_family(
            db, effective_skill_ids, effective_family_id
        )
        if incompatible:
            raise ValueError(
                f"skills incompatible with family '{effective_family_id}': {incompatible}"
            )

    # Apply scalar updates
    list_fields = {"allowed_mcps", "forbidden_effects", "limitations"}
    for field, value in updates.items():
        if field in list_fields:
            setattr(agent, field, _dedupe_str_list(value))
            continue
        if field in {"prompt_content", "skills_content"} and isinstance(value, str):
            if not value.strip():
                raise ValueError(f"{field} cannot be empty")
        setattr(agent, field, value)

    # Sync skill join table + regenerate skills_content
    if new_skill_ids is not None or new_family_id:
        await _sync_agent_skills(db, agent_id, effective_skill_ids)
        if effective_skill_ids:
            agent.skills_content = await skill_service.build_skills_content(db, effective_skill_ids)

    await db.flush()
    await emit_event(
        db,
        "agent.updated",
        "system",
        "agent_registry",
        payload={"agent_id": agent.id},
    )
    return agent


async def update_agent_status(
    db: "AsyncSession",
    agent_id: str,
    new_status: str,
    reason: str = "",
) -> AgentDefinition:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    sm = AgentLifecycleStateMachine(agent.status)
    if not sm.transition(new_status, reason=reason):
        raise ValueError(f"Cannot transition agent from {agent.status} to {new_status}")
    agent.status = sm.state
    await emit_event(
        db,
        f"agent.{new_status}",
        "system",
        "agent_registry",
        payload={"agent_id": agent.id},
    )
    return agent


def _workflow_matches(agent: AgentDefinition, workflow_id: str) -> bool:
    hints = agent.selection_hints or {}
    if not isinstance(hints, dict):
        return False
    for key in ("workflow_ids", "preferred_workflows", "allowed_workflows"):
        value = hints.get(key)
        if isinstance(value, list) and workflow_id in value:
            return True
        if isinstance(value, str) and workflow_id == value:
            return True
    return False


def _matches_text(agent: AgentDefinition, q: str) -> bool:
    haystacks = [
        agent.id,
        agent.name,
        agent.family_id,
        agent.purpose,
        agent.description or "",
        " ".join(agent.allowed_mcps or []),
    ]
    low_q = q.lower()
    return any(low_q in h.lower() for h in haystacks)


async def list_agents(
    db: "AsyncSession",
    *,
    family: str | None = None,
    status: str | None = None,
    criticality: str | None = None,
    cost_profile: str | None = None,
    q: str | None = None,
    mcp_id: str | None = None,
    workflow_id: str | None = None,
    used_in_workflow_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentDefinition]:
    stmt = select(AgentDefinition)
    if family and family != "all":
        stmt = stmt.where(AgentDefinition.family_id == family)
    if status and status != "all":
        stmt = stmt.where(AgentDefinition.status == status)
    if criticality and criticality != "all":
        stmt = stmt.where(AgentDefinition.criticality == criticality)
    if cost_profile and cost_profile != "all":
        stmt = stmt.where(AgentDefinition.cost_profile == cost_profile)

    result = await db.execute(stmt.order_by(AgentDefinition.name))
    items = list(result.scalars().all())

    if q:
        items = [a for a in items if _matches_text(a, q)]
    if mcp_id:
        items = [a for a in items if mcp_id in (a.allowed_mcps or [])]
    if used_in_workflow_only and workflow_id:
        items = [a for a in items if _workflow_matches(a, workflow_id)]

    return items[offset : offset + limit]


async def get_agent(db: "AsyncSession", agent_id: str) -> AgentDefinition | None:
    return await db.get(AgentDefinition, agent_id)


async def delete_agent(db: "AsyncSession", agent_id: str) -> None:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    if agent.status == "active":
        raise ValueError("Cannot delete an active agent. Disable or deprecate it first.")

    await db.delete(agent)
    await db.flush()
    await emit_event(
        db,
        "agent.deleted",
        "system",
        "agent_registry",
        payload={"agent_id": agent_id},
    )


async def get_registry_stats(db: "AsyncSession", workflow_id: str | None = None) -> AgentRegistryStats:
    result = await db.execute(select(AgentDefinition))
    items = list(result.scalars().all())
    tested_like_status = {"tested", "registered", "active", "deprecated", "disabled", "archived"}

    current_workflow_agents = 0
    if workflow_id:
        current_workflow_agents = sum(1 for a in items if _workflow_matches(a, workflow_id))

    return AgentRegistryStats(
        total_agents=len(items),
        active_agents=sum(1 for a in items if a.status == "active"),
        tested_agents=sum(
            1
            for a in items
            if a.status in tested_like_status or (a.last_test_status and a.last_test_status != "not_tested")
        ),
        deprecated_agents=sum(1 for a in items if a.status == "deprecated"),
        current_workflow_agents=current_workflow_agents,
    )


async def available_mcp_summaries(db: "AsyncSession") -> list[dict[str, str | bool]]:
    items = await obot_catalog_service.list_catalog_items(db)
    return [
        {
            "id": item.obot_server.id,
            "name": item.obot_server.name,
            "purpose": item.obot_server.purpose,
            "effect_type": item.obot_server.effect_type,
            "criticality": item.obot_server.criticality,
            "approval_required": item.obot_server.approval_required,
            "obot_state": item.obot_state,
            "orkestra_state": item.orkestra_state,
        }
        for item in items
    ]


async def enrich_agent(db: "AsyncSession", agent: AgentDefinition) -> dict:
    """Build an enriched dict with family object, skill_ids, and skills_resolved."""
    skill_ids = await _get_agent_skill_ids(db, agent.id)
    resolved, _ = await skill_service.resolve_skills(db, skill_ids)
    family = await db.get(FamilyDefinition, agent.family_id)

    return {
        "id": agent.id,
        "name": agent.name,
        "family_id": agent.family_id,
        "family": {
            "id": family.id,
            "label": family.label,
            "description": family.description,
            "created_at": family.created_at,
            "updated_at": family.updated_at,
        } if family else None,
        "purpose": agent.purpose,
        "description": agent.description,
        "skill_ids": skill_ids,
        "skills_resolved": resolved,
        "selection_hints": agent.selection_hints,
        "allowed_mcps": agent.allowed_mcps,
        "forbidden_effects": agent.forbidden_effects,
        "input_contract_ref": agent.input_contract_ref,
        "output_contract_ref": agent.output_contract_ref,
        "criticality": agent.criticality,
        "cost_profile": agent.cost_profile,
        "limitations": agent.limitations,
        "prompt_ref": agent.prompt_ref,
        "prompt_content": agent.prompt_content,
        "skills_ref": agent.skills_ref,
        "skills_content": agent.skills_content,
        "version": agent.version,
        "status": agent.status,
        "owner": agent.owner,
        "last_test_status": agent.last_test_status,
        "last_validated_at": agent.last_validated_at,
        "usage_count": agent.usage_count,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


async def save_generated_draft(db: "AsyncSession", draft: GeneratedAgentDraft) -> AgentDefinition:
    errors: list[str] = []

    if draft.status not in {"draft", "designed"}:
        errors.append("status must be draft or designed")
    if not _AGENT_ID_RE.match(draft.agent_id):
        errors.append("agent_id format is invalid")
    if not draft.name.strip():
        errors.append("name is required")
    if not draft.purpose.strip():
        errors.append("purpose is required")
    if not draft.skill_ids:
        errors.append("at least one skill is required")
    if not draft.prompt_content.strip():
        errors.append("prompt_content is required")
    if not draft.skills_content.strip():
        errors.append("skills_content is required")
    if not draft.limitations:
        errors.append("at least one limitation is required")

    available_mcps = await available_mcp_summaries(db)
    available_ids = {str(m["id"]) for m in available_mcps}
    unknown_mcps = [m for m in draft.allowed_mcps if m not in available_ids]
    if unknown_mcps:
        errors.append(f"allowed_mcps contain unknown ids: {', '.join(unknown_mcps)}")

    if errors:
        raise ValueError(f"Draft validation errors: {'; '.join(errors)}")

    payload = AgentCreate(
        id=draft.agent_id,
        name=draft.name,
        family_id=draft.family_id,
        purpose=draft.purpose,
        description=draft.description,
        skill_ids=draft.skill_ids,
        selection_hints=draft.selection_hints,
        allowed_mcps=draft.allowed_mcps,
        forbidden_effects=draft.forbidden_effects,
        input_contract_ref=draft.input_contract_ref,
        output_contract_ref=draft.output_contract_ref,
        criticality=draft.criticality,
        cost_profile=draft.cost_profile,
        limitations=draft.limitations,
        prompt_content=draft.prompt_content,
        skills_content=draft.skills_content,
        owner=draft.owner,
        version=draft.version,
        status="draft" if draft.status == "designed" else draft.status,
    )

    return await create_agent(db, payload)
```

- [ ] **Step 2: Commit**

```bash
git add app/services/agent_registry_service.py
git commit -m "feat: refactor agent registry service for DB-backed families and skills"
```

---

## Task 9: API Routes — Families

**Files:**
- Create: `app/api/routes/families.py`

- [ ] **Step 1: Create families route**

```python
"""Family API routes — CRUD for agent families."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.family import FamilyCreate, FamilyDetail, FamilyOut, FamilyUpdate
from app.services import family_service

router = APIRouter()


@router.get("", response_model=list[FamilyOut])
async def list_families(db: AsyncSession = Depends(get_db)):
    return await family_service.list_families(db)


@router.get("/{family_id}", response_model=FamilyDetail)
async def get_family(family_id: str, db: AsyncSession = Depends(get_db)):
    detail = await family_service.get_family_detail(db, family_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Family '{family_id}' not found")
    return detail


@router.post("", response_model=FamilyOut, status_code=201)
async def create_family(data: FamilyCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await family_service.create_family(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{family_id}", response_model=FamilyOut)
async def update_family(family_id: str, data: FamilyUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await family_service.update_family(db, family_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_family(family_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await family_service.delete_family(db, family_id)
    except ValueError as exc:
        if "Cannot delete" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 2: Commit**

```bash
git add app/api/routes/families.py
git commit -m "feat: add family CRUD API routes"
```

---

## Task 10: API Routes — Skills (rework)

**Files:**
- Modify: `app/api/routes/skills.py:1-67`

- [ ] **Step 1: Rewrite skills routes for DB-backed service**

```python
"""Skills API routes — DB-backed CRUD for skill definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.skill import (
    AgentSummary,
    SkillCreate,
    SkillOut,
    SkillUpdate,
    SkillWithAgents,
)
from app.services import skill_service
from app.services import agent_registry_service

router = APIRouter()


@router.get("/by-family/{family_id}", response_model=list[SkillOut])
async def list_skills_by_family(family_id: str, db: AsyncSession = Depends(get_db)):
    """Return skills allowed for a given family."""
    return await skill_service.get_skills_for_family(db, family_id)


@router.get("/with-agents", response_model=list[SkillWithAgents])
async def list_skills_with_agents(db: AsyncSession = Depends(get_db)):
    """Return all skills enriched with the agents that reference each skill."""
    from app.models.family import AgentSkill
    from app.models.registry import AgentDefinition
    from sqlalchemy import select

    all_skills = await skill_service.list_skills(db)

    # Build skill_id -> list of AgentSummary
    skill_agent_map: dict[str, list[AgentSummary]] = {s["skill_id"]: [] for s in all_skills}

    result = await db.execute(
        select(AgentSkill.skill_id, AgentDefinition.id, AgentDefinition.name)
        .join(AgentDefinition, AgentSkill.agent_id == AgentDefinition.id)
    )
    for skill_id, agent_id, agent_name in result.all():
        if skill_id in skill_agent_map:
            skill_agent_map[skill_id].append(AgentSummary(agent_id=agent_id, label=agent_name))

    return [
        SkillWithAgents(
            skill_id=s["skill_id"],
            label=s["label"],
            category=s["category"],
            description=s.get("description"),
            allowed_families=s.get("allowed_families", []),
            agents=skill_agent_map.get(s["skill_id"], []),
        )
        for s in all_skills
    ]


@router.get("", response_model=list[SkillOut])
async def list_skills(db: AsyncSession = Depends(get_db)):
    """Return all registered skills."""
    return await skill_service.list_skills(db)


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    """Return a single skill by skill_id."""
    skill = await skill_service.get_skill(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return skill


@router.post("", response_model=SkillOut, status_code=201)
async def create_skill(data: SkillCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await skill_service.create_skill(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{skill_id}", response_model=SkillOut)
async def update_skill(skill_id: str, data: SkillUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await skill_service.update_skill(db, skill_id, data)
    except ValueError as exc:
        if "Cannot remove" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await skill_service.delete_skill(db, skill_id)
    except ValueError as exc:
        if "Cannot delete" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Note: path routes with fixed segments (`/by-family/{family_id}`, `/with-agents`) must come BEFORE the `/{skill_id}` catch-all route to avoid routing conflicts.

- [ ] **Step 2: Commit**

```bash
git add app/api/routes/skills.py
git commit -m "feat: rework skills API routes for DB-backed CRUD"
```

---

## Task 11: API Routes — Agents (adapt)

**Files:**
- Modify: `app/api/routes/agents.py:1-138`

- [ ] **Step 1: Update agents routes**

Key changes: use `enrich_agent()` for GET, accept `family_id` filter param, handle 409 on delete guards.

```python
"""Agent Registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent import (
    AgentCreate,
    AgentGenerationRequest,
    AgentGenerationResponse,
    AgentOut,
    AgentRegistryStats,
    AgentStatusUpdate,
    AgentUpdate,
    McpCatalogSummary,
    SaveGeneratedDraftRequest,
)
from app.services import agent_generation_service, agent_registry_service

router = APIRouter()


@router.get("/stats", response_model=AgentRegistryStats)
async def get_agent_registry_stats(
    workflow_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await agent_registry_service.get_registry_stats(db, workflow_id=workflow_id)


@router.get("/available-skills")
async def get_available_skills(db: AsyncSession = Depends(get_db)):
    """Return sorted list of unique skill_ids used across agents."""
    from app.models.family import AgentSkill
    from sqlalchemy import select
    result = await db.execute(select(AgentSkill.skill_id).distinct())
    return sorted(row[0] for row in result.all())


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    try:
        agent = await agent_registry_service.create_agent(db, data)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[AgentOut])
async def list_agents(
    q: str | None = None,
    family: str | None = None,
    status: str | None = None,
    criticality: str | None = None,
    cost_profile: str | None = None,
    mcp_id: str | None = None,
    workflow_id: str | None = None,
    used_in_workflow_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    agents = await agent_registry_service.list_agents(
        db,
        q=q,
        family=family,
        status=status,
        criticality=criticality,
        cost_profile=cost_profile,
        mcp_id=mcp_id,
        workflow_id=workflow_id,
        used_in_workflow_only=used_in_workflow_only,
        limit=limit,
        offset=offset,
    )
    result = []
    for agent in agents:
        enriched = await agent_registry_service.enrich_agent(db, agent)
        result.append(enriched)
    return result


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await agent_registry_service.enrich_agent(db, agent)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    try:
        agent = await agent_registry_service.update_agent(db, agent_id, data)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        if "incompatible" in str(exc).lower():
            raise HTTPException(status_code=422, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{agent_id}/status", response_model=AgentOut)
async def update_agent_status(
    agent_id: str,
    data: AgentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        agent = await agent_registry_service.update_agent_status(db, agent_id, data.status, data.reason or "")
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    existing = await agent_registry_service.get_agent(db, agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        await agent_registry_service.delete_agent(db, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/generate-draft", response_model=AgentGenerationResponse)
async def generate_agent_draft(
    data: AgentGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    available = await agent_registry_service.available_mcp_summaries(db)
    catalog = [McpCatalogSummary.model_validate(item) for item in available]
    draft = agent_generation_service.generate_agent_draft(data, catalog)
    return AgentGenerationResponse(draft=draft, available_mcps=catalog, source="mock_llm")


@router.post("/save-generated-draft", response_model=AgentOut, status_code=201)
async def save_generated_draft(
    data: SaveGeneratedDraftRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        agent = await agent_registry_service.save_generated_draft(db, data.draft)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 2: Commit**

```bash
git add app/api/routes/agents.py
git commit -m "feat: adapt agent routes for DB-backed families/skills with enrich_agent"
```

---

## Task 12: Update main.py — register families router + DB seed

**Files:**
- Modify: `app/main.py:1-64`

- [ ] **Step 1: Update main.py**

Replace `skill_registry_service.load_skills()` with `seed_service.seed_all()` and add families router:

```python
"""Orkestra — Governed multi-agent orchestration platform."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import get_async_session_factory
from app.api.routes import (
    health, requests, cases, agents, mcps, plans, runs,
    control, supervision, approvals, audit, workflows, mcp_catalog,
)
from app.api.routes import settings as settings_routes
from app.api.routes.skills import router as skills_router
from app.api.routes.families import router as families_router
from app.services import seed_service

settings = get_settings()
logger = logging.getLogger("orkestra")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Orkestra {settings.APP_VERSION} starting")
    try:
        factory = get_async_session_factory()
        async with factory() as db:
            await seed_service.seed_all(db)
    except Exception as exc:
        logger.error(f"Failed to seed database: {exc}")
        raise
    yield
    logger.info("Orkestra shutting down")


app = FastAPI(
    title="Orkestra API",
    description="Governed multi-agent orchestration platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(requests.router, prefix="/api/requests", tags=["requests"])
app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(families_router, prefix="/api/families", tags=["families"])
app.include_router(skills_router, prefix="/api/skills", tags=["skills"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(mcps.router, prefix="/api/mcps", tags=["mcps"])
app.include_router(mcp_catalog.router, prefix="/api/mcp-catalog", tags=["mcp-catalog"])
app.include_router(plans.router, prefix="/api", tags=["plans"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(control.router, prefix="/api", tags=["control"])
app.include_router(supervision.router, prefix="/api", tags=["supervision"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(workflows.router, prefix="/api/workflow-definitions", tags=["workflows"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: replace in-memory skill load with DB seed + register families router"
```

---

## Task 13: Update tests

**Files:**
- Modify: `tests/test_api_agents.py:1-34`
- Create: `tests/test_api_families.py`
- Create: `tests/test_api_skills.py`

- [ ] **Step 1: Update existing agent tests**

The agent tests need to seed families/skills before creating agents since `family_id` is now a FK:

```python
"""API tests for agent registry endpoints."""

import pytest


async def _seed_test_family(client, family_id="analysis", label="Analysis"):
    """Helper: create a family for tests."""
    await client.post("/api/families", json={
        "id": family_id, "label": label, "description": "Test family"
    })


async def _seed_test_skill(client, skill_id="web_research", family_id="analysis"):
    """Helper: create a skill for tests."""
    await client.post("/api/skills", json={
        "skill_id": skill_id,
        "label": "Web Research",
        "category": "execution",
        "description": "Research skill",
        "behavior_templates": ["Search the web"],
        "output_guidelines": ["Cite sources"],
        "allowed_families": [family_id],
    })


async def test_create_agent(client):
    await _seed_test_family(client)
    resp = await client.post("/api/agents", json={
        "id": "test_agent",
        "name": "Test Agent",
        "family_id": "analysis",
        "purpose": "Test agent for API tests",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == "test_agent"
    assert resp.json()["family_id"] == "analysis"
    assert resp.json()["status"] == "draft"


async def test_agent_lifecycle_via_api(client):
    await _seed_test_family(client)
    await client.post("/api/agents", json={
        "id": "lc_agent", "name": "LC Agent",
        "family_id": "analysis", "purpose": "Lifecycle test agent via API",
    })
    for status in ["tested", "registered", "active"]:
        resp = await client.patch("/api/agents/lc_agent/status", json={"status": status})
        assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_list_agents_by_family(client):
    await _seed_test_family(client, "analysis", "Analysis")
    await _seed_test_family(client, "control", "Control")
    await client.post("/api/agents", json={"id": "a1", "name": "A1", "family_id": "analysis", "purpose": "Agent A1 test"})
    await client.post("/api/agents", json={"id": "a2", "name": "A2", "family_id": "control", "purpose": "Agent A2 test"})
    resp = await client.get("/api/agents?family=analysis")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_invalid_transition_returns_400(client):
    await _seed_test_family(client, "test", "Test")
    await client.post("/api/agents", json={"id": "bad", "name": "Bad", "family_id": "test", "purpose": "Bad transition test"})
    resp = await client.patch("/api/agents/bad/status", json={"status": "active"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Create `tests/test_api_families.py`**

```python
"""API tests for family endpoints."""


async def test_create_family(client):
    resp = await client.post("/api/families", json={
        "id": "test_fam", "label": "Test Family", "description": "A test family"
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == "test_fam"


async def test_list_families(client):
    await client.post("/api/families", json={"id": "f1", "label": "F1"})
    await client.post("/api/families", json={"id": "f2", "label": "F2"})
    resp = await client.get("/api/families")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_family_detail(client):
    await client.post("/api/families", json={"id": "detail_fam", "label": "Detail"})
    resp = await client.get("/api/families/detail_fam")
    assert resp.status_code == 200
    assert resp.json()["id"] == "detail_fam"
    assert "skills" in resp.json()


async def test_update_family(client):
    await client.post("/api/families", json={"id": "upd_fam", "label": "Old"})
    resp = await client.patch("/api/families/upd_fam", json={"label": "New"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "New"


async def test_delete_family(client):
    await client.post("/api/families", json={"id": "del_fam", "label": "Del"})
    resp = await client.delete("/api/families/del_fam")
    assert resp.status_code == 204


async def test_delete_family_with_agents_blocked(client):
    await client.post("/api/families", json={"id": "used_fam", "label": "Used"})
    await client.post("/api/agents", json={
        "id": "blocker", "name": "Blocker", "family_id": "used_fam", "purpose": "Block delete test"
    })
    resp = await client.delete("/api/families/used_fam")
    assert resp.status_code == 409
    assert "Cannot delete" in resp.json()["detail"]
```

- [ ] **Step 3: Create `tests/test_api_skills.py`**

```python
"""API tests for skill endpoints."""


async def _seed_family(client, fid="analysis"):
    await client.post("/api/families", json={"id": fid, "label": fid.title()})


async def test_create_skill(client):
    await _seed_family(client)
    resp = await client.post("/api/skills", json={
        "skill_id": "test_skill",
        "label": "Test Skill",
        "category": "analysis",
        "description": "A test skill",
        "behavior_templates": ["Do analysis"],
        "output_guidelines": ["Be precise"],
        "allowed_families": ["analysis"],
    })
    assert resp.status_code == 201
    assert resp.json()["skill_id"] == "test_skill"
    assert "analysis" in resp.json()["allowed_families"]


async def test_list_skills(client):
    await _seed_family(client)
    await client.post("/api/skills", json={
        "skill_id": "sk1", "label": "SK1", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["analysis"],
    })
    resp = await client.get("/api/skills")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_skills_by_family(client):
    await _seed_family(client, "exec")
    await client.post("/api/skills", json={
        "skill_id": "fam_skill", "label": "FS", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["exec"],
    })
    resp = await client.get("/api/skills/by-family/exec")
    assert resp.status_code == 200
    assert any(s["skill_id"] == "fam_skill" for s in resp.json())


async def test_delete_skill_used_by_agent_blocked(client):
    await _seed_family(client, "block_fam")
    await client.post("/api/skills", json={
        "skill_id": "blocked_sk", "label": "BS", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["block_fam"],
    })
    await client.post("/api/agents", json={
        "id": "sk_user", "name": "SK User", "family_id": "block_fam",
        "purpose": "Uses blocked skill", "skill_ids": ["blocked_sk"],
    })
    resp = await client.delete("/api/skills/blocked_sk")
    assert resp.status_code == 409
    assert "Cannot delete" in resp.json()["detail"]
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/mbensass/projetPreso/multiAgents/orkestra && python -m pytest tests/test_api_families.py tests/test_api_skills.py tests/test_api_agents.py -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_api_agents.py tests/test_api_families.py tests/test_api_skills.py
git commit -m "test: add family/skill endpoint tests, update agent tests for FK model"
```

---

## Task 14: Frontend — TypeScript types + API service

**Files:**
- Create: `frontend/src/lib/families/types.ts`
- Create: `frontend/src/lib/families/service.ts`
- Modify: `frontend/src/lib/agent-registry/types.ts:1-169`
- Modify: `frontend/src/lib/agent-registry/service.ts:1-140`

- [ ] **Step 1: Create `frontend/src/lib/families/types.ts`**

```typescript
export interface FamilyDefinition {
  id: string;
  label: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface FamilyDetail extends FamilyDefinition {
  skills: SkillBrief[];
  agent_count: number;
}

export interface SkillBrief {
  skill_id: string;
  label: string;
  category: string;
}

export interface SkillDefinition {
  skill_id: string;
  label: string;
  category: string;
  description: string | null;
  behavior_templates: string[];
  output_guidelines: string[];
  allowed_families: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface SkillWithAgents extends SkillDefinition {
  agents: { agent_id: string; label: string }[];
}

export interface FamilyCreatePayload {
  id: string;
  label: string;
  description?: string;
}

export interface FamilyUpdatePayload {
  label?: string;
  description?: string;
}

export interface SkillCreatePayload {
  skill_id: string;
  label: string;
  category: string;
  description?: string;
  behavior_templates: string[];
  output_guidelines: string[];
  allowed_families: string[];
}

export interface SkillUpdatePayload {
  label?: string;
  category?: string;
  description?: string;
  behavior_templates?: string[];
  output_guidelines?: string[];
  allowed_families?: string[];
}
```

- [ ] **Step 2: Create `frontend/src/lib/families/service.ts`**

```typescript
import type {
  FamilyCreatePayload,
  FamilyDefinition,
  FamilyDetail,
  FamilyUpdatePayload,
  SkillCreatePayload,
  SkillDefinition,
  SkillUpdatePayload,
  SkillWithAgents,
} from "./types";

async function request<R>(url: string, opts?: RequestInit): Promise<R> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Families
// ---------------------------------------------------------------------------

export async function listFamilies(): Promise<FamilyDefinition[]> {
  return request<FamilyDefinition[]>("/api/families");
}

export async function getFamily(familyId: string): Promise<FamilyDetail> {
  return request<FamilyDetail>(`/api/families/${familyId}`);
}

export async function createFamily(payload: FamilyCreatePayload): Promise<FamilyDefinition> {
  return request<FamilyDefinition>("/api/families", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateFamily(familyId: string, payload: FamilyUpdatePayload): Promise<FamilyDefinition> {
  return request<FamilyDefinition>(`/api/families/${familyId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteFamily(familyId: string): Promise<void> {
  const res = await fetch(`/api/families/${familyId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

export async function listSkills(): Promise<SkillDefinition[]> {
  return request<SkillDefinition[]>("/api/skills");
}

export async function getSkill(skillId: string): Promise<SkillDefinition> {
  return request<SkillDefinition>(`/api/skills/${skillId}`);
}

export async function listSkillsByFamily(familyId: string): Promise<SkillDefinition[]> {
  return request<SkillDefinition[]>(`/api/skills/by-family/${familyId}`);
}

export async function listSkillsWithAgents(): Promise<SkillWithAgents[]> {
  return request<SkillWithAgents[]>("/api/skills/with-agents");
}

export async function createSkill(payload: SkillCreatePayload): Promise<SkillDefinition> {
  return request<SkillDefinition>("/api/skills", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateSkill(skillId: string, payload: SkillUpdatePayload): Promise<SkillDefinition> {
  return request<SkillDefinition>(`/api/skills/${skillId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteSkill(skillId: string): Promise<void> {
  const res = await fetch(`/api/skills/${skillId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
}
```

- [ ] **Step 3: Update `frontend/src/lib/agent-registry/types.ts`**

Replace `family` with `family_id` and `skills` with `skill_ids` in all interfaces:

```typescript
export type AgentStatus =
  | "draft"
  | "designed"
  | "tested"
  | "registered"
  | "active"
  | "deprecated"
  | "disabled"
  | "archived"
  | string;

export interface FamilyRef {
  id: string;
  label: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentDefinition {
  id: string;
  name: string;
  family_id: string;
  family: FamilyRef | null;
  purpose: string;
  description: string | null;
  skill_ids: string[];
  skills_resolved: { skill_id: string; label: string; category: string }[] | null;
  selection_hints: Record<string, string | boolean | string[]> | null;
  allowed_mcps: string[] | null;
  forbidden_effects: string[] | null;
  input_contract_ref: string | null;
  output_contract_ref: string | null;
  criticality: string;
  cost_profile: string;
  limitations: string[] | null;
  prompt_ref: string | null;
  prompt_content: string | null;
  skills_ref: string | null;
  skills_content: string | null;
  version: string;
  status: AgentStatus;
  owner: string | null;
  last_test_status: string;
  last_validated_at: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface AgentRegistryFilters {
  q?: string;
  family?: string;
  status?: string;
  criticality?: string;
  cost_profile?: string;
  mcp_id?: string;
  workflow_id?: string;
  used_in_workflow_only?: boolean;
}

export interface AgentRegistryStats {
  total_agents: number;
  active_agents: number;
  tested_agents: number;
  deprecated_agents: number;
  current_workflow_agents: number;
}

export interface McpCatalogSummary {
  id: string;
  name: string;
  purpose: string;
  effect_type: string;
  criticality: string;
  approval_required: boolean;
  obot_state: string;
  orkestra_state: string;
}

export interface AgentGenerationRequest {
  intent: string;
  use_case?: string;
  target_workflow?: string;
  criticality_target?: string;
  preferred_family?: string;
  preferred_output_style?: string;
  preferred_mcp_scope?: string;
  constraints?: string;
  owner?: string;
}

export interface GeneratedAgentDraft {
  agent_id: string;
  name: string;
  family_id: string;
  purpose: string;
  description: string;
  skill_ids: string[];
  selection_hints: Record<string, string | boolean | string[]>;
  allowed_mcps: string[];
  forbidden_effects: string[];
  input_contract_ref: string | null;
  output_contract_ref: string | null;
  criticality: string;
  cost_profile: string;
  limitations: string[];
  prompt_content: string;
  skills_content: string;
  owner: string | null;
  version: string;
  status: AgentStatus;
  suggested_missing_mcps: string[];
  mcp_rationale: Record<string, string>;
}

export interface AgentGenerationResponse {
  draft: GeneratedAgentDraft;
  available_mcps: McpCatalogSummary[];
  source: string;
}

export interface AgentGenerationReviewState {
  request: AgentGenerationRequest;
  draft: GeneratedAgentDraft;
  available_mcps: McpCatalogSummary[];
}

export interface AgentCreatePayload {
  id: string;
  name: string;
  family_id: string;
  purpose: string;
  description?: string | null;
  skill_ids?: string[];
  selection_hints?: Record<string, string | boolean | string[]>;
  allowed_mcps?: string[];
  forbidden_effects?: string[];
  input_contract_ref?: string | null;
  output_contract_ref?: string | null;
  criticality?: string;
  cost_profile?: string;
  limitations?: string[];
  prompt_ref?: string | null;
  prompt_content?: string | null;
  skills_ref?: string | null;
  skills_content?: string | null;
  version?: string;
  status?: AgentStatus;
  owner?: string | null;
  last_test_status?: string;
  usage_count?: number;
}

export interface AgentUpdatePayload {
  name?: string;
  family_id?: string;
  purpose?: string;
  description?: string | null;
  skill_ids?: string[];
  selection_hints?: Record<string, string | boolean | string[]>;
  allowed_mcps?: string[];
  forbidden_effects?: string[];
  input_contract_ref?: string | null;
  output_contract_ref?: string | null;
  criticality?: string;
  cost_profile?: string;
  limitations?: string[];
  prompt_ref?: string | null;
  prompt_content?: string | null;
  skills_ref?: string | null;
  skills_content?: string | null;
  version?: string;
  status?: AgentStatus;
  owner?: string | null;
  last_test_status?: string;
  usage_count?: number;
}
```

- [ ] **Step 4: Update `frontend/src/lib/agent-registry/service.ts`**

Replace `listAvailableSkills` to use new types and update filter param name:

```typescript
import type {
  AgentCreatePayload,
  AgentDefinition,
  AgentGenerationRequest,
  AgentGenerationResponse,
  AgentRegistryFilters,
  AgentRegistryStats,
  AgentUpdatePayload,
  GeneratedAgentDraft,
  McpCatalogSummary,
} from "./types";

const BASE = "/api/agents";

async function request<R>(url: string, opts?: RequestInit): Promise<R> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
  return res.json();
}

function asBoolParam(value: boolean | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value ? "true" : "false";
}

export async function listAgents(filters?: AgentRegistryFilters): Promise<AgentDefinition[]> {
  const q = new URLSearchParams();
  if (filters?.q) q.set("q", filters.q);
  if (filters?.family && filters.family !== "all") q.set("family", filters.family);
  if (filters?.status && filters.status !== "all") q.set("status", filters.status);
  if (filters?.criticality && filters.criticality !== "all") q.set("criticality", filters.criticality);
  if (filters?.cost_profile && filters.cost_profile !== "all") q.set("cost_profile", filters.cost_profile);
  if (filters?.mcp_id) q.set("mcp_id", filters.mcp_id);
  if (filters?.workflow_id) q.set("workflow_id", filters.workflow_id);
  const workflowOnly = asBoolParam(filters?.used_in_workflow_only);
  if (workflowOnly) q.set("used_in_workflow_only", workflowOnly);
  const qs = q.toString();
  return request<AgentDefinition[]>(`${BASE}${qs ? `?${qs}` : ""}`);
}

export async function getAgent(agentId: string): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/${agentId}`);
}

export async function createAgent(payload: AgentCreatePayload): Promise<AgentDefinition> {
  return request<AgentDefinition>(BASE, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAgent(agentId: string, payload: AgentUpdatePayload): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/${agentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function updateAgentStatus(agentId: string, status: string): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/${agentId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function deleteAgent(agentId: string): Promise<void> {
  const res = await fetch(`${BASE}/${agentId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
}

export async function getAgentRegistryStats(workflowId?: string): Promise<AgentRegistryStats> {
  const query = workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : "";
  return request<AgentRegistryStats>(`${BASE}/stats${query}`);
}

export async function generateAgentDraft(
  payload: AgentGenerationRequest,
): Promise<AgentGenerationResponse> {
  return request<AgentGenerationResponse>(`${BASE}/generate-draft`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveGeneratedDraft(draft: GeneratedAgentDraft): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/save-generated-draft`, {
    method: "POST",
    body: JSON.stringify({ draft }),
  });
}

export async function listMcpCatalogForAgentDesign(): Promise<McpCatalogSummary[]> {
  const items = await request<
    Array<{
      obot_server: {
        id: string;
        name: string;
        purpose: string;
        effect_type: string;
        criticality: string;
        approval_required: boolean;
      };
      obot_state: string;
      orkestra_state: string;
    }>
  >("/api/mcp-catalog");

  return items.map((item) => ({
    id: item.obot_server.id,
    name: item.obot_server.name,
    purpose: item.obot_server.purpose,
    effect_type: item.obot_server.effect_type,
    criticality: item.obot_server.criticality,
    approval_required: item.obot_server.approval_required,
    obot_state: item.obot_state,
    orkestra_state: item.orkestra_state,
  }));
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/families/ frontend/src/lib/agent-registry/
git commit -m "feat: add family/skill TS types and API service, update agent types for family_id/skill_ids"
```

---

## Task 15: Frontend — Agent Form (family dropdown + skills by family)

**Files:**
- Modify: `frontend/src/components/agents/agent-form.tsx:1-562`
- Modify: `frontend/src/app/agents/new/page.tsx`
- Modify: `frontend/src/app/agents/[id]/edit/page.tsx`

This is a large UI task. The key changes to `agent-form.tsx`:
1. Accept `availableFamilies` prop instead of hardcoded family input
2. Family becomes a `<select>` fed by API data
3. Skills multi-select is filtered by `GET /api/skills/by-family/{family_id}` when family changes
4. Family change auto-deselects incompatible skills with a warning

- [ ] **Step 1: Update `agent-form.tsx`**

The full file is too large to include here. Key changes are:

1. Add to props: `availableFamilies: FamilyDefinition[]`
2. Replace the family `<input>` (line 224-229) with a `<select>` populated from `availableFamilies`
3. Add `useEffect` that calls `listSkillsByFamily(family)` when family changes, then sets `availableSkillsForFamily`
4. In the skills section, use `availableSkillsForFamily` (SkillDefinition objects) instead of string list
5. When family changes, filter out skills not in the new family's allowed list, show warning
6. Update payload: `family` → `family_id`, `skills` → `skill_ids`

Key code snippets for the changes:

**Props update:**
```typescript
import type { FamilyDefinition, SkillDefinition } from "@/lib/families/types";
import { listSkillsByFamily } from "@/lib/families/service";

interface AgentFormProps {
  mode: "create" | "edit";
  initial?: AgentDefinition;
  availableMcps: McpCatalogSummary[];
  availableFamilies: FamilyDefinition[];
  submitLabel: string;
  saving: boolean;
  onSubmit: (payload: FormPayload) => Promise<void> | void;
}
```

**State changes:**
```typescript
const [familyId, setFamilyId] = useState(initial?.family_id ?? "");
const [skills, setSkills] = useState<string[]>(initial?.skill_ids ?? []);
const [familySkills, setFamilySkills] = useState<SkillDefinition[]>([]);
const [skillWarning, setSkillWarning] = useState<string | null>(null);
```

**Family change effect:**
```typescript
useEffect(() => {
  if (!familyId) { setFamilySkills([]); return; }
  listSkillsByFamily(familyId).then((data) => {
    setFamilySkills(data);
    // Check for incompatible skills
    const allowedIds = new Set(data.map((s) => s.skill_id));
    const incompatible = skills.filter((s) => !allowedIds.has(s));
    if (incompatible.length > 0) {
      setSkills(skills.filter((s) => allowedIds.has(s)));
      setSkillWarning(`Skills removed (incompatible with ${familyId}): ${incompatible.join(", ")}`);
    } else {
      setSkillWarning(null);
    }
  }).catch(() => setFamilySkills([]));
}, [familyId]);
```

**Family select element:**
```tsx
<select
  value={familyId}
  onChange={(e) => setFamilyId(e.target.value)}
  className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
>
  <option value="">Select a family...</option>
  {availableFamilies.map((f) => (
    <option key={f.id} value={f.id}>{f.label} ({f.id})</option>
  ))}
</select>
```

**Skills section with family-aware datalist:**
```tsx
{familySkills.length > 0 && (
  <datalist id="available-skills-list">
    {familySkills.map((skill) => (
      <option key={skill.skill_id} value={skill.skill_id}>
        {skill.label}
      </option>
    ))}
  </datalist>
)}
```

**Payload update in submit:**
```typescript
const payloadBase: AgentCreatePayload = {
  id: mode === "create" ? agentId.trim() : initial?.id ?? agentId.trim(),
  name: name.trim(),
  family_id: familyId.trim(),
  // ... rest same
  skill_ids: skills,
  // ... rest same
};
```

- [ ] **Step 2: Update `new/page.tsx` and `[id]/edit/page.tsx`**

Both pages need to load families via `listFamilies()` and pass to AgentForm.

```typescript
import { listFamilies } from "@/lib/families/service";
import type { FamilyDefinition } from "@/lib/families/types";

// In the component:
const [families, setFamilies] = useState<FamilyDefinition[]>([]);

useEffect(() => {
  // Add to the parallel loads:
  listFamilies().then(setFamilies).catch(console.error);
}, []);

// In the JSX:
<AgentForm
  availableFamilies={families}
  // ... rest same
/>
```

Remove the `availableSkills` prop and its loading — skills are now loaded inside agent-form based on family.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/agents/agent-form.tsx frontend/src/app/agents/new/page.tsx frontend/src/app/agents/\\[id\\]/edit/page.tsx
git commit -m "feat: agent form with family dropdown and family-filtered skills"
```

---

## Task 16: Frontend — Agent list page + detail page adaptations

**Files:**
- Modify: `frontend/src/app/agents/page.tsx`
- Modify: `frontend/src/app/agents/[id]/page.tsx`

- [ ] **Step 1: Update agent list page**

Key changes:
1. Family filter dropdown from `listFamilies()` instead of extracting unique strings from agents
2. Display `agent.family?.label` instead of raw `agent.family` string
3. Display `agent.skill_ids` instead of `agent.skills`

- [ ] **Step 2: Update agent detail page**

Key changes:
1. Display family label + description
2. Display resolved skills with labels

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/agents/page.tsx frontend/src/app/agents/\\[id\\]/page.tsx
git commit -m "feat: update agent list and detail pages for family_id/skill_ids model"
```

---

## Task 17: Frontend — Families Admin Page

**Files:**
- Create: `frontend/src/app/agents/families/page.tsx`
- Create: `frontend/src/components/agents/family-form-modal.tsx`
- Modify: `frontend/src/components/layout/sidebar.tsx:10-28`

- [ ] **Step 1: Create `frontend/src/components/agents/family-form-modal.tsx`**

A modal for creating/editing a family with fields: id (create only), label, description. Uses the Orkestra design system classes.

- [ ] **Step 2: Create `frontend/src/app/agents/families/page.tsx`**

A page listing all families in a table with columns: label, family_id, description, skill count, agent count. Buttons: create, edit, delete. Uses `listFamilies()`, `getFamily()`, `createFamily()`, `updateFamily()`, `deleteFamily()`. Empty state: "No families defined. Create one or run the seed."

- [ ] **Step 3: Update sidebar**

Add a "Families" nav item in the Registries section:

```typescript
{ label: "Families", href: "/agents/families", icon: Bot },
```

Insert after the Agents entry.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/agents/families/ frontend/src/components/agents/family-form-modal.tsx frontend/src/components/layout/sidebar.tsx
git commit -m "feat: add families admin page with create/edit/delete"
```

---

## Task 18: Frontend — Skills Admin Page

**Files:**
- Modify: `frontend/src/app/agents/skills/page.tsx`
- Create: `frontend/src/components/agents/skill-form-modal.tsx`

- [ ] **Step 1: Create `frontend/src/components/agents/skill-form-modal.tsx`**

A modal for creating/editing a skill with fields: skill_id (create only), label, category, description, behavior_templates (textarea, one per line), output_guidelines (textarea, one per line), allowed_families (multi-select checkboxes from `listFamilies()`).

- [ ] **Step 2: Build out `frontend/src/app/agents/skills/page.tsx`** (currently empty)

A page listing all skills in a table with columns: label, skill_id, category, allowed_families (badges), agent count. CRUD buttons. Uses `listSkillsWithAgents()`, `createSkill()`, `updateSkill()`, `deleteSkill()`. Empty state: "No skills defined."

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/agents/skills/page.tsx frontend/src/components/agents/skill-form-modal.tsx
git commit -m "feat: add skills admin page with create/edit/delete"
```

---

## Task 19: Frontend — Generate Agent Modal adaptation

**Files:**
- Modify: `frontend/src/components/agents/generate-agent-modal.tsx`

- [ ] **Step 1: Update generate modal**

Replace `family` references with `family_id`, `skills` with `skill_ids`. The preferred_family field in the generation request stays as-is (it's a hint, not a FK). The draft review step needs to use `family_id` and `skill_ids`.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/agents/generate-agent-modal.tsx
git commit -m "feat: adapt generate agent modal for family_id/skill_ids"
```

---

## Task 20: Cleanup — remove old skill_registry_service

**Files:**
- Delete: `app/services/skill_registry_service.py`
- Verify no remaining imports

- [ ] **Step 1: Search for remaining references**

Run: `grep -r "skill_registry_service" app/ --include="*.py"`
Expected: no results (all replaced in previous tasks)

- [ ] **Step 2: Delete the old service**

```bash
rm app/services/skill_registry_service.py
```

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/mbensass/projetPreso/multiAgents/orkestra && python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove deprecated skill_registry_service, all reads now go through DB"
```

---

## Task 21: Final verification

- [ ] **Step 1: Verify imports compile**

Run: `cd /Users/mbensass/projetPreso/multiAgents/orkestra && python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Verify frontend compiles**

Run: `cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend && npx next build`
Expected: build succeeds

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -A && git commit -m "fix: final adjustments after integration verification"
```
