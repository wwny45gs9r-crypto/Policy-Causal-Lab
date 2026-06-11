import argparse
import hashlib
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base, SessionLocal, engine
from app.models import User


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def main():
    parser = argparse.ArgumentParser(description="Create or promote a Policy Causal Lab admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user:
            user.role = "admin"
            user.hashed_password = hash_password(args.password)
        else:
            user = User(email=args.email, hashed_password=hash_password(args.password), role="admin")
            db.add(user)
        db.commit()
        print(f"Admin ready: {args.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
