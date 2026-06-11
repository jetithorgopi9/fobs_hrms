# Break Management Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation for Break Management: Break Type, Employee Break Log, and server APIs for ESS start/stop/status.

**Architecture:** Add Frappe doctypes under `hrms/hr/doctype`, with all employee identity and validation enforced server-side. ESS and future eSSL features read from existing `Employee Checkin` records; Break Management does not create attendance itself.

**Tech Stack:** Frappe Framework DocTypes, Python controllers, Frappe whitelisted APIs, HRMS test suite.

---

## File Structure

- Create `hrms/hr/doctype/break_type/`: Break Type doctype metadata and controller.
- Create `hrms/hr/doctype/employee_break_log/`: Employee Break Log doctype metadata, controller, and tests.
- Create `hrms/api/break_management.py`: ESS-facing API methods for status, active break types, start break, and stop break.
- Modify `hrms/setup.py`: add Employee Self Service permissions for Employee Break Log read access if needed by role setup.

## Task 1: Break Type Doctype

**Files:**
- Create: `hrms/hr/doctype/break_type/__init__.py`
- Create: `hrms/hr/doctype/break_type/break_type.py`
- Create: `hrms/hr/doctype/break_type/break_type.json`

- [ ] **Step 1: Add doctype metadata**

Create `break_type.json` with fields:

```json
{
 "actions": [],
 "allow_rename": 1,
 "creation": "2026-06-11 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "break_name",
  "active",
  "default_max_duration_minutes",
  "paid_break",
  "allow_employee_selection",
  "minimum_gap_after_previous_break_minutes"
 ],
 "fields": [
  {"fieldname": "break_name", "fieldtype": "Data", "label": "Break Name", "reqd": 1, "unique": 1},
  {"default": "1", "fieldname": "active", "fieldtype": "Check", "label": "Active"},
  {"fieldname": "default_max_duration_minutes", "fieldtype": "Int", "label": "Default Max Duration (Minutes)"},
  {"default": "0", "fieldname": "paid_break", "fieldtype": "Check", "label": "Paid Break"},
  {"default": "1", "fieldname": "allow_employee_selection", "fieldtype": "Check", "label": "Allow Employee Selection"},
  {"default": "45", "fieldname": "minimum_gap_after_previous_break_minutes", "fieldtype": "Int", "label": "Minimum Gap After Previous Break (Minutes)"}
 ],
 "index_web_pages_for_search": 1,
 "links": [],
 "modified": "2026-06-11 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "HR",
 "name": "Break Type",
 "owner": "Administrator",
 "permissions": [
  {"create": 1, "delete": 1, "email": 1, "export": 1, "print": 1, "read": 1, "report": 1, "role": "HR Manager", "share": 1, "write": 1},
  {"create": 1, "email": 1, "export": 1, "print": 1, "read": 1, "report": 1, "role": "Supervisor", "share": 1, "write": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 2: Add controller**

Create `break_type.py`:

```python
import frappe
from frappe.model.document import Document


class BreakType(Document):
	def validate(self):
		if self.minimum_gap_after_previous_break_minutes is None:
			self.minimum_gap_after_previous_break_minutes = 45
```

- [ ] **Step 3: Verify doctype imports**

Run: `python -m compileall hrms/hr/doctype/break_type`

Expected: exit code 0.

## Task 2: Employee Break Log Doctype and Validation

**Files:**
- Create: `hrms/hr/doctype/employee_break_log/__init__.py`
- Create: `hrms/hr/doctype/employee_break_log/employee_break_log.py`
- Create: `hrms/hr/doctype/employee_break_log/employee_break_log.json`
- Create: `hrms/hr/doctype/employee_break_log/test_employee_break_log.py`

- [ ] **Step 1: Write failing tests**

Create tests for:

```python
class TestEmployeeBreakLog(HRMSTestSuite):
	def test_employee_cannot_have_two_active_breaks(self):
		...

	def test_stop_break_sets_duration_and_completed_status(self):
		...

	def test_start_break_requires_first_checkin(self):
		...

	def test_start_break_enforces_gap_after_previous_break(self):
		...
