from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime, time_diff_in_hours

from hrms.hr.utils import validate_active_employee


class EmployeeBreakLog(Document):
	def validate(self):
		validate_active_employee(self.employee)
		self.set_employee_name()
		self.validate_status_and_times()
		self.validate_one_active_break()
		self.set_duration()

	def set_employee_name(self):
		if self.employee and not self.employee_name:
			self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")

	def validate_status_and_times(self):
		if self.status == "Active" and self.stop_time:
			frappe.throw(_("An active break cannot have a stop time."))

		if self.status in ("Completed", "Auto Closed", "Cancelled") and not self.stop_time:
			frappe.throw(_("Stop time is required for {0} break logs.").format(self.status))

		if self.stop_time and get_datetime(self.stop_time) < get_datetime(self.start_time):
			frappe.throw(_("Stop time cannot be before start time."))

	def validate_one_active_break(self):
		if self.status != "Active":
			return

		existing = frappe.db.exists(
			"Employee Break Log",
			{
				"employee": self.employee,
				"status": "Active",
				"name": ("!=", self.name),
			},
		)
		if existing:
			frappe.throw(_("Employee already has an active break."))

	def set_duration(self):
		if not self.stop_time:
			self.duration_minutes = 0
			return

		self.duration_minutes = time_diff_in_hours(self.stop_time, self.start_time) * 60


def get_first_checkin(employee: str, for_date=None):
	for_date = getdate(for_date or now_datetime())
	return frappe.db.get_value(
		"Employee Checkin",
		{
			"employee": employee,
			"time": ("between", [f"{for_date} 00:00:00", f"{for_date} 23:59:59"]),
		},
		["name", "time", "log_type", "device_id"],
		order_by="time asc",
		as_dict=True,
	)


def get_last_checkout(employee: str, for_date=None):
	for_date = getdate(for_date or now_datetime())
	return frappe.db.get_value(
		"Employee Checkin",
		{
			"employee": employee,
			"time": ("between", [f"{for_date} 00:00:00", f"{for_date} 23:59:59"]),
		},
		["name", "time", "log_type", "device_id"],
		order_by="time desc",
		as_dict=True,
	)


def get_active_break(employee: str):
	return frappe.db.get_value(
		"Employee Break Log",
		{"employee": employee, "status": "Active"},
		["name", "break_type", "start_time", "status"],
		as_dict=True,
	)


def get_latest_completed_break(employee: str):
	return frappe.db.get_value(
		"Employee Break Log",
		{"employee": employee, "status": "Completed"},
		["name", "break_type", "start_time", "stop_time", "duration_minutes"],
		order_by="stop_time desc",
		as_dict=True,
	)


def validate_break_start(employee: str, break_type: str, timestamp: datetime | str | None = None):
	timestamp = get_datetime(timestamp or now_datetime())
	break_type_doc = frappe.get_doc("Break Type", break_type)

	if not break_type_doc.active:
		frappe.throw(_("Break Type {0} is not active.").format(break_type))

	first_checkin = get_first_checkin(employee, timestamp)
	if not first_checkin:
		frappe.throw(_("You can start a break after your first office punch is synced."))

	if get_active_break(employee):
		frappe.throw(_("Employee already has an active break."))

	latest_completed_break = get_latest_completed_break(employee)
	if latest_completed_break and latest_completed_break.stop_time:
		minimum_gap = break_type_doc.minimum_gap_after_previous_break_minutes or 45
		next_allowed_time = add_to_date(latest_completed_break.stop_time, minutes=minimum_gap)
		if timestamp < get_datetime(next_allowed_time):
			frappe.throw(
				_("You can start another break after {0}.").format(
					frappe.format_value(next_allowed_time, {"fieldtype": "Datetime"})
				)
			)

	return first_checkin


def start_employee_break(
	employee: str,
	break_type: str,
	timestamp: datetime | str | None = None,
	source: str = "ESS Portal",
):
	timestamp = get_datetime(timestamp or now_datetime()).replace(microsecond=0)
	first_checkin = validate_break_start(employee, break_type, timestamp)

	break_log = frappe.get_doc(
		{
			"doctype": "Employee Break Log",
			"employee": employee,
			"break_type": break_type,
			"start_time": timestamp,
			"status": "Active",
			"source": source,
			"linked_first_checkin": first_checkin.name,
		}
	)
	break_log.insert()
	return break_log


def stop_employee_break(employee: str, timestamp: datetime | str | None = None):
	timestamp = get_datetime(timestamp or now_datetime()).replace(microsecond=0)
	active_break = get_active_break(employee)
	if not active_break:
		frappe.throw(_("No active break found."))

	break_log = frappe.get_doc("Employee Break Log", active_break.name)
	break_log.stop_time = timestamp
	break_log.status = "Completed"

	last_checkout = get_last_checkout(employee, timestamp)
	if last_checkout:
		break_log.linked_last_checkout = last_checkout.name

	break_log.save()
	return break_log
