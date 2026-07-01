PROJECT: B2B AI Order Processing Agent
PHASE: Week 3 — Implementation Start
TEAM:
- Lea Murturi
- Endi Hyseni
- Imane

OBJECTIVE

Complete all Week 3 requirements for the B2B AI Order Processing Agent.

The Week 2 design document is the source of truth for the architecture, database, workflows, screens, statuses, technology stack, and business rules.

Week 3 is complete when:

1. A professional GitHub repository exists.
2. The three team members are represented in the project documentation and task allocation.
3. A task board and implementation backlog exist.
4. The React frontend, FastAPI backend, PostgreSQL database, and Docker environment are initialized.
5. A working vertical slice can be demonstrated locally.
6. Initial implementation has begun across frontend, backend, database, and AI-related modules.
7. The repository contains meaningful commits, documentation, tests, and setup instructions.

Do not attempt to build the complete final product during Week 3. Build the foundation and one working end-to-end flow.

==================================================
1. PROJECT CONTEXT
==================================================

The application is a B2B AI Order Processing Agent for suppliers and distributors that receive customer orders through email.

The future complete workflow is:

1. Monitor a supplier Outlook inbox.
2. Classify an email as an order or non-order.
3. Identify the client.
4. Load the client-specific AI prompt and business rules.
5. Read the email body and attachments.
6. Support PDF, scanned PDF, image, Word, Excel, and CSV files.
7. Use OCR for scanned documents and images.
8. Extract structured header and item fields.
9. Store the source and confidence of every extracted field.
10. Validate the result using business rules.
11. Assign a status:
   - OK
   - Human in the Loop
   - Waiting for Reply
   - Failed
12. Allow an operator to review and edit the order.
13. Generate two ERP XML files:
   - Header XML
   - Items XML
14. Send XML files only after the employee manually clicks “Send XMLs”.

For Week 3, implement the foundation and a sample-order vertical slice. Outlook, OpenAI, OCR, email sending, and ERP transmission may use interfaces, mocks, or placeholders if the real integrations are not ready.

==================================================
2. TECHNOLOGY STACK
==================================================

Use the following stack:

Frontend:
- React
- TypeScript
- Vite
- React Router
- A simple maintainable styling solution
- Axios or Fetch for API communication

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Database:
- PostgreSQL

AI:
- OpenAI API integration interface
- Do not require a real API key for the basic application to run
- Provide a mock extraction mode

Document processing:
- pdfplumber
- Tesseract OCR
- Poppler where needed for PDF conversion
- python-docx
- openpyxl
- Python CSV library
- Pillow for images

Email:
- Future Microsoft Graph / Outlook integration
- Create an email service interface and mock implementation for Week 3

Authentication:
- JWT

Storage:
- Local file storage

Deployment:
- Docker
- Docker Compose

Testing:
- Pytest for backend
- Vitest or equivalent for frontend

Code quality:
- Ruff or Flake8 for Python
- ESLint for TypeScript
- Prettier for frontend formatting

==================================================
3. GITHUB REPOSITORY
==================================================

Create a GitHub repository named:

b2b-ai-order-processing-agent

Use this description:

AI-powered B2B order-processing platform that classifies customer order emails, extracts structured data from documents, validates orders, supports human review, and generates ERP-ready XML files.

Add the following repository topics where supported:

ai
fastapi
react
typescript
postgresql
ocr
document-processing
order-automation
erp
docker

Create these branches:

main
develop

Development work must use branches such as:

feature/project-foundation
feature/database-models
feature/orders-api
feature/frontend-layout
feature/orders-page
feature/mock-extraction
feature/docker-setup

Do not place secrets in the repository.

Add:

- .gitignore
- .env.example
- README.md
- CONTRIBUTING.md
- LICENSE if appropriate
- docs directory
- issue templates if practical
- pull request template

Protect main conceptually through documented workflow. If repository permissions allow, configure pull requests before merge.

==================================================
4. REPOSITORY STRUCTURE
==================================================

Create this structure:

