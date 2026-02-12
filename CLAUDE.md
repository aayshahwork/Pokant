# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Voxture (internally "Pokant") is a voice AI optimization platform. It ingests real call transcripts from voice bots, uses Claude to analyze failures and extract structured attributes, clusters failures into patterns, then auto-generates and tests prompt variants to fix them.

**Pipeline**: Ingest calls → Claude analysis (15 attributes) → embedding + clustering → GPT-4o variant generation → Claude simulation testing → A/B deploy

## Repository Structure

```
Voxture/
├── CLAUDE.md
├── package.json              # pnpm workspace root
├── pnpm-workspace.yaml       # workspaces: pokant-landing-page, pokant-backend
├── index.html                # Dev redirect (checks localhost ports)
├── scripts/
│   └── build-cloudflare-pages.sh
├── pokant-landing-page/      # Next.js frontend
└── pokant-backend/           # FastAPI backend
```

## Tech Stack

### Frontend (`pokant-landing-page/`)
- **Framework**: Next.js 15 (React 19, TypeScript)
- **UI**: Tailwind CSS + shadcn/ui (59 Radix components in `components/ui/`)
- **Charts**: Recharts
- **Build**: Static export (`output: 'export'` in next.config.mjs)
- **Deploy**: Cloudflare Pages

### Backend (`pokant-backend/`)
- **Framework**: FastAPI 0.109
- **Database**: PostgreSQL 15+ with pgvector (1536-dim embeddings, IVFFlat index)
- **ORM**: SQLAlchemy 2.0 (declarative base)
- **Migrations**: Alembic (configured, no migrations generated yet — uses `create_all`)
- **AI Services**: Anthropic SDK (Claude analysis + simulation), OpenAI SDK (GPT-4o variants + embeddings)
- **Encryption**: Fernet (cryptography lib) for API key storage
- **HTTP Client**: httpx (async)

## Development

### Frontend
```bash
pnpm dev                    # Next.js dev server on :3000
pnpm build                  # Static export
```

### Backend
```bash
cd pokant-backend
pip install -r requirements.txt
cp .env.example .env        # Fill in API keys
uvicorn app.main:app --reload --port 8000
```

Or from root:
```bash
pnpm backend:dev            # uvicorn with reload on :8000
```

### Database Setup
```bash
python -m scripts.init_db   # Create tables + seed test data
```

## Backend Architecture

### Database Models (`app/models.py`) — 6 tables

| Model | Key Fields |
|-------|-----------|
| **Customer** | company_name, email, vapi_api_key_encrypted, bot_provider, bot_id, status |
| **Call** | customer_id (FK), provider_call_id, transcript, outcome, failure_category, metadata (JSONB) |
| **CallAttribute** | call_id (FK), 15 Claude-extracted attributes (accent_strength, failure_pattern, emotional_markers, etc.), embedding (Vector 1536) |
| **Pattern** | customer_id (FK), name, failure_type, frequency, severity, revenue_impact_monthly, root_cause, status |
| **Variant** | pattern_id (FK), letter (A-E), prompt_text, success_rate, improvement_delta, recommended, tested_against |
| **ABTest** | customer_id (FK), pattern_id (FK), status, control_assistant_id, variant_assistant_id, traffic_split, control/variant calls + success rates, start_date, end_date, winner_variant_id |

### API Routes (`app/routers/`) — prefix `/api`

| Endpoint | Router | Behavior |
|----------|--------|----------|
| `POST /api/onboard` | onboarding.py | Creates customer, encrypts API keys, persists to DB |
| `GET /api/dashboard/{customer_id}` | dashboard.py | Real DB queries with mock fallback |
| `GET /api/patterns/{customer_id}` | patterns.py | Real DB queries with mock fallback |
| `GET /api/variants/{pattern_id}` | variants.py | Auto-generates via VariantManager if none exist |
| `POST /api/variants/{pattern_id}/regenerate` | variants.py | Deletes + regenerates variants |
| `POST /api/tests/deploy` | tests.py | Creates variant assistant in Vapi, starts A/B test |
| `GET /api/tests/{test_id}` | tests.py | Fetches live results from Vapi + statistical significance |
| `POST /api/tests/{test_id}/promote` | tests.py | Promotes winning variant to 100% traffic |
| `POST /api/tests/{test_id}/cancel` | tests.py | Cancels test and cleans up variant assistant |
| `GET /api/tests?customer_id=` | tests.py | Lists all A/B tests for a customer |
| `GET /health` | main.py | Health check |

### Services (`app/services/`)

