# SafePayout

AI-assisted batch payout manager built on PayPal Payouts. An LLM cleans and flags messy payout sheets, a rules engine enforces limits, and a human approves before money moves. Python/FastAPI, PayPal sandbox.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Input     │────▶│   LLM       │────▶│  Policy     │────▶│  Human      │
│  (CSV/Text) │     │  Parser     │     │  Engine     │     │  Review     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  Normalized │     │  Decisions  │     │  Approved/  │
                    │  Payees     │     │  + Reasons  │     │  Rejected   │
                    └─────────────┘     └─────────────┘     └─────────────┘
                                                                       │
                                                                       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Audit      │◀────│  PayPal     │◀────│  Execute    │◀────│  Approved   │
│  Summary    │     │  Payouts    │     │  Batch      │     │  Items      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

**Core Principle**: The LLM proposes. The rules enforce. The human approves. PayPal executes.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PayPal Developer Sandbox account
- Anthropic API key

### Installation

```bash
# Clone and enter the project
cd safepayout

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

Edit `.env` with your credentials:

```bash
# PayPal Sandbox (get from developer.paypal.com)
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_WEBHOOK_ID=your_webhook_id

# Anthropic API (get from console.anthropic.com)
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-sonnet-5-5

# Database (SQLite for dev, Postgres for prod)
DATABASE_URL=sqlite:///./safepayout.db
```

### Running the Backend

```bash
# Start the API server
uvicorn app.main:app --reload --app-dir backend

# Or from project root
cd backend && uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

- Health check: `GET /health`
- API docs: `http://localhost:8000/docs`

### Running the Frontend

```bash
# From project root
cd frontend && npm run dev
```

The frontend will be available at `http://localhost:5173` (or next available port).

The Vite dev server proxies API requests to `http://localhost:8000` by default. Set `VITE_API_URL` to override.

### Running Tests

```bash
# Backend tests
pytest backend/tests -v

# Backend tests with coverage
pytest backend/tests --cov=app --cov-report=term-missing

# Frontend tests
cd frontend && npm test

# Frontend tests in watch mode
cd frontend && npm run test:watch
```

### Sample Data

Test files are in `backend/sample_data/`:
- `messy_payouts.csv` - CSV with duplicates, malformed emails, unusual amounts
- `messy_text.txt` - Free-text payout instructions

The frontend has a "Load Sample Data" button on the New Run screen for one-click demo setup.

## API Endpoints

### Payout Runs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/runs` | Create a new payout run |
| GET | `/runs/{id}` | Get run details |
| GET | `/runs` | List runs |
| POST | `/runs/{id}/items/{item_id}/decision` | Approve/reject item |
| POST | `/runs/{id}/execute` | Execute approved batch |
| GET | `/runs/{id}/audit` | Get audit summary |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhooks/paypal` | PayPal webhook receiver |

## Development

### Project Structure

```
safepayout/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── services/     # Business logic
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── schemas.py    # Pydantic models
│   │   ├── config.py     # Settings
│   │   ├── db.py         # Database setup
│   │   └── main.py       # FastAPI app
│   ├── tests/            # Pytest tests
│   └── sample_data/      # Test CSV/text files
├── frontend/
│   ├── src/
│   │   ├── api/          # API client & TanStack Query hooks
│   │   ├── components/   # Reusable UI components
│   │   ├── pages/        # Page components (NewRun, Review)
│   │   ├── types/        # TypeScript types matching backend schemas
│   │   ├── utils/        # Formatting, helpers
│   │   ├── test/         # Test setup & utilities
│   │   ├── App.tsx       # Routing
│   │   └── main.tsx      # Entry point with providers
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vitest.config.ts
├── docs/                 # Architecture, demo script
└── pyproject.toml        # Backend dependencies
```

### Code Quality

```bash
# Backend
ruff check backend/
ruff format backend/
mypy backend/app/

# Frontend
cd frontend && npm run lint
cd frontend && npm test
```

## PayPal Sandbox Setup

1. Go to [developer.paypal.com](https://developer.paypal.com)
2. Create a sandbox app to get Client ID and Secret
3. Create a webhook URL (use ngrok for local: `ngrok http 8000`)
4. Subscribe to events: `PAYMENT.PAYOUTSBATCH.*`, `PAYMENT.PAYOUTS-ITEM.*`
5. Copy Webhook ID to `.env`

---

## About the Project

### Inspiration

The inspiration for SafePayout came from the common pain points in business payout operations. Managing multiple payouts manually, tracking approvals, and integrating with payment processors like PayPal creates significant overhead for businesses. Many small to medium enterprises struggle with efficiently batch-processing payments while maintaining proper audit trails and compliance. The idea was to build a tool that leverages AI to automate the tedious parts of payout management while giving humans control over decisions that require judgment.

### What it does

SafePayout is an **AI-assisted batch payout manager with PayPal integration** that streamlines the entire payout workflow:

- **CSV/Text Upload**: Users can upload CSV files or free-text payout instructions
- **AI Parsing**: The system automatically parses payee information (names, emails, amounts, currencies, notes)
- **Policy Engine**: Built-in policy evaluation handles auto-approvals, blocks, and flags based on configurable rules
- **AI Review**: Additional AI analysis flags potentially problematic payouts with explanations
- **PayPal Integration**: Creates payout batches in PayPal Sandbox and tracks status
- **Audit Trail**: Complete audit events logging for all actions (run creation, item decisions, webhook events)
- **Review Interface**: Dashboard to review pending items, approve/reject, and execute payouts
- **CSV Download**: Export audit events and details for record-keeping

The system manages payout runs through statuses: DRAFT → REVIEW → EXECUTING → COMPLETED/FAILED, with full visibility into auto-approved, needs-review, and blocked items.

### How we built it

The project was built as a full-stack application with a **FastAPI backend** and **React frontend**:

**Backend (FastAPI)**
- **Database**: SQLAlchemy 2.0 with Alembic migrations, using SQLite for storage
- **API Routes**: 14 endpoints for run management, item decisions, approval execution, and PayPal webhooks
- **AI Services**: Three service modules:
  - `ai_parser`: Parses CSV/free-text input into structured payee data
  - `ai_review`: Additional AI analysis for flagging issues
  - `paypal`: PayPal API client for batch creation and webhook verification
- **Policy Engine**: Configurable policy rules for auto-approval, blocking, and review decisions
- **Lifespan Management**: Database initialization on startup, proper cleanup on shutdown

**Frontend (React + Vite)**
- **Query Management**: TanStack React Query for data fetching and state management
- **Routing**: React Router DOM for navigation between runs, audit, and review pages
- **UI**: Served from Vite-built static files in the `dist/` directory
- **API Client**: Fetch-based client communicating with the FastAPI backend at `http://localhost:8000`