b2b-ai-order-processing-agent/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py
│   │   │   │   ├── health.py
│   │   │   │   ├── orders.py
│   │   │   │   ├── clients.py
│   │   │   │   └── feedback.py
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── seed.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── client.py
│   │   │   ├── email.py
│   │   │   ├── order.py
│   │   │   ├── order_item.py
│   │   │   ├── attachment.py
│   │   │   ├── validation_issue.py
│   │   │   ├── generated_xml.py
│   │   │   └── feedback_issue.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── client.py
│   │   │   ├── order.py
│   │   │   ├── order_item.py
│   │   │   └── feedback.py
│   │   ├── repositories/
│   │   │   ├── orders.py
│   │   │   └── clients.py
│   │   ├── services/
│   │   │   ├── email/
│   │   │   ├── classification/
│   │   │   ├── client_detection/
│   │   │   ├── document_processing/
│   │   │   ├── ocr/
│   │   │   ├── extraction/
│   │   │   ├── validation/
│   │   │   ├── decision/
│   │   │   ├── xml/
│   │   │   └── reporting/
│   │   ├── main.py
│   │   └── __init__.py
│   ├── alembic/
│   ├── tests/
│   │   ├── test_health.py
│   │   ├── test_orders.py
│   │   └── test_validation.py
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   ├── orders/
│   │   │   ├── common/
│   │   │   └── charts/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── OverviewPage.tsx
│   │   │   ├── OrdersPage.tsx
│   │   │   ├── OrderDetailsPage.tsx
│   │   │   ├── ClientsPage.tsx
│   │   │   ├── DataExportPage.tsx
│   │   │   ├── FeedbackIssuesPage.tsx
│   │   │   ├── UsersPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── routes/
│   │   │   └── AppRoutes.tsx
│   │   ├── types/
│   │   │   ├── order.ts
│   │   │   ├── client.ts
│   │   │   └── user.ts
│   │   ├── utils/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── database/
│   ├── seed/
│   └── samples/
│
├── docs/
│   ├── week-2/
│   ├── diagrams/
│   ├── api/
│   └── week-3/
│
├── storage/
│   ├── emails/
│   ├── attachments/
│   └── xml/
│
├── sample-data/
│   ├── clients/
│   ├── orders/
│   └── documents/
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
│
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── docker-compose.yml
├── README.md
└── LICENSE

Do not create empty directories without adding a useful placeholder, README, or initial implementation.

==================================================
5. WEEK 2 DOCUMENTATION
==================================================

Copy the Week 2 files into:

docs/week-2/

Include:

- B2B_AI_Order_Processing_Agent_Week2_Design_Document.docx
- B2B_AI_Order_Processing_Agent_Week2_Design_Document.pdf
- FlowForge_Week2_Mermaid_Diagrams.md

Add a docs/week-2/README.md explaining that these files are the approved design reference for implementation.

==================================================
6. DATABASE FOUNDATION
==================================================

Implement the initial PostgreSQL schema with SQLAlchemy and Alembic.

Required Week 3 tables:

1. users
2. clients
3. emails
4. orders
5. order_items
6. attachments

Also create initial versions of:

7. validation_issues
8. generated_xmls
9. feedback_issues

Use UUIDs or integer IDs consistently. Do not mix strategies without reason.

Recommended fields:

USERS
- id
- full_name
- email
- password_hash
- role
- is_active
- created_at
- updated_at

CLIENTS
- id
- client_name
- customer_number
- default_email
- email_domain
- extraction_prompt
- required_fields as JSON
- validation_rules as JSON
- is_active
- created_at
- updated_at

EMAILS
- id
- external_message_id
- sender_email
- reply_to_email
- mail_to_email
- subject
- body
- received_at
- classification_status
- client_id
- created_at

ORDERS
- id
- email_id
- client_id
- ticket_number
- customer_number
- customer_name
- commission_number
- commission_name
- store_address
- delivery_address
- delivery_week
- order_date
- requested_delivery_date
- contact_person
- phone_number
- total_price
- currency
- status
- approved_by_user_id
- approved_at
- created_at
- updated_at

ORDER_ITEMS
- id
- order_id
- article_number
- model_number
- quantity
- unit_price
- total_price
- currency
- created_at
- updated_at

ATTACHMENTS
- id
- email_id
- order_id
- file_name
- file_type
- file_path
- is_scanned
- created_at