| Service | Purpose |
|---------|---------|
| **claude_analysis.py** | `ClaudeAnalyzer` — analyzes transcripts with Claude, extracts 15 structured attributes |
| **variant_generator.py** | `VariantGenerator` — GPT-4o generates 5 prompt variants per pattern |
| **variant_tester.py** | `VariantTester` — Claude simulates each variant against edge cases via pgvector search |
| **variant_manager.py** | `VariantManager` — orchestrates generate → test → store pipeline |
| **pattern_clustering.py** | `PatternClusterer` — groups failed calls by failure_pattern, saves to Pattern table |
| **ab_test_manager.py** | `ABTestManager` — deploy tests, fetch results, promote winners, cancel tests |
| **statistical_analyzer.py** | `StatisticalAnalyzer` — two-proportion z-test, annual impact projection |
| **test_monitor.py** | Background job: monitors running tests, auto-promotes winners after 4 days |
| **vapi.py** | `VapiClient` — async Vapi API (calls, assistants, clone/deploy/delete for A/B) |
| **retell.py** | `RetellClient` — stub, raises NotImplementedError |
| **encryption.py** | Fernet encrypt/decrypt for API key storage |

### Utilities (`app/utils/`)

| Utility | Purpose |
|---------|---------|
| **vectors.py** | OpenAI text-embedding-3-small: `generate_embedding()`, `generate_embeddings_batch()`, `cosine_similarity()` |

### Scripts (`scripts/`)

| Script | Usage |
|--------|-------|
| **init_db.py** | `python -m scripts.init_db` — create tables + seed test data |
| **analyze_customer.py** | `python -m scripts.analyze_customer --customer-id=<uuid> --limit=100` — full pipeline: Vapi fetch → Claude analysis → embeddings → pattern clustering |
| **generate_variants.py** | `python scripts/generate_variants.py --pattern-id=<uuid>` — generate + test prompt variants |
| **monitor_tests.py** | `python -m scripts.monitor_tests` — cron job to monitor active A/B tests (run every 6h) |

## Frontend Architecture (`pokant-landing-page/`)

### Pages
- `app/page.tsx` — Landing page (hero, features, pricing, waveform visualization)
- `app/dashboard/page.tsx` — Dashboard stub linking to static HTML pages

### Static Dashboard Pages (`public/`)
9 HTML files served via Next.js static export. All use Tailwind CDN + vanilla JS with a consistent layout:
- **Fixed top nav** (h-14): Logo, connected bot indicator, settings
- **Fixed left sidebar** (w-56): Navigation with active state highlighting
- **Scrollable main content**
- **Fixed right sidebar** (w-80/w-72): Contextual widgets

Pages: dashboard.html, test-runs.html, settings.html, analytics.html, testing.html, call-breakdown.html, results.html, setup.html, signin.html

### Design System (Static Pages)
- Dark theme: Background `#0a0a0a`, Cards `#1a1a1a`, Borders `zinc-800`
- Accent: Blue `#3b82f6`
- Severity colors: Red (critical), Amber (moderate), Green (low)
- Monospace: `.mono` class (JetBrains Mono)
- Active nav: `bg-blue-500/10 text-blue-400 border border-blue-500/20`
- Live indicators: `.pulse-dot` animation
- Bot branding: "ServiceBot" connected to "Zendesk"

## Environment Variables (`pokant-backend/.env`)

```
DATABASE_URL=postgresql://postgres:password@localhost:5432/pokant
SECRET_KEY=<openssl rand -hex 32>
ENCRYPTION_KEY=<Fernet.generate_key()>
VAPI_TEST_API_KEY=sk_test_...
CLAUDE_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...
ENVIRONMENT=development
DEBUG=True
```

## Key Patterns

- **Mock fallback**: Dashboard and patterns routers query real DB first, return hardcoded mock data if empty
- **Auto-generation**: Variants router auto-triggers VariantManager pipeline when no variants exist for a pattern
- **Encryption at rest**: Customer API keys encrypted with Fernet before DB storage
- **15 analysis attributes**: Each failed call gets Claude-extracted structured data stored in CallAttribute
- **pgvector similarity**: Edge cases for variant testing found via cosine distance on call embeddings
- **Revenue impact**: Estimated at $20/failure in pattern_clustering.py
- **A/B test lifecycle**: deploy → monitor (cron every 6h) → statistical significance check → auto-promote after 4 days
- **Vapi A/B split**: No native split — clones assistant with variant prompt, routes traffic manually
- **Statistical significance**: Two-proportion z-test, requires 30+ calls per group, extends test if not significant

## What's Not Built Yet

- Alembic migration files (using create_all for now)
- Retell integration (stub only)
- Webhook-based automatic traffic routing (currently manual split)
- Proper background job queue (monitoring runs via cron script)
- Authentication/authorization
- Frontend-backend integration (dashboard still reads hardcoded HTML data)
