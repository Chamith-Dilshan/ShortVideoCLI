# ShortVideoCLI

ShortVideoCLI is an AI-assisted workflow for discovering compelling
moments in long-form videos and preparing them for short-form platforms.

The initial focus is gameplay footage, but the architecture is intended
to support other video genres.

## Planned workflow

1. Investigate a video and its available public information.
2. Optionally analyze authorized YouTube Analytics data.
3. Optionally inspect selected video frames.
4. Detect and rank potentially engaging moments.
5. Prepare candidates for human review.
6. Export approved clips using platform-specific presets.

## Supported platforms

- YouTube Shorts
- TikTok
- Instagram Reels

## Requirements

- Python 3.11+
- uv

## Installation

```bash
uv sync

Step 1 — Install dependencies
uv sync


Step 2 — Create the migration directory

Only do this if migrations/ doesn't already exist:
uv run alembic init migrations


Replace its generated env.py with the code above.

Step 3 — Generate the initial migration
uv run alembic revision --autogenerate -m "initial database schema"


Step 4 — Create the database tables
uv run alembic upgrade head


Step 5 — Verify everything
uv run shortvideocli status
uv run shortvideocli db-check
uv run pytest
```

One important design decision: each milestone gets its own database session and transaction. This prevents SQLAlchemy's
automatic transaction handling from accidentally mixing queries from one milestone with another.

Situation What happens on resume
Step completed Skipped
Step failed Retried
Process crashed while step was running Retried
Earlier steps completed Their outputs remain available