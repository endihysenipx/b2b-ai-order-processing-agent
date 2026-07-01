# Week 3 Completion Report

Project: B2B AI Order Processing Agent  
Team: Lea Murturi, Endi Hyseni, Imane  
Date: July 1, 2026

## Repository URL

Hosted GitHub repository URL: https://github.com/endihysenipx/b2b-ai-order-processing-agent

Visibility: private

Local repository path:

```text
C:\Users\Admin\Documents\GitHub\FlowForge
```

## Branches

Created and pushed branches:

- `main`
- `develop`
- `feature/project-foundation`
- `feature/database-models`
- `feature/orders-api`
- `feature/frontend-layout`
- `feature/orders-page`
- `feature/mock-extraction`
- `feature/docker-setup`

Feature branch naming documented in `CONTRIBUTING.md`.

## Seed Login Credentials

- Admin: `admin@example.com` / `Admin123!`
- Operator: `operator@example.com` / `Operator123!`

These are development-only credentials from seeded fake data.

## Local Startup Commands

Docker target:

```bash
cp .env.example .env
docker compose up --build
```

Local fallback commands:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:DATABASE_URL="sqlite:///./dev.db"
$env:STORAGE_ROOT="../storage"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m app.db.seed
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ../frontend
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8000/api/v1"
npm run dev -- --host 127.0.0.1
```

## Local URLs

- Frontend: http://127.0.0.1:5173
- Backend health: http://127.0.0.1:8000/health
- Swagger API documentation: http://127.0.0.1:8000/docs

## Implemented Endpoints

- `GET /health`
- `POST /api/v1/auth/login`
- `GET /api/v1/clients`
- `GET /api/v1/clients/{client_id}`
- `GET /api/v1/orders`
- `GET /api/v1/orders/{order_id}`
- `PATCH /api/v1/orders/{order_id}`
- `PATCH /api/v1/orders/{order_id}/items/{item_id}`
- `POST /api/v1/orders/{order_id}/approve`
- `POST /api/v1/orders/{order_id}/reject`
- `POST /api/v1/orders/{order_id}/report-issue`
- `POST /api/v1/orders/{order_id}/validate`
- `POST /api/v1/orders/{order_id}/generate-xml`
- `POST /api/v1/orders/{order_id}/send-xml`
- `GET /api/v1/reports/summary`
- `GET /api/v1/feedback`
- `POST /api/v1/feedback`

## Implemented Frontend Pages

- Login
- Overview
- Orders
- Order Details
- Clients
- Data Export
- Feedback & Issues
- Users
- Settings

## Project Board and Issues

Hosted backlog:

- Repository issues: https://github.com/endihysenipx/b2b-ai-order-processing-agent/issues
- 17 Week 3 issues created with owners and acceptance criteria.
- Required labels created, including `frontend`, `backend`, `database`, `ai`, `ocr`, `email`, `xml`, `documentation`, `testing`, `infrastructure`, priorities, `week-3`, and `future`.
- Required milestones created:
  - `Week 3 - Foundation`
  - `Sprint 2 - AI and Document Processing`
  - `Sprint 3 - Human Review and XML`
  - `Final Integration and Testing`
- Issues #1-#17 are assigned to the `Week 3 - Foundation` milestone.

Local board equivalent:

- `docs/project-board/README.md`
- `docs/project-board/week-3-issues.md`
- `docs/project-board/index.html`

It includes the required columns, labels, milestones, 17 Week 3 issues, owners, and acceptance criteria. A hosted GitHub Project was not created because the authenticated token does not have the required `project`/`read:project` scope. The hosted GitHub Issues backlog plus the local board artifact are the Week 3 board equivalent.

## Screenshots

- Overview page: `docs/week-3/screenshots/overview.png`
- Orders page: `docs/week-3/screenshots/orders.png`
- Order Details page: `docs/week-3/screenshots/order-details.png`
- Swagger API: `docs/week-3/screenshots/swagger.png`
- Project board: `docs/week-3/screenshots/project-board.png`

## Test Results

Backend:

```text
ruff check .: passed
pytest: 10 passed
```

Frontend:

```text
npm run lint: passed
npm test -- --run: 3 passed
npm run build: passed
```

Migration and seed:

```text
alembic upgrade head: passed
python -m app.db.seed: passed
```

Docker:

```text
docker compose up --build -d: passed
PostgreSQL container: healthy
Backend container: running on port 8000
Frontend container: running on port 5173
Alembic migration: ran against PostgreSQL
Seed command: ran during backend startup
```

Containerized smoke test:

```text
GET /health: ok
GET /openapi.json: 200
GET frontend /: 200
POST /api/v1/auth/login: admin@example.com authenticated
GET /api/v1/orders: 5 seeded orders
GET /api/v1/orders/{id}: returned 2 items for sample order
PATCH /api/v1/orders/{id}: edited delivery address
POST /api/v1/orders/{id}/approve: Approved
POST /api/v1/orders/{id}/generate-xml: ERP Ready, 2 files
POST /api/v1/orders/{id}/send-xml: XMLs Sent
GET /api/v1/orders?status=Waiting for Reply: 1 order
```

GitHub Actions:

```text
CI workflow on main: completed successfully
CI workflow on develop and feature branches: completed successfully
```

## Fully Implemented

- Repository structure, `.gitignore`, `.env.example`, README, contribution guide, license, CI workflow, issue template, and pull request template.
- Week 2 design files copied to `docs/week-2/`.
- PostgreSQL-oriented SQLAlchemy models for users, clients, emails, orders, order items, attachments, validation issues, generated XMLs, and feedback issues.
- Initial Alembic migration.
- Realistic anonymized seed data with two clients, two users, five orders, at least eight items, required statuses, attachments, validation issues, generated XML records, and feedback issue data.
- FastAPI application with CORS, logging, `/api/v1` routes, JWT login, clients, orders, reports, feedback, validation, XML generation, and simulated XML sending.
- React dashboard layout and required pages.
- Orders table search/filter/pagination API support.
- Order Details page with header editing, item editing, approval, rejection, feedback issue reporting, XML generation, and separate XML sending action.
- Backend and frontend automated tests.
- Screenshot evidence for local UI/API views.
- Hosted GitHub repository with description, topics, pushed branches, labels, milestones, and 17 Week 3 issues.

## Mocked or Simulated

- Outlook/Microsoft Graph email monitoring and clarification sending.
- OpenAI extraction through a mock extraction service.
- OCR through a mock OCR interface.
- ERP XML transmission through `simulate_send_xml`.
- Hosted GitHub Issues backlog and local HTML board are used as the Week 3 board equivalent instead of a GitHub Project.

## Partially Implemented

- Data Export page is a UI shell; real Excel export is planned later.
- User and Settings pages are functional shells only.
- Authentication protects approval but broader role-based authorization is not complete.
- Document processing service functions are scaffolded for PDF, Word, Excel, CSV, and image/OCR paths, but full ingestion orchestration is future work.
- Waiting-for-Reply continuity is represented in data design with conversation IDs, but live reply ingestion is not implemented in Week 3.
- Hosted GitHub Project board is not created because the current GitHub token lacks `project` and `read:project` scopes.

## Planned for Future Sprints

- Real Microsoft Graph inbox monitoring and same-thread reply matching.
- Real OpenAI structured extraction with database-managed prompts and confidence/source persistence for every field.
- Full OCR execution with Tesseract and scanned PDF image conversion.
- Excel export generation.
- Prompt versioning, email templates, processing logs, extracted fields, and audit history tables.
- Role-based authorization for administration, approvals, prompt changes, and XML sending.
- Real ERP adapter after the employee clicks `Send XMLs`.
- Hosted GitHub Project board if project OAuth scope is granted.
- Repository protection rules if repository permissions and course workflow require them.

## Known Limitations

- No real customer data is included.
- No credentials are committed.
- The app does not claim real Outlook, OpenAI, OCR, or ERP operation.
- Generated XML files are simple sample XML files for Week 3 validation.
- The hosted repository is private. Mentor/reviewer access must be granted from GitHub if external review is required.
- Creating a hosted GitHub Project requires refreshing GitHub CLI auth with `gh auth refresh -h github.com -s project,read:project`.
