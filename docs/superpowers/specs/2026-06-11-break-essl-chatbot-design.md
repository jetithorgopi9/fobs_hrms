# Break Management, eSSL Sync, and Local AI Chatbot Design

## Goal

Add three connected capabilities to FOBS:

- Break Management in the Employee Self Service portal.
- Real-time eSSL/eTimeTrackLite punch syncing into FOBS attendance.
- A local/provider-based AI chatbot for HR data, file summaries, and writing/formula assistance.

The implementation must preserve the existing Frappe HRMS attendance flow. eSSL punches should become `Employee Checkin` records so current Auto Attendance and Shift Type behavior continue to work.

## Current Context

FOBS is based on Frappe HRMS. The existing code already includes:

- ESS/mobile frontend under `frontend/src`.
- Attendance routes under `frontend/src/router/attendance.js`.
- Employee check-in UI in `frontend/src/components/CheckInPanel.vue`.
- Employee check-in history in `frontend/src/views/attendance/EmployeeCheckinList.vue`.
- Backend HRMS doctypes under `hrms/hr/doctype`.
- Auto Attendance via `Employee Checkin` and `Shift Type`.

The production deployment currently runs FOBS on Docker with web traffic proxied to the Frappe development server. The new features should be designed at the app level and should not depend on the current port mapping.

## Architecture

Use the FOBS app as the source of truth for break logs, employee attendance visibility, permissions, and chatbot UI. Use a separate office LAN sync agent for eSSL because the eSSL SQL Server is inside the office network and should not be exposed publicly.

Data flow:

```text
eSSL SQL Server/eTimeTrackLite
        |
        v
Office LAN Sync Agent
        |
        v HTTPS API
FOBS eSSL Raw Punch Log
        |
        v
Employee Checkin
        |
        v
Auto Attendance / ESS Attendance Views / Break Eligibility
```

Chatbot flow:

```text
ESS/Desk Chat UI
        |
        v
FOBS Chat API and Permission Guard
        |
        v
Configured AI Provider
Ollama / LM Studio / OpenAI-compatible local endpoint
```

## Phase 1: Break Management

### New Doctype: Break Type

Purpose: Let HR Manager and Supervisor define selectable break types.

Fields:

- `break_name` Data, required.
- `active` Check, default enabled.
- `default_max_duration_minutes` Int.
- `paid_break` Check.
- `allow_employee_selection` Check, default enabled.
- `minimum_gap_after_previous_break_minutes` Int, default `45`.

Permissions:

- HR Manager: create, read, update, delete.
- Supervisor: create, read, update.
- Employee Self Service: read active records only through server APIs.

### New Doctype: Employee Break Log

Purpose: Store employee break sessions.

Fields:

- `employee` Link to Employee, required.
- `employee_name` Data, fetched/display only.
- `break_type` Link to Break Type, required.
- `start_time` Datetime, required.
- `stop_time` Datetime.
- `duration_minutes` Float.
- `status` Select: `Active`, `Completed`, `Auto Closed`, `Cancelled`.
- `source` Select: `ESS Portal`, `HR Desk`, `API`.
- `linked_first_checkin` Link to Employee Checkin.
- `linked_last_checkout` Link to Employee Checkin.

Rules:

- An employee can have only one `Active` break at a time.
- An employee can start a break only after the first IN punch for the day exists.
- An employee can start a new break only after 45 minutes have passed since their previous completed break stopped.
- The 45-minute gap should come from the selected Break Type, defaulting to 45 if empty.
- Employees can select any active Break Type once eligible.
- Stop Break sets `stop_time`, calculates `duration_minutes`, and marks the log `Completed`.

### ESS Portal Behavior

Add a Break Management tab/card to the ESS portal.

Visible state:

- Today first IN punch.
- Today latest OUT punch, if any.
- Active break, if one exists.
- Today break history.
- Start Break button if eligible.

Start flow:

- Employee selects an active Break Type.
- Server validates employee identity, first IN punch, no active break, and 45-minute gap.
- Server creates `Employee Break Log` with `status = Active`.
- Frontend opens an active break popup.

