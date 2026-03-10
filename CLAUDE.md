# ComputerUse.dev

## Project Overview
Managed orchestration platform for browser-based AI automation.
Monorepo: Python backend (FastAPI + Celery) + TypeScript frontend (Next.js).

## Tech Stack
- API: FastAPI (Python 3.11+), uvicorn
- Queue: Celery + Redis (Upstash)
- Database: PostgreSQL 16 (Supabase), SQLAlchemy async
- Browser: Playwright + Browserbase
- LLM: Anthropic Claude API (claude-sonnet-4-5)
- Storage: Cloudflare R2 (S3-compatible)
- Frontend: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- Payments: Stripe
- Testing: pytest + pytest-asyncio (backend), vitest (frontend)

## Directory Structure
/api          - FastAPI application (routes, models, middleware)
/workers      - Celery workers (task executor, browser manager, agent)
/sdk          - Python SDK package
/dashboard    - Next.js frontend application
/shared       - Shared types, constants, utilities
/tests        - Test suites (unit, integration, e2e)
/infra        - Docker, deployment configs
/scripts      - Dev scripts, migrations, seed data

## Commands
- Backend tests: cd api && pytest -x -v
- Frontend tests: cd dashboard && npm test
- Lint: ruff check . && cd dashboard && npm run lint
- Type check: mypy api/ workers/ && cd dashboard && npx tsc --noEmit
- Run API locally: cd api && uvicorn main:app --reload --port 8000
- Run worker locally: cd workers && celery -A main worker --loglevel=info
- Run dashboard: cd dashboard && npm run dev

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update tasks/lessons.md with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management
1. Plan First: Write plan to tasks/todo.md with checkable items
2. Verify Plan: Check in before starting implementation
3. Track Progress: Mark items complete as you go
4. Explain Changes: High-level summary at each step
5. Document Results: Add review section to tasks/todo.md
6. Capture Lessons: Update tasks/lessons.md after corrections

## Core Principles
- Simplicity First: Make every change as simple as possible. Impact minimal code.
- No Laziness: Find root causes. No temporary fixes. Senior developer standards.
- Minimal Impact: Changes should only touch what's necessary. Avoid introducing bugs.
