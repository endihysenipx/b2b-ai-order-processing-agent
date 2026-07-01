# Week 3 Issues

## Done

### 1. Initialize repository and development standards
Owner: Endi Hyseni

Acceptance criteria:
- Repository structure exists
- main and develop workflow documented
- `.gitignore` and `.env.example` exist
- pull request template exists

### 2. Configure Docker Compose development environment
Owner: Endi Hyseni

Acceptance criteria:
- frontend, backend, and PostgreSQL start with Docker Compose
- services communicate successfully
- setup is documented

### 3. Initialize FastAPI backend
Owner: Endi Hyseni

Acceptance criteria:
- FastAPI starts
- `/health` returns success
- configuration and logging exist
- Swagger documentation works

### 4. Create PostgreSQL models and migration
Owner: Endi Hyseni

Acceptance criteria:
- core tables exist
- Alembic migration succeeds
- database relationships are valid

### 5. Create seed data and demo orders
Owner: Endi Hyseni

Acceptance criteria:
- two clients exist
- five orders exist
- all required demo statuses are represented

### 6. Define AI extraction schema
Owner: Lea Murturi

Acceptance criteria:
- header schema exists
- item schema exists
- source metadata exists
- confidence field exists
- schema is documented

### 7. Create mock AI extraction service
Owner: Lea Murturi

Acceptance criteria:
- service interface exists
- works without an OpenAI key
- produces structured data for sample orders

### 8. Implement validation engine
Owner: Lea Murturi

Acceptance criteria:
- missing required fields are detected
- invalid quantities are detected
- validation issues are persisted or returned consistently
- tests exist

### 9. Implement order decision engine
Owner: Lea Murturi

Acceptance criteria:
- OK rule works
- Human in the Loop rule works
- Waiting for Reply rule works
- Failed rule works
- tests exist

### 10. Initialize React and TypeScript frontend
Owner: Imane

Acceptance criteria:
- Vite project starts
- routing exists
- shared layout exists
- sidebar navigation exists

### 11. Build Overview dashboard
Owner: Imane

Acceptance criteria:
- KPI cards render
- data comes from the backend
- recent orders are shown

### 12. Build Orders page
Owner: Imane

Acceptance criteria:
- table renders backend data
- search works
- status filter works
- client filter works
- order can be opened

### 13. Build Order Details page
Owner: Imane

Acceptance criteria:
- header data is visible
- items are visible
- validation issues are visible
- actions are present
- basic editing works

### 14. Implement order API endpoints
Owner: Endi Hyseni and Lea Murturi

Acceptance criteria:
- list endpoint works
- details endpoint works
- update endpoint works
- approval endpoint works

### 15. Implement sample XML generation
Owner: Lea Murturi or Endi Hyseni

Acceptance criteria:
- header XML generated
- items XML generated
- files saved locally
- endpoint returns status

### 16. Add automated tests and CI
Owner: All team members

Acceptance criteria:
- backend tests pass
- frontend tests pass
- GitHub Actions passes

### 17. Add Week 2 design files and Week 3 documentation
Owner: Lea Murturi

Acceptance criteria:
- Week 2 files are under `docs/week-2`
- Week 3 plan is under `docs/week-3`
- README references the design document
