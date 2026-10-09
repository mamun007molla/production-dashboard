# Technical Explanation — FSE-01 Production Dashboard

## 1. Architecture

The project has three main components:

- **Next.js frontend:** Displays production metrics, submits events, shows pending acknowledgements and exceptions.
- **FastAPI backend:** Exposes REST endpoints and implements event processing, state reporting, acknowledgement, and MQTT challenge handling.
- **PostgreSQL:** Stores production sources, production events, submission attempts, acknowledgements, and MQTT challenges.

SQLAlchemy is used for database access, and Alembic manages schema migrations.

## 2. Event Processing

Each production event is identified by `(source_id, event_id)`.

- **COUNT:** Requires a positive integer quantity, a timezone-aware event timestamp, and no target event.
- **VOID:** Requires a target event ID and no quantity.
- **DUPLICATE:** Indicates a repeated identity with the same normalized payload.
- **CONFLICT:** Indicates a repeated identity with a different payload.
- **PENDING_REFERENCE:** Indicates that a VOID target has not arrived yet.

The event-processing service records submission attempts and applies the business rules. When a target COUNT arrives, the service checks for pending VOID references and attempts to resolve them.

## 3. Production State

`GET /api/state` provides the production summary.

Supported views:

- `summary`
- `pending`
- `exceptions`

An optional `source_id` filters the state to one source.

The summary includes `net_total`, `processed_events`, `pending_ack`, `unresolved`, `duplicates`, and `conflicts`.

Net production is calculated from accepted COUNT events after excluding counts reversed by accepted VOID events from the same source.

## 4. Acknowledgements

`POST /api/ack` accepts event IDs and returns an outcome for each requested event. The implementation distinguishes acknowledged events, events that are not ready, and events that do not exist.

## 5. MQTT Processing

The MQTT client subscribes to the candidate's challenge topic and publishes correlated responses and status updates.

The challenge-processing service validates the candidate ID, command, expiry, and event collection. It stores a digest of the request body and the resulting response for replay handling.

- Same challenge ID and same request digest: return the stored response when available.
- Same challenge ID and a different request digest: return `CHALLENGE_CONFLICT`.

The MQTT and REST event paths call the same event-processing service.

## 6. Testing and Limitations

Automated tests cover canonical JSON, payload digests, expiry parsing, response structure, replay decisions, and net production calculation.

The development test suite has reported 19 passing tests. This does not by itself establish that every PostgreSQL integration scenario or live MQTT broker challenge has passed.

Before submission, verify the API behavior, frontend workflows, acknowledgement edge cases, and live MQTT challenge/response flow.