VALIDATION_ISSUES
- id
- order_id
- field_name
- issue_type
- message
- severity
- is_resolved
- created_at
- resolved_at

GENERATED_XMLS
- id
- order_id
- xml_type
- file_path
- status
- generated_at
- sent_at

FEEDBACK_ISSUES
- id
- order_id
- reported_by_user_id
- category
- title
- description
- status
- created_at
- resolved_at

Create an initial Alembic migration.

Create realistic, anonymized seed data.

Seed:

- One admin user
- One operator user
- At least two clients
- At least five orders
- At least eight order items
- Different statuses:
  - OK
  - Human in the Loop
  - Waiting for Reply
  - Failed
  - ERP Ready
- At least one validation issue
- At least one attachment record

Use fake business names and fake addresses.

==================================================
7. BACKEND IMPLEMENTATION
==================================================

Create a FastAPI application with:

- Application configuration from environment variables
- PostgreSQL session management
- CORS configured for the frontend
- Structured error handling
- Basic logging
- API prefix: /api/v1

Required endpoints:

GET /health

Expected response:

{
  "status": "ok",
  "service": "b2b-ai-order-processing-agent"
}

AUTHENTICATION

POST /api/v1/auth/login

Accept email and password.

Return:

- access_token
- token_type
- basic user information

Use secure password hashing.

CLIENTS

GET /api/v1/clients
GET /api/v1/clients/{client_id}

ORDERS

GET /api/v1/orders

Support query parameters:

- status
- client_id
- search
- date_from
- date_to
- page
- page_size

GET /api/v1/orders/{order_id}

Return:

- complete order header
- client information
- items
- email metadata
- attachments
- validation issues
- XML status

PATCH /api/v1/orders/{order_id}

Allow editable header fields.

PATCH /api/v1/orders/{order_id}/items/{item_id}

Allow editing:

- article_number
- model_number
- quantity
- unit_price

POST /api/v1/orders/{order_id}/approve

Set approval fields and appropriate status.

POST /api/v1/orders/{order_id}/reject

Require a rejection reason.

POST /api/v1/orders/{order_id}/report-issue

Create a feedback issue.

POST /api/v1/orders/{order_id}/generate-xml

For Week 3, generate simple sample XML files based on current order data.

Generate:

- header XML
- items XML

Store them under:

storage/xml/{order_id}/

POST /api/v1/orders/{order_id}/send-xml

For Week 3, simulate ERP sending.

Do not connect to a real ERP.

Return a clear simulated success result and update the XML/order status.

REPORTING

GET /api/v1/reports/summary

Return:

- total orders
- count by status
- count by client
- recent order count

FEEDBACK

GET /api/v1/feedback
POST /api/v1/feedback

==================================================
8. SERVICE INTERFACES
==================================================

Create clean service interfaces even where the real implementation is mocked.

Email service:

- fetch_new_emails()
- download_attachments()
- send_clarification_email()

Classification service:

- classify_email(subject, body, attachments)

Return:

- order
- not_order
- spam
- unknown

Client detection service:

- detect_client(sender, email_body, attachment_text)

Document processing service:

- detect_file_type()
- extract_pdf_text()
- extract_word_text()
- extract_excel_data()
- extract_csv_data()
- extract_image_text()

OCR service:

- run_ocr(file_path)

AI extraction service:

- extract_order(client_prompt, email_content, documents)

Create a mock extractor that returns structured sample data when no API key is configured.

Validation service:

Implement at least these validations:

- missing ticket number
- missing customer number
- missing commission number
- missing delivery address
- missing article number
- missing quantity
- invalid or non-positive quantity
- missing currency when price is present
- scanned/image document flag

Decision service:

Implement status rules:

- Technical exception → Failed
- Missing information requiring customer response → Waiting for Reply
- Scanned document, low-confidence result, or conflict → Human in the Loop
- All required fields valid → OK

XML service:

- generate_header_xml(order)
- generate_items_xml(order)
- simulate_send_xml(order)

==================================================
9. FRONTEND IMPLEMENTATION
==================================================

Create a professional React dashboard based on the Week 2 design.

Required layout:

- Sidebar navigation
- Top bar
- Responsive content area
- Consistent status badges
- Loading states
- Empty states
- Error messages

