#!/usr/bin/env python3
"""Seed demo case #001. Run from backend/: PYTHONPATH=. python scripts/seed_demo.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import SessionLocal, init_db
from main import _seed_demo_case

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    _seed_demo_case(db)
    db.close()
    print("Demo case #001 seeded.")