Active break popup:

- Shows break type.
- Shows start time.
- Shows real-time running clock.
- Has only one action: `Stop Break`.
- Popup cannot start a second break.

Stop flow:

- Employee taps Stop Break.
- Server validates the active break belongs to current user.
- Server records `stop_time`, `duration_minutes`, and `status = Completed`.
- Frontend closes popup and refreshes today history.

### HR and Supervisor Views

HR Manager:

- Can see all break logs.
- Can filter by employee, department, date, status, and break type.
- Can manage Break Types.

Supervisor:

- Can see break logs only for employees reporting to them.
- Can manage Break Types.

Employee:

- Can see only their own break logs in ESS.

## Phase 2: eSSL Sync

### Deployment Model

Use a small sync agent inside the office LAN. The agent connects to the eSSL/eTimeTrackLite SQL Server directly, then pushes records to FOBS over HTTPS.

Reason:

- SQL Server remains private inside office LAN.
- No SQL Server port is exposed publicly.
- The agent can be restarted independently.
- The FOBS VPS receives normalized punch logs only.

### New Doctype: eSSL Sync Source

Purpose: Represent each sync agent/source authorized to send logs.

Fields:

- `source_name` Data, required.
- `active` Check, default enabled.
- `api_user` Link to User or generated integration user.
- `last_successful_sync` Datetime.
- `last_error` Text.
- `allowed_device_ids` Table or child rows with device identifiers.

Permissions:

- System Manager and HR Manager can configure.
- Sync agent can access only the API endpoints assigned to its source.

### New Doctype: eSSL Raw Punch Log

Purpose: Store imported raw punch logs and dedupe before creating `Employee Checkin`.

Fields:

- `source` Link to eSSL Sync Source.
- `essl_user_id` Data, required.
- `punch_time` Datetime, required.
- `device_id` Data.
- `raw_log_id` Data.
- `raw_hash` Data, unique fallback for dedupe.
- `sync_status` Select: `Pending`, `Linked`, `Skipped`, `Error`.
- `linked_employee` Link to Employee.
- `linked_employee_checkin` Link to Employee Checkin.
- `error_message` Small Text.

Rules:

- Deduplicate by `source + raw_log_id` when raw log ID exists.
- Otherwise deduplicate by `source + essl_user_id + punch_time + device_id`.
- Map eSSL `UserId` to Employee `attendance_device_id`.
- Create an `Employee Checkin` record for mapped employees.
- Preserve unmapped logs with `sync_status = Error` and a clear error message.

### FOBS Sync API

Provide an authenticated API endpoint for the office sync agent.

Endpoint behavior:

- Accept batch punch logs.
- Validate source active status.
- Validate allowed device IDs when configured.
- Deduplicate logs.
- Create raw punch rows.
- Create or link Employee Checkin rows.
- Return per-row statuses to the agent.

Employee Checkin mapping:

- `employee`: mapped Employee.
- `time`: punch timestamp.
- `device_id`: eSSL device ID or source name.
- `log_type`: only set when reliable from eSSL. If eSSL log type is unclear, leave blank and let Shift Type Auto Attendance infer IN/OUT.

### Office LAN Sync Agent

The agent runs near the eSSL SQL Server and polls every 30-60 seconds.

Responsibilities:

- Connect to SQL Server/eTimeTrackLite.
- Read the current monthly `DeviceLogs_MM_YYYY` table.
- Also check the previous month table for the first day of a month.
- Keep a local cursor/state file or SQLite DB.
- Push new logs to FOBS over HTTPS.
- Retry failed pushes.
- Log sync errors clearly.

The first implementation targets SQL Server/eTimeTrackLite. MySQL/MS Access can be separate future connectors.

### Attendance and Break Interaction

After the first IN punch is synced into `Employee Checkin`, the ESS Break Management tab becomes eligible for Start Break. After an OUT punch exists, the ESS portal displays latest logout information.

Break logic should read `Employee Checkin`, not the raw eSSL table, so mobile/manual checkins can still work if enabled.