Navigation:

- Overview
- Orders
- Clients
- Data Export
- Feedback & Issues
- Users
- Settings

LOGIN PAGE

Create a functional login page.

Use JWT returned by the backend.

Store authentication safely for the MVP.

OVERVIEW PAGE

Display:

- Total orders
- OK count and percentage
- Human in the Loop count and percentage
- Waiting for Reply count and percentage
- Failed count and percentage
- ERP Ready count
- Recent orders table

Charts may use a simple chart library or placeholders if needed, but the KPI data must come from the backend.

ORDERS PAGE

Display a table with:

- Order ID
- Ticket number
- Commission number
- Client
- Received date
- Delivery week
- Status
- Action to view

Add:

- Search
- Status filter
- Client filter
- Pagination
- Status tabs or quick filters

Statuses:

- All
- OK
- Human in the Loop
- Waiting for Reply
- Failed
- ERP Ready
- XMLs Sent
- Rejected

ORDER DETAILS PAGE

Display:

- Order header fields
- Order items
- Client
- Status
- Original email metadata
- Attachments
- Validation issues
- XML status

Add working actions:

- Edit header data
- Edit item data
- Save corrections
- Approve
- Reject
- Report issue
- Generate XML
- Send XMLs using the simulated backend endpoint

The “Send XMLs” action must remain separate from approval and generation.

CLIENTS PAGE

Display:

- Client name
- Customer number
- Email domain
- Active/inactive status
- View action

Client details should show:

- extraction prompt
- required fields
- validation rules

DATA EXPORT PAGE

Create the UI structure for:

- Date range
- Client
- Status
- Export to Excel

A real Excel export is optional for Week 3. The page must be present and tracked for later completion.

FEEDBACK & ISSUES PAGE

Display feedback records.

Allow creating a basic issue.

USERS AND SETTINGS

Create functional page shells.

They do not need full administration features during Week 3.

==================================================
10. SAMPLE DATA AND DEMO SCENARIOS
==================================================

Create sample orders representing these cases:

ORDER 1 — OK
- Complete valid order
- Normal PDF source
- At least two items

ORDER 2 — HUMAN IN THE LOOP
- Scanned PDF or image attachment
- Valid extracted values
- Manual verification flag

ORDER 3 — WAITING FOR REPLY
- Missing commission number
- Clarification required

ORDER 4 — FAILED
- Simulated unsupported or corrupted attachment

ORDER 5 — ERP READY
- Approved
- Header and items XML generated
- XMLs not yet sent

Use fake client names.

Create simple dummy documents where useful, but do not include confidential or real customer files.

==================================================
11. DOCKER ENVIRONMENT
==================================================

Create docker-compose.yml with services:

- postgres
- backend
- frontend

Recommended ports:

- Frontend: 5173
- Backend: 8000
- PostgreSQL: 5432

Add health checks where practical.

The project must start with:

docker compose up --build

Provide database initialization instructions.

Avoid requiring manual installation outside Docker except Docker itself.

The backend must wait safely for PostgreSQL before migration or startup.

==================================================
12. ENVIRONMENT VARIABLES
==================================================

Create .env.example containing placeholders only:

APP_ENV=development
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=60

POSTGRES_DB=order_agent
POSTGRES_USER=order_agent
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://order_agent:change-me@postgres:5432/order_agent

OPENAI_API_KEY=
OPENAI_MODEL=

MICROSOFT_TENANT_ID=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_MAILBOX=

STORAGE_ROOT=/app/storage

FRONTEND_URL=http://localhost:5173
VITE_API_BASE_URL=http://localhost:8000/api/v1

Do not commit an actual .env file.

==================================================
13. TESTING
==================================================

Backend tests must include:

- Health endpoint works
- Login works with seed user
- Orders list returns seeded orders
- Order details returns items
- Missing-field validation works
- Scanned-document decision returns Human in the Loop
- Missing required information returns Waiting for Reply
- XML generation creates two files

Frontend tests should include at least:

- Orders page renders
- Status badge renders correctly
- Order details displays sample data

All tests should be runnable with documented commands.

==================================================
14. CI WORKFLOW
==================================================

Create a basic GitHub Actions workflow.