```

Run: `bench --site test_site run-tests --app hrms --module hrms.hr.doctype.employee_break_log.test_employee_break_log`

Expected before implementation: failures because doctype/API does not exist.

- [ ] **Step 2: Add doctype metadata**

Create fields:

- `employee` Link Employee, required.
- `employee_name` Data, read only.
- `break_type` Link Break Type, required.
- `start_time` Datetime, required.
- `stop_time` Datetime.
- `duration_minutes` Float, read only.
- `status` Select `Active\nCompleted\nAuto Closed\nCancelled`, default Active.
- `source` Select `ESS Portal\nHR Desk\nAPI`, default ESS Portal.
- `linked_first_checkin` Link Employee Checkin.
- `linked_last_checkout` Link Employee Checkin.

Permissions:

- HR Manager full access.
- Supervisor read/report/write.
- Employee Self Service read own records through API; direct doctype write is not granted.

- [ ] **Step 3: Add controller validation**

Implement:

```python
class EmployeeBreakLog(Document):
	def validate(self):
		self.validate_active_employee()
		self.set_employee_name()
		self.validate_one_active_break()
		self.set_duration()
```

Rules:

- Active break cannot have `stop_time`.
- Completed/Auto Closed/Cancelled break must have `stop_time`.
- New active break cannot overlap another active break for same employee.
- Duration is calculated in minutes when `stop_time` exists.

- [ ] **Step 4: Add helper functions**

In `employee_break_log.py` implement:

- `get_first_checkin(employee, for_date)`
- `get_last_checkout(employee, for_date)`
- `get_active_break(employee)`
- `get_latest_completed_break(employee)`
- `validate_break_start(employee, break_type, now)`
- `start_employee_break(employee, break_type, now, source="ESS Portal")`
- `stop_employee_break(employee, now)`

- [ ] **Step 5: Run tests and commit**

Run the Employee Break Log test module.

Expected: all tests pass.

Commit:

```bash
git add hrms/hr/doctype/break_type hrms/hr/doctype/employee_break_log
git commit -m "feat: add break management doctypes"
```

## Task 3: ESS Break Management API

**Files:**
- Create: `hrms/api/break_management.py`
- Test: `hrms/hr/doctype/employee_break_log/test_employee_break_log.py`

- [ ] **Step 1: Write failing API tests**

Add tests for:

- `get_break_status` returns first checkin, last checkout, active break, history, and eligibility.
- `start_break` starts a break for the logged-in user's employee only.
- `stop_break` stops the logged-in user's active break.

Run the same test module.

Expected before implementation: failures because API methods do not exist.

- [ ] **Step 2: Implement employee lookup**

In `break_management.py`:

```python
def get_current_employee():
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("No Employee record is linked to the current user."))
	return employee
```

- [ ] **Step 3: Implement whitelisted APIs**

Add:

- `get_active_break_types()`
- `get_break_status()`
- `start_break(break_type)`
- `stop_break()`

All APIs derive `employee` from current session. None accepts employee from the client.

- [ ] **Step 4: Run tests and commit**

Run the API tests.

Expected: pass.

Commit:

```bash
git add hrms/api/break_management.py hrms/hr/doctype/employee_break_log/test_employee_break_log.py
git commit -m "feat: add break management api"
```

## Task 4: Minimal Frontend Status View

**Files:**
- Modify: `frontend/src/router/attendance.js`
- Create: `frontend/src/views/attendance/BreakManagement.vue`

- [ ] **Step 1: Add route**

Add:

```js
{
	name: "BreakManagementView",
	path: "/break-management",
	component: () => import("@/views/attendance/BreakManagement.vue"),
}
```

- [ ] **Step 2: Add status view wired to API**

Create a small working view that calls `hrms.api.break_management.get_break_status` and displays today's checkin/break state. The full timer popup belongs to Phase 2.

- [ ] **Step 3: Build frontend**

Run: `cd frontend && yarn build`

Expected: build succeeds.

Commit:

```bash
git add frontend/src/router/attendance.js frontend/src/views/attendance/BreakManagement.vue
git commit -m "feat: add break management ess route"
```

## Phase 1 Completion Checks

- [ ] Backend tests for Employee Break Log pass.
- [ ] Break APIs do not accept arbitrary employee IDs.
- [ ] 45-minute gap is enforced.
- [ ] Only one active break per employee is allowed.
- [ ] Frontend build succeeds.
- [ ] Push branch to GitHub for review.
