import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import RoleEnum, User


def bootstrap_admin() -> None:
    email = os.environ["BOOTSTRAP_ADMIN_EMAIL"].strip().lower()
    password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]
    if len(password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name="TuneAI Admin",
                hashed_password=hash_password(password),
                role=RoleEnum.admin,
                is_active=True,
            )
            db.add(user)
        else:
            user.hashed_password = hash_password(password)
            user.role = RoleEnum.admin
            user.is_active = True
        db.commit()
    print("Production administrator is ready.")


if __name__ == "__main__":
    bootstrap_admin()