The workflow should:

Backend:
- Install Python dependencies
- Run linting
- Run tests

Frontend:
- Install Node dependencies
- Run linting
- Run tests
- Run production build

The CI workflow should not require real OpenAI, Outlook, or ERP credentials.

Use mocks and test configuration.

==================================================
15. README
==================================================

Create a professional README containing:

1. Project name
2. Overview
3. Problem
4. Solution
5. Core features
6. Architecture summary
7. Technology stack
8. Team members
9. Repository structure
10. Local setup
11. Docker setup
12. Environment variables
13. Database migration and seed instructions
14. Test commands
15. API documentation location
16. Week 3 implementation status
17. Current limitations
18. Future roadmap

Team section:

- Lea Murturi — AI extraction, validation, and decision logic
- Endi Hyseni — backend infrastructure, database, documents, OCR, and Docker
- Imane — frontend dashboard and user experience

Do not claim that real Outlook, OpenAI, or ERP integration works unless it has actually been implemented and tested.

==================================================
16. PROJECT BOARD
==================================================

Create a GitHub Project, Trello board, or equivalent.

Preferred board columns:

- Backlog
- Ready
- In Progress
- Code Review
- Testing
- Done

Create labels:

- frontend
- backend
- database
- ai
- ocr
- email
- xml
- documentation
- testing
- infrastructure
- bug
- enhancement
- priority-high
- priority-medium
- priority-low
- week-3
- future

Create milestones:

- Week 3 — Foundation
- Sprint 2 — AI and Document Processing
- Sprint 3 — Human Review and XML
- Final Integration and Testing

==================================================
17. WEEK 3 ISSUES
==================================================

Create separate issues for at least the following tasks.

ISSUE 1
Title:
Initialize repository and development standards

Owner:
Endi Hyseni

Acceptance criteria:
- Repository structure exists
- main and develop workflow documented
- .gitignore and .env.example exist
- pull request template exists

ISSUE 2
Title:
Configure Docker Compose development environment

Owner:
Endi Hyseni

Acceptance criteria:
- frontend, backend, and PostgreSQL start with Docker Compose
- services communicate successfully
- setup is documented

ISSUE 3
Title:
Initialize FastAPI backend

Owner:
Endi Hyseni

Acceptance criteria:
- FastAPI starts
- /health returns success
- configuration and logging exist
- Swagger documentation works

ISSUE 4
Title:
Create PostgreSQL models and migration

Owner:
Endi Hyseni

Acceptance criteria:
- core tables exist
- Alembic migration succeeds
- database relationships are valid

ISSUE 5
Title:
Create seed data and demo orders

Owner:
Endi Hyseni

Acceptance criteria:
- two clients exist
- five orders exist
- all required demo statuses are represented

ISSUE 6
Title:
Define AI extraction schema

Owner:
Lea Murturi

Acceptance criteria:
- header schema exists
- item schema exists
- source metadata exists
- confidence field exists
- schema is documented

ISSUE 7
Title:
Create mock AI extraction service

Owner:
Lea Murturi

Acceptance criteria:
- service interface exists
- works without an OpenAI key
- produces structured data for sample orders

ISSUE 8
Title:
Implement validation engine

Owner:
Lea Murturi

Acceptance criteria:
- missing required fields are detected
- invalid quantities are detected
- validation issues are persisted or returned consistently
- tests exist

ISSUE 9
Title:
Implement order decision engine

Owner:
Lea Murturi

Acceptance criteria:
- OK rule works
- Human in the Loop rule works
- Waiting for Reply rule works
- Failed rule works
- tests exist

ISSUE 10
Title:
Initialize React and TypeScript frontend

Owner:
Imane

Acceptance criteria:
- Vite project starts
- routing exists
- shared layout exists
- sidebar navigation exists

ISSUE 11
Title:
Build Overview dashboard

Owner:
Imane

Acceptance criteria:
- KPI cards render
- data comes from the backend
- recent orders are shown

ISSUE 12
Title:
Build Orders page

Owner:
Imane

Acceptance criteria:
- table renders backend data
- search works
- status filter works
- client filter works
- order can be opened

ISSUE 13
Title:
Build Order Details page

