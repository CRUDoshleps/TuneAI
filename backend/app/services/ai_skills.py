from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AISkill


MAX_SKILL_INSTRUCTIONS_CHARS = 12000


def skill_ids_from_criteria(criteria: dict | None) -> list[str]:
    raw = (criteria or {}).get("skill_ids")
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    return values


def load_skill_instructions(db: Session, criteria: dict | None) -> str:
    skill_ids = skill_ids_from_criteria(criteria)
    if not skill_ids:
        return ""
    stmt = select(AISkill).where(AISkill.id.in_(skill_ids), AISkill.is_active.is_(True))
    rows = list(db.scalars(stmt).all())
    by_id = {skill.id: skill for skill in rows}
    blocks: list[str] = []
    for skill_id in skill_ids:
        skill = by_id.get(skill_id)
        if skill:
            blocks.append(f"{skill.name}\n{skill.content}")
    return "\n\n---\n\n".join(blocks)[:MAX_SKILL_INSTRUCTIONS_CHARS]
