import asyncio
import json

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ai_provider_runtime import probe_active_ai_provider


async def check_ai() -> dict[str, str]:
    settings = get_settings()
    with SessionLocal() as db:
        details = await probe_active_ai_provider(db, settings)
    return {
        "status": "ready",
        "provider": "active",
        "details": details,
        "version": settings.app_revision.removeprefix("sha-"),
    }


def main() -> None:
    print(json.dumps(asyncio.run(check_ai()), ensure_ascii=False))


if __name__ == "__main__":
    main()