**Architecture**
- Environment configuration via Pydantic Settings with `.env` file support
- CORS middleware configured for development origin (`http://localhost:3000`)
- Async context manager for FastAPI lifespan (DB init/cleanup)
- Editable install via `pip install -e .` for development workflow

### Challenges we ran into

1. **CORS Configuration**: Initially struggled with Cross-Origin Resource Sharing between the React frontend (port 3000) and FastAPI backend (port 8000). Fixed by configuring `CORSMiddleware` with environment-based allowOrigins.

2. **PayPal Webhook Verification**: The webhook endpoint requires PayPal transmission headers (`PayPal-Transmission-Id`, `PayPal-Transmission-Time`, `PayPal-Cert-Url`, `PayPal-Transmission-Sig`, `PayPal-Auth-Algo`) for signature verification. Without proper PayPal Sandbox credentials, webhook testing was limited.

3. **AI Parsing Edge Cases**: The AI parser (`parse_payouts`) had to handle various input formats - CSV files, free-text descriptions, different currency formats, and edge cases like missing fields or malformed entries.

4. **Policy Decision Logic**: Designing the policy engine to correctly categorize items into AUTO_APPROVED, NEEDS_REVIEW, BLOCKED, and PENDING states required careful consideration of business rules and threshold values.

5. **State Management**: Synchronizing the backend run status with frontend UI state, especially during the execute flow which involves PayPal API calls and async status updates.

6. **Database Schema Design**: Creating the relational model with PayoutRun, PayoutItem, AuditEvent, and policy decision tables that properly track the lifecycle of each payout from creation through execution.

### Accomplishments that we're proud of

- **End-to-End Workflow**: Successfully built a complete payout management pipeline from CSV upload to PayPal batch execution with proper status tracking
- **AI Integration**: Integrated multiple AI services (parsing, review) that work together to reduce manual review overhead
- **Policy Flexibility**: Configurable policy engine that can be adapted to different business rules without code changes
- **Full Audit Trail**: Comprehensive audit event logging that captures all significant actions for compliance and debugging
- **PayPal Integration**: Functional PayPal Sandbox API integration including batch creation and webhook handling
- **Modern Stack**: FastAPI 0.109+ with SQLAlchemy 2.0 and async/await patterns, paired with a React frontend using TanStack Query
- **Deployable**: Editable install makes development iterative, and the architecture supports deployment with uvicorn and production-ready configuration

### What we learned

- **FastAPI Maturity**: FastAPI's type system and automatic documentation (OpenAPI) significantly reduced development time and helped catch integration errors early
- **SQLAlchemy 2.0**: New features like `ident=True` and improved async support, though the migration from 1.x required careful attention to session management
- **Pydantic Settings**: Environment-based configuration with `extra="ignore"` provides clean config management without breaking on unexpected env vars
- **React Query Essentials**: TanStack React Query's `queryKeys`, `enabled` guards, and refetch strategies are essential for reliable data fetching in CRUD applications
- **PayPal API Realities**: The difference between PayPal Sandbox and production environments, required headers for webhook verification, and the batch vs. item-level event types
- **Async Best Practices**: Proper use of `await` with httpx for HTTP calls, async SQLAlchemy sessions, and avoiding blocking operations in async FastAPI endpoints
- **Full-Stack Integration**: The importance of matching CORS origins, error handling boundaries, and loading states when connecting frontend and backend
- **Database Design Patterns**: Relational modeling for tracking state machines (run statuses, item decisions, audit events) with proper foreign key relationships

### What's next for SafePayout

- **Multi-User Support**: Authentication and authorization to allow multiple users per organization with role-based access
- **PayPal Production**: Full production PayPal integration with proper credentials and live API endpoints
- **Email Notifications**: SMTP integration to notify users of run status changes, pending items, and execution results
- **Template System**: Pre-built payout templates for common scenarios (employee payments, vendor payouts, refunds)
- **Advanced Analytics**: Dashboards with charts showing payout trends, approval rates, and financial summaries
- **API Rate Limiting**: Add rate limiting and request validation for production deployments
- **Export Formats**: Additional export options (Excel, JSON) beyond CSV for audit data
- **Slack Integration**: Real-time notifications and webhook responses sent to Slack channels
- **Docker Deployment**: Containerized deployment with proper database migrations and environment configuration
- **Enhanced Policy Rules**: More sophisticated policy evaluation with regex patterns, amount thresholds, and custom rule expressions

---

*Built with ❤️ using FastAPI, SQLAlchemy, Pydantic, React, and AI assistance*

## License

MIT License - see LICENSE file