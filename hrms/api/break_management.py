import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from hrms.hr.doctype.employee_break_log.employee_break_log import (
	get_active_break,
	get_first_checkin,
	get_last_checkout,
	get_latest_completed_break,
	start_employee_break,
	stop_employee_break,
	validate_break_start,
)


def get_current_employee() -> str:
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("No Employee record is linked to the current user."))
	return employee


@frappe.whitelist()
def get_active_break_types() -> list[dict]:
	return frappe.get_all(
		"Break Type",
		filters={"active": 1, "allow_employee_selection": 1},
		fields=[
			"name",
			"break_name",
			"default_max_duration_minutes",
			"paid_break",
			"minimum_gap_after_previous_break_minutes",
		],
		order_by="break_name asc",
	)


@frappe.whitelist()
def get_break_status(timestamp: str | None = None) -> dict:
	employee = get_current_employee()
	timestamp = get_datetime(timestamp or now_datetime())
	first_checkin = get_first_checkin(employee, timestamp)
	last_checkout = get_last_checkout(employee, timestamp)
	active_break = get_active_break(employee)
	latest_completed_break = get_latest_completed_break(employee)
	break_types = get_active_break_types()

	can_start_break = False
	start_block_reason = None

	if not first_checkin:
		start_block_reason = _("You can start a break after your first office punch is synced.")
	elif active_break:
		start_block_reason = _("Employee already has an active break.")
	elif not break_types:
		start_block_reason = _("No active break types are available.")
	else:
		try:
			validate_break_start(employee, break_types[0].name, timestamp)
			can_start_break = True
		except frappe.ValidationError as exc:
			start_block_reason = str(exc)

	history = frappe.get_all(
		"Employee Break Log",
		filters={
			"employee": employee,
			"start_time": ("between", [f"{timestamp.date()} 00:00:00", f"{timestamp.date()} 23:59:59"]),
		},
		fields=[
			"name",
			"break_type",
			"start_time",
			"stop_time",
			"duration_minutes",
			"status",
		],
		order_by="start_time desc",
	)

	return {
		"employee": employee,
		"first_checkin": first_checkin,
		"last_checkout": last_checkout,
		"active_break": active_break,
		"latest_completed_break": latest_completed_break,
		"break_types": break_types,
		"history": history,
		"can_start_break": can_start_break,
		"start_block_reason": start_block_reason,
	}


@frappe.whitelist()
def start_break(break_type: str, timestamp: str | None = None) -> dict:
	employee = get_current_employee()
	break_log = start_employee_break(employee, break_type, timestamp, source="ESS Portal")
	return serialize_break_log(break_log)


@frappe.whitelist()
def stop_break(timestamp: str | None = None) -> dict:
	employee = get_current_employee()
	break_log = stop_employee_break(employee, timestamp)
	return serialize_break_log(break_log)


def serialize_break_log(break_log) -> dict:
	return {
		"name": break_log.name,
		"employee": break_log.employee,
		"break_type": break_log.break_type,
		"start_time": break_log.start_time,
		"stop_time": break_log.stop_time,
		"duration_minutes": break_log.duration_minutes,
		"status": break_log.status,
	}
