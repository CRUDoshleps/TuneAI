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
            blocks.append(render_skill_instructions(skill))
    return "\n\n---\n\n".join(blocks)[:MAX_SKILL_INSTRUCTIONS_CHARS]


def render_skill_instructions(skill: AISkill) -> str:
    rubric = ", ".join(
        f"{item.get('name')}:{item.get('weight')}"
        for item in (skill.rubric or [])
        if isinstance(item, dict) and item.get("name")
    )
    instructions = "; ".join(str(item).strip() for item in (skill.instructions or []) if str(item).strip())
    output_flags = ", ".join(
        key for key, enabled in (skill.output_config or {}).items() if enabled
    )
    parts = [
        f"Evaluator skill: {skill.name}",
        f"scenario={skill.scenario}; language={skill.language}; strictness={skill.strictness}; "
        f"score_scale={skill.score_scale}; confidence_threshold={skill.confidence_threshold}; "
        f"material_policy={skill.material_policy}",
    ]
    if rubric:
        parts.append(f"rubric_weights={rubric}")
    if instructions:
        parts.append(f"instructions={instructions}")
    if output_flags:
        parts.append(f"required_output={output_flags}")
    parts.append(f"notes={skill.content}")
    return "\n".join(parts)
