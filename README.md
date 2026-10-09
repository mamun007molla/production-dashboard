# Production Dashboard — FSE-01

A production event processing dashboard built with FastAPI, PostgreSQL, SQLAlchemy, Next.js, and MQTT.

## Features

- Submit production events through REST API.
- Process COUNT and VOID events.
- Detect duplicate and conflicting event submissions.
- Resolve pending VOID references when the target COUNT arrives.
- View production summaries, pending acknowledgements, and exceptions.
- Acknowledge eligible events through the API and dashboard.
- Receive MQTT challenges and publish correlated responses.
- Store event attempts and MQTT challenge responses for audit and replay handling.

## Technology Stack

- **Backend:** FastAPI, Python, SQLAlchemy
- **Database:** PostgreSQL
- **Frontend:** Next.js, React, Tailwind CSS
- **Messaging:** MQTT using Paho MQTT
- **Testing:** pytest

## Project Structure

```text
production-dashboard/
├── backend/
│   ├── app/
│   │   ├── database/
│   │   └── modules/
│   │       ├── acknowledgements/
│   │       ├── events/
│   │       ├── mqtt/
│   │       └── state/
│   ├── migrations/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── .env.example
├── .gitignore
├── README.md
├── TECHNICAL_EXPLANATION.md
└── AI_USAGE.md
```

## Prerequisites

- Python and pip
- Node.js and npm
- PostgreSQL
- Git

## Backend Setup

From the project root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and set a valid PostgreSQL connection string. Create the database and database user before running migrations.

Apply migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

API documentation:

- Swagger UI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Database health: http://127.0.0.1:8000/health/database

## Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

## Run Tests

From the backend directory, activate the virtual environment and run:

```bash
python -m pytest -q
```

The current development run reported 19 passing tests. Run the tests again after making changes.

## MQTT Configuration

The MQTT client reads its broker settings and candidate ID from the backend environment. The configured assessment broker is `152.42.238.142:1883`.

Topics:

- `fse-01/{candidate_id}/challenge`
- `fse-01/{candidate_id}/response`
- `fse-01/{candidate_id}/status`

Start the MQTT client from the backend directory:

```bash
python -m app.modules.mqtt.client
```

The broker is an external dependency, so a working local API does not by itself prove end-to-end MQTT operation.

## Security Notes

- Do not commit `.env` or `.env.local`.
- Use `.env.example` only for placeholders and non-secret defaults.
- Do not publish database passwords, tokens, or other credentials.
- The configured assessment broker uses plain MQTT; use only for the intended assessment environment.

## Status

Backend health, PostgreSQL connectivity, and the existing automated test suite have been checked during development. Verify all REST, frontend, and MQTT integration scenarios before treating the project as submission-ready.
