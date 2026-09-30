from app.db.session import SessionLocal
from app.services.conference_quiz import QUIZZES, seed_conference_quiz


if __name__ == "__main__":
    with SessionLocal() as db:
        for quiz_key in QUIZZES:
            test = seed_conference_quiz(db, quiz_key)
            print(f"{test.title}: {len(test.questions)} questions ready.")
