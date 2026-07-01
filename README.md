# B2B AI Order Processing Agent

AI-powered B2B order-processing platform that classifies customer order emails, extracts structured data from documents, validates orders, supports human review, and generates ERP-ready XML files.

## Overview

This Week 3 implementation provides the project foundation and a working local vertical slice. A user can log in, view seeded orders, open an order, edit order data, approve it, generate Header and Items XML files, and separately simulate XML sending.

Outlook, OpenAI, OCR, and ERP integrations are represented by interfaces and mock or simulated implementations for Week 3.

## Problem

Suppliers receive orders through email in inconsistent customer formats, often with multiple attachment types. Manual order entry is slow, hard to audit, and risky when fields are missing or scanned documents reduce extraction confidence.

## Solution

The system stores client-specific prompts and rules, processes order evidence into structured records, validates required fields, routes uncertain orders to human review, and keeps ERP XML transmission under explicit operator control.

## Core Features

- FastAPI API with JWT login, clients, orders, feedback, reports, and XML endpoints.
- PostgreSQL schema with Alembic migration and realistic seed data.
- React + TypeScript dashboard with Overview, Orders, Order Details, Clients, Data Export, Feedback & Issues, Users, and Settings pages.
- Mock AI extraction and email service interfaces.
- Validation and decision services aligned with the Week 2 design.
- Separate approval, XML generation, and simulated XML sending actions.
- Docker Compose environment for PostgreSQL, backend, and frontend.

## Architecture Summary

The MVP is a modular FastAPI monolith with a React dashboard, PostgreSQL database, and local file storage. External Outlook, OpenAI, OCR, and ERP dependencies are isolated behind service interfaces so real integrations can replace Week 3 mocks in later sprints.

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

The backend container waits for PostgreSQL, applies Alembic migrations, seeds demo data, and starts FastAPI.

## Environment Variables

Use `.env.example` as the source of placeholders. Do not commit `.env`. `OPENAI_API_KEY`, Microsoft Graph credentials, and ERP details are optional placeholders during Week 3.

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
- Mocked AI/email/OCR integration boundaries
- Simulated ERP XML sending

## Current Limitations

- Outlook ingestion is not connected to Microsoft Graph.
- OpenAI extraction uses a mock mode unless future credentials and implementation are added.
- OCR service interface is present, but real Tesseract execution is not required for the Week 3 demo.
- ERP transmission is simulated and does not contact a real ERP.
- Excel export page is a UI foundation only.

## Future Roadmap

- Real Microsoft Graph inbox monitoring and reply matching.
- Real OpenAI structured extraction with client-specific prompts.
- OCR execution and richer document parsing pipeline.
- Audit log expansion and role-based access controls.
- Excel report generation and ERP adapter integration.
