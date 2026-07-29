# B2B AI Order Processing Agent

AI-powered B2B order-processing platform that classifies customer order emails, extracts structured data from documents, validates orders, supports human review, and generates ERP-ready XML files.

## Overview

This Week 3 implementation provides the project foundation and a working local vertical slice. A user can log in, view seeded orders, open an order, edit order data, approve it, generate Header and Items XML files, and separately simulate XML sending.

Amazon Bedrock structured extraction and AWS Textract/S3 document analysis are available alongside mock or simulated Outlook, OCR, and ERP boundaries.

## Problem

Suppliers receive orders through email in inconsistent customer formats, often with multiple attachment types. Manual order entry is slow, hard to audit, and risky when fields are missing or scanned documents reduce extraction confidence.

## Solution

The system stores client-specific prompts and rules, processes order evidence into structured records, validates required fields, routes uncertain orders to human review, and keeps ERP XML transmission under explicit operator control.

## Core Features

- FastAPI API with JWT login, clients, orders, feedback, reports, and XML endpoints.
- PostgreSQL schema with Alembic migration and realistic seed data.
- React + TypeScript dashboard with Overview, Orders, Order Details, Clients, Data Export, Feedback & Issues, Users, and Settings pages.
- Selectable Amazon Bedrock or mock AI extraction service and mock email service interface.
- Validation and decision services aligned with the Week 2 design.
- Separate approval, XML generation, and simulated XML sending actions.
- Docker Compose environment for PostgreSQL, backend, and frontend.

## Architecture Summary

The MVP is a modular FastAPI monolith with a React dashboard, PostgreSQL database, and local file storage. AI extraction is isolated behind a provider interface with Amazon Bedrock and mock implementations; other external dependencies remain behind replaceable service interfaces.

## Technology Stack

- Frontend: React, TypeScript, Vite, React Router, Vitest, ESLint, Prettier
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, Pytest, Ruff
- Database: PostgreSQL
- Storage: Local filesystem
- Deployment: Docker and Docker Compose

## Team Members

- Lea Murturi - AI extraction, validation, and decision logic
- Endi Hyseni - backend infrastructure, database, documents, OCR, and Docker
- Imane - frontend dashboard and user experience

## Repository Structure

```text
backend/          FastAPI app, models, services, tests, Alembic
frontend/         React dashboard
database/         Seed and sample database notes
docs/             Week 2 references, diagrams, API notes, Week 3 report
sample-data/      Demo clients, orders, and document notes
storage/          Local runtime storage for emails, attachments, XML
```

## Local Setup

Copy the example environment file before running locally:

```bash
cp .env.example .env
```

For Docker-first development, no host Python or Node setup is required beyond Docker.

## Docker Setup

```bash
docker compose up --build
```

The services run on:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

The backend container waits for PostgreSQL, applies Alembic migrations, creates the required login users, and starts FastAPI. Demo orders are disabled by default; set `SEED_DEMO_DATA=true` only in an isolated demonstration environment.

## Environment Variables

Use `.env.example` as the source of placeholders. Do not commit `.env`. Microsoft Graph and OpenAI values remain optional placeholders.

### Amazon Bedrock extraction

The backend calls Amazon Bedrock through Boto3's `bedrock-runtime` client and the model-neutral Converse API. Set these values in `.env`:

```dotenv
AI_PROVIDER=bedrock
AWS_REGION=eu-central-1
AWS_PROFILE=your-local-aws-profile
BEDROCK_MODEL_ID=your-enabled-model-or-inference-profile-id
BEDROCK_MAX_TOKENS=4096
BEDROCK_TEMPERATURE=0
```

`AWS_PROFILE` is optional. Boto3 can instead use its standard credential chain, including `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, an ECS task role, or an EC2 instance role. The active principal needs `bedrock:InvokeModel` permission for the configured model or inference profile, and that model must be available in the selected region.

After login, call `POST /api/v1/extraction/order` with extracted document text:

```json
{
  "client_prompt": "Extract the purchase order fields and line items.",
  "email_content": "The order email body",
  "documents": [
    {
      "file_name": "order.txt",
      "content": "Text previously extracted from the attachment"
    }
  ]
}
```

The endpoint returns fields with their source, source filename, and confidence. Set `AI_PROVIDER=mock` to use the deterministic local fallback without contacting AWS.

### Gmail automatic email intake

Gmail inbox retrieval uses IMAP over TLS. SMTP is used only when the application later sends acknowledgements or clarification requests. Enable two-step verification on the Google account, create a Google App Password, and configure:

```dotenv
GMAIL_INGESTION_ENABLED=true
GMAIL_USERNAME=orders@example.com
GMAIL_APP_PASSWORD=your-16-character-google-app-password
GMAIL_IMAP_FOLDER=INBOX
GMAIL_SEARCH_CRITERIA=UNSEEN
GMAIL_POLL_INTERVAL_SECONDS=60
GMAIL_MAX_MESSAGES_PER_POLL=25
GMAIL_MARK_AS_READ=true
```

When enabled, the backend polls Gmail, stores the raw `.eml` and attachments, prevents duplicate imports using `Message-ID`, classifies the email, and creates database orders from supported Lutz/Lesnina body formats. Recognized customers are matched by sender domain; a minimal profile client is created on first intake if no matching client exists.

When `TEXTRACT_AUTO_PROCESSING_ENABLED=true`, PDF, TIFF, PNG, and JPEG attachments are uploaded to the configured S3 bucket and submitted to Amazon Textract automatically. The background worker persists job state, detected text, completion time, and errors. Order Details shows the processing status and extracted text. Scanned orders remain in Human in the Loop until their OCR evidence is reviewed or mapped into structured order fields.

After login, the connection can be checked without waiting for the timer:

- `GET /api/v1/emails/gmail/status` reports configuration without exposing the password.
- `POST /api/v1/emails/gmail/poll` performs one immediate inbox poll.

For local S3 and Textract access, configure a dedicated least-privilege IAM identity:

```dotenv
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
TEXTRACT_AUTO_PROCESSING_ENABLED=true
TEXTRACT_POLL_INTERVAL_SECONDS=15
TEXTRACT_MAX_JOBS_PER_POLL=20
```

## Database Migration and Seed

Inside the backend container, startup runs:

```bash
alembic upgrade head
python -m app.db.seed
```

Manual local backend commands:

```bash
cd backend
alembic upgrade head
python -m app.db.seed
```

## Test Commands

```bash
cd backend
ruff check .
pytest

cd ../frontend
npm run lint
npm test
npm run build
```

## API Documentation

Swagger UI is available at http://localhost:8000/docs after the backend starts.

## Week 3 Implementation Status

Implemented foundation:

- Repository structure and documentation
- Backend API, models, migration, seed data, tests
- Frontend dashboard pages and tests
- Docker Compose environment
- Amazon Bedrock and mock AI extraction providers
- Mocked email/OCR integration boundaries
- Simulated ERP XML sending

## Current Limitations

- Outlook ingestion is not connected to Microsoft Graph.
- Bedrock extraction requires valid AWS credentials, model access, and an explicitly configured model ID.
- Textract OCR text is persisted, but client-specific mapping from arbitrary scanned tables into order items still requires review or AI extraction.
- ERP transmission is simulated and does not contact a real ERP.
- Excel export page is a UI foundation only.

## Future Roadmap

- Real Microsoft Graph inbox monitoring and reply matching.
- Persist Bedrock extraction results into the end-to-end email-to-order workflow.
- OCR execution and richer document parsing pipeline.
- Audit log expansion and role-based access controls.
- Excel report generation and ERP adapter integration.
