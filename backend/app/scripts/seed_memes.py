from app.db.session import SessionLocal
from app.services.meme_quiz import seed_meme_quiz


if __name__ == "__main__":
    with SessionLocal() as db:
        test = seed_meme_quiz(db)
        print(f"Meme quiz ready: {len(test.questions)} questions.")