## Phase 3: Local AI Chatbot

### Provider Settings

New single doctype: AI Provider Settings.

Fields:

- `enabled` Check.
- `provider_type` Select: `Ollama`, `LM Studio`, `OpenAI Compatible`.
- `base_url` Data.
- `model` Data.
- `api_key` Password, optional.
- `timeout_seconds` Int, default 60.
- `file_retention_days` Int, configurable values such as 7, 30, 90, or custom.

All provider calls go through the FOBS backend. The frontend never calls the AI provider directly.

### Chat UI

Add a chatbot window/tab in ESS and Desk.

Capabilities:

- Employee self-service HR questions about own attendance, breaks, leave, and salary slips.
- HR/Admin questions based on their normal role access.
- Excel summary.
- Word/PDF summary.
- Statement correction/rewrite.
- Formula/help text generation.

### Permission Guard

All data access must happen through server-side tools with explicit permission checks.

Rules:

- Employee users can access only their own HR data.
- HR Manager and System Manager can access broader data according to existing Frappe permissions.
- Supervisors can access subordinate/team data only where supervisor relationships allow it.
- The AI model never receives unrestricted database access.
- Every tool call is logged with user, timestamp, tool name, target doctype/document, and result status.

### File Handling

Files uploaded for chat should be stored in private File records or temporary private storage according to admin retention settings.

Retention:

- Admin config controls deletion after 7, 30, 90, or custom days.
- A scheduled job deletes expired chat uploads.
- File summaries should avoid exposing file contents to unauthorized users.

## Security Requirements

- eSSL sync agent uses HTTPS and token-based authentication.
- SQL Server credentials stay only in the office LAN agent configuration.
- FOBS never stores SQL Server password.
- Break APIs derive employee identity from the logged-in user, not client-submitted employee IDs.
- Chatbot APIs enforce permissions server-side before any model prompt is assembled.
- Chatbot provider URL and API key are visible only to System Manager.
- Audit logs are required for eSSL sync batches, break changes, and chatbot tool calls.

## Error Handling

Break Management:

- If no first IN punch exists, return a clear message: "You can start a break after your first office punch is synced."
- If an active break exists, return the active break details.
- If the 45-minute gap is not complete, return the remaining wait time.

eSSL Sync:

- If an employee mapping is missing, store the raw log and mark it Error.
- If API call fails, the agent retries with backoff.
- If the monthly eSSL table is missing, the agent logs the issue and continues polling.

Chatbot:

- If provider is disabled, show "AI assistant is not enabled."
- If provider times out, show a retryable error.
- If a user asks for unauthorized data, return a refusal without calling the model for that data.

## Testing Strategy

Break Management:

- Unit tests for start/stop validation.
- Tests for active break uniqueness.
- Tests for 45-minute gap enforcement.
- Permission tests for employee, supervisor, and HR Manager.

eSSL Sync:

- Unit tests for dedupe logic.
- Unit tests for employee mapping.
- API tests for batch ingest.
- Agent tests using mocked SQL Server rows.

Chatbot:

- Provider adapter tests with mocked responses.
- Permission guard tests for employee, supervisor, and HR/Admin.
- File retention scheduled job tests.

## Implementation Phases

1. Break backend doctypes, permissions, and APIs.
2. ESS Break Management frontend with active break timer popup.
3. HR/Supervisor break list/report views.
4. eSSL FOBS sync source, raw punch log, ingest API, and checkin creation.
5. Office LAN eSSL sync agent for SQL Server/eTimeTrackLite.
6. AI provider settings, chatbot backend, and provider adapter.
7. Chatbot UI, HR data tools, file tools, audit logs, and retention cleanup.

## Open Operational Inputs

These values are needed during implementation/deployment, but they do not block the app design:

- eSSL SQL Server host inside office LAN.
- eSSL SQL Server database name.
- Actual current `DeviceLogs_MM_YYYY` table structure.
- eSSL `UserId` to Employee `attendance_device_id` mapping policy.
- First local AI provider to test, such as Ollama, LM Studio, or another OpenAI-compatible endpoint.
