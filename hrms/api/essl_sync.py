import hmac

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from hrms.hr.doctype.employee_checkin.employee_checkin import add_log_based_on_employee_field


@frappe.whitelist(allow_guest=True, methods=["POST"])
def push_punch_logs(logs, api_secret: str | None = None) -> dict:
	"""Receive eSSL punch logs from the office LAN sync agent."""
	validate_sync_secret(api_secret)

	if isinstance(logs, str):
		logs = frappe.parse_json(logs)

	if not isinstance(logs, list):
		frappe.throw(_("logs must be a list of punch records."))

	settings = frappe.get_single("ESSL Sync Settings")
	results = [sync_one_punch_log(row, settings) for row in logs]
	frappe.db.set_single_value("ESSL Sync Settings", "last_sync_time", now_datetime())

	return {
		"received": len(logs),
		"synced": len([row for row in results if row["status"] == "Synced"]),
		"skipped": len([row for row in results if row["status"] == "Skipped"]),
		"errors": len([row for row in results if row["status"] == "Error"]),
		"results": results,
	}


def validate_sync_secret(api_secret: str | None):
	settings = frappe.get_single("ESSL Sync Settings")
	configured_secret = frappe.conf.get("essl_sync_api_secret") or settings.get_password(
		"sync_api_secret"
	)

	if not settings.enabled:
		frappe.throw(_("ESSL sync is disabled."))

	if not configured_secret:
		frappe.throw(_("ESSL sync API secret is not configured."))

	if not api_secret or not hmac.compare_digest(str(api_secret), str(configured_secret)):
		frappe.throw(_("Invalid ESSL sync API secret."))


def sync_one_punch_log(row: dict, settings) -> dict:
	source_log_id = row.get("source_log_id") or row.get("id")
	employee_field_value = row.get("employee_field_value") or row.get("device_user_id")
	punch_time = row.get("punch_time") or row.get("timestamp")
	log_type = normalize_log_type(row.get("log_type"))
	device_id = row.get("device_id")

	if source_log_id and frappe.db.exists("ESSL Punch Log", {"source_log_id": source_log_id}):
		return {"source_log_id": source_log_id, "status": "Skipped", "message": _("Duplicate log.")}

	punch_log = frappe.get_doc(
		{
			"doctype": "ESSL Punch Log",
			"source_log_id": source_log_id,
			"employee_field_value": employee_field_value,
			"punch_time": get_datetime(punch_time) if punch_time else None,
			"log_type": log_type,
			"device_id": device_id,
			"status": "Received",
			"raw_payload": frappe.as_json(row),
		}
	)

	try:
		punch_log.insert(ignore_permissions=True)
		checkin = add_log_based_on_employee_field(
			employee_field_value=employee_field_value,
			timestamp=punch_log.punch_time,
			device_id=device_id,
			log_type=log_type,
			skip_auto_attendance=settings.skip_auto_attendance,
			employee_fieldname=settings.employee_fieldname or "attendance_device_id",
		)
		punch_log.employee = checkin.employee
		punch_log.employee_checkin = checkin.name
		punch_log.status = "Synced"
		punch_log.save(ignore_permissions=True)
		frappe.db.commit()
		return {
			"source_log_id": source_log_id,
			"status": "Synced",
			"employee_checkin": checkin.name,
		}
	except Exception as exc:
		frappe.db.rollback()
		save_error_punch_log(punch_log, exc)
		return {
			"source_log_id": source_log_id,
			"status": "Error",
			"message": str(exc),
		}


def save_error_punch_log(punch_log, exc: Exception):
	punch_log.status = "Error"
	punch_log.error_message = str(exc)
	punch_log.flags.ignore_validate = True
	punch_log.insert(ignore_permissions=True)
	frappe.db.commit()


def normalize_log_type(log_type: str | None) -> str | None:
	if not log_type:
		return None

	log_type = str(log_type).strip().upper()
	if log_type in ("IN", "I", "CHECKIN", "CHECK-IN"):
		return "IN"
	if log_type in ("OUT", "O", "CHECKOUT", "CHECK-OUT"):
		return "OUT"

	return log_type