Owner:
Imane

Acceptance criteria:
- header data is visible
- items are visible
- validation issues are visible
- actions are present
- basic editing works

ISSUE 14
Title:
Implement order API endpoints

Owner:
Endi Hyseni and Lea Murturi

Acceptance criteria:
- list endpoint works
- details endpoint works
- update endpoint works
- approval endpoint works

ISSUE 15
Title:
Implement sample XML generation

Owner:
Lea Murturi or Endi Hyseni

Acceptance criteria:
- header XML generated
- items XML generated
- files saved locally
- endpoint returns status

ISSUE 16
Title:
Add automated tests and CI

Owner:
All team members

Acceptance criteria:
- backend tests pass
- frontend tests pass
- GitHub Actions passes

ISSUE 17
Title:
Add Week 2 design files and Week 3 documentation

Owner:
Lea Murturi

Acceptance criteria:
- Week 2 files are under docs/week-2
- Week 3 plan is under docs/week-3
- README references the design document

If GitHub usernames are unknown, create the issues without assigning accounts but include the responsible team member in each issue body.

==================================================
18. FIRST SPRINT
==================================================

Sprint name:

Week 3 — Project Foundation and First Vertical Slice

Sprint goal:

A user can run the complete system locally, log in, view seeded orders from PostgreSQL through the FastAPI API, open an order in the React dashboard, edit basic information, approve it, generate two sample XML files, and simulate sending them to the ERP.

Sprint must include:

- Repository setup
- Docker environment
- Database and seed data
- Backend endpoints
- Frontend dashboard structure
- Orders page
- Order details page
- Validation and decision foundations
- Sample XML generation
- Tests
- Documentation

==================================================
19. DEFINITION OF DONE
==================================================

A task is Done only when:

- Code is implemented
- Code runs locally
- Relevant tests pass
- Linting passes
- No secrets are committed
- Acceptance criteria are satisfied
- Documentation is updated
- Another team member could understand the implementation
- The task is linked to an issue or project-board card

==================================================
20. FINAL WEEK 3 DEMONSTRATION
==================================================

The final local demonstration must show:

1. docker compose up --build succeeds
2. PostgreSQL is running
3. FastAPI is available
4. /health works
5. Swagger API documentation opens
6. React frontend opens
7. Login works
8. Overview KPIs load
9. Orders page displays seeded orders
10. Status filters work
11. An order can be opened
12. Header and item information are displayed
13. At least one field can be edited
14. Order can be approved
15. Header XML can be generated
16. Items XML can be generated
17. XML transmission can be simulated only after clicking “Send XMLs”
18. Tests pass
19. Repository documentation is complete
20. Project board contains the backlog and team allocation

==================================================
21. REQUIRED FINAL OUTPUT FROM THE AGENT
==================================================

At completion, provide:

1. GitHub repository URL
2. Summary of created branches
3. Summary of project-board issues
4. Exact local startup commands
5. Seed login credentials for development
6. API documentation URL
7. List of implemented endpoints
8. List of implemented frontend pages
9. Test results
10. Known limitations
11. Screenshots of:
    - Overview page
    - Orders page
    - Order Details page
    - Swagger API
    - GitHub project board
12. A Week 3 completion report in:
    docs/week-3/WEEK_3_COMPLETION_REPORT.md

The completion report must clearly separate:

- Fully implemented
- Mocked or simulated
- Partially implemented
- Planned for future sprints

==================================================
22. IMPORTANT CONSTRAINTS
==================================================

- Do not use real customer data.
- Do not commit credentials.
- Do not claim that an integration works when it is mocked.
- Keep the architecture modular.
- Do not automatically send XMLs after approval.
- XML generation and XML sending must be separate actions.
- Waiting for Reply must update the same order when a reply arrives.
- Scanned PDFs and images must require Human-in-the-Loop review.
- Client prompts must be stored in the database.
- There is no manual “Reprocess Order” button.
- Operators edit incorrect fields directly.
- Reported extraction problems go to Feedback & Issues.
- The codebase must remain understandable for three student developers.
- Prefer a working simple implementation over an incomplete overengineered system.

Begin by inspecting the Week 2 design files, creating an implementation plan, then build the repository in small verified stages.