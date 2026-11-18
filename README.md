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

retry will use the failed run's saved inputs.

resume RUN_ID FILE will continue to allow corrected YAML inputs.

restart will create a separate run, preserving the original history and records.

We need to make claiming a workflow run an atomic database operation. Only one process should be able to change a run
from pending or failed to running.

We'll do this without adding a new database column
How the new behavior will work
Existing status Execution request
pending Allowed; claims the run
failed Allowed; claims the run for retry
running Rejected; another execution may be active
completed Rejected; already finished

The claim uses a conditional SQL UPDATE, not a Python check followed by an update.

That distinction matters:

- A Python check can allow two processes to see pending simultaneously.
- The conditional database update allows only one process to change the status successfully.
- The other process receives a clear error instead of executing the workflow.

1. Prevent concurrent execution

- Stop two CLI processes from executing the same workflow run simultaneously.
- Prevent the same milestone from being claimed by multiple workers.
- Reject attempts to resume a workflow that is already actively executing.

2. Recover interrupted workflows

- Detect workflow runs left in running state after a crash.
- Identify milestones left in running state.
- Safely return interrupted milestones to a retryable state.

3. Protect checkpoint integrity

- Ensure a milestone's database changes and completed checkpoint remain in the same transaction.
- Avoid accidentally repeating already completed milestones.
- Preserve useful error information when recovery fails.

4. Add regression tests

- Two execution attempts against the same run.
- Interrupted workflow recovery.
- Interrupted milestone recovery.
- Completed milestones remain untouched.
- Normal retry and resume behavior still works.

let ShortVideoCLI periodically report that a workflow execution is still alive.
What we'll implement

1. When a workflow starts, generate a unique execution_id.
2. Record the initial last_heartbeat_at timestamp.
3. Start a background heartbeat task that updates the timestamp at a configurable interval.
4. Stop the heartbeat task when execution completes or fails.
5. Use execution_id to ensure an old execution cannot update the heartbeat of a newer execution.
6. Preserve the existing milestone transaction and recovery behavior.
   One important detail: heartbeat updates must use their own database sessions, not share the workflow handler's
   SQLAlchemy session. We'll also account for SQLite write-locking so heartbeat updates don't undermine milestone
   transactions.

One design choice is important: the heartbeat must run independently of milestone execution. A milestone might take
several minutes, so updating the heartbeat only between steps would incorrectly make a healthy workflow look abandoned.

Scenario Expected result
Normal execution Run completes and heartbeat stops
Handler failure Run and failed step are recorded as failed
Concurrent execution Second process cannot claim the run
Ownership lost Old execution cannot commit its checkpoint
Heartbeat update Only the current execution can update it
Completed run Heartbeat stops after completion