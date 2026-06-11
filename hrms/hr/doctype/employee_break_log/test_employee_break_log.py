from datetime import datetime, timedelta

import frappe
from frappe.utils import get_time, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.employee_break_log.employee_break_log import (
	start_employee_break,
	stop_employee_break,
)
from hrms.tests.utils import HRMSTestSuite


class TestEmployeeBreakLog(HRMSTestSuite):
	def setUp(self):
		frappe.db.delete("Employee Break Log")
		frappe.db.delete("Break Type")
		frappe.db.delete("Employee Checkin")

	def test_start_break_requires_first_checkin(self):
		employee = make_employee("break_requires_checkin@example.com", company="_Test Company")
		break_type = make_break_type("Tea Break")

		with self.assertRaises(frappe.ValidationError):
			start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:00:00")))

	def test_employee_cannot_have_two_active_breaks(self):
		employee = make_employee("single_active_break@example.com", company="_Test Company")
		break_type = make_break_type("Lunch Break")
		make_checkin(employee, datetime.combine(getdate(), get_time("09:00:00")))

		start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:00:00")))

		with self.assertRaises(frappe.ValidationError):
			start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:15:00")))

	def test_stop_break_sets_duration_and_completed_status(self):
		employee = make_employee("stop_break@example.com", company="_Test Company")
		break_type = make_break_type("Personal Break")
		make_checkin(employee, datetime.combine(getdate(), get_time("09:00:00")))

		start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:00:00")))
		break_log = stop_employee_break(employee, datetime.combine(getdate(), get_time("10:20:00")))

		self.assertEqual(break_log.status, "Completed")
		self.assertEqual(break_log.duration_minutes, 20)
		self.assertEqual(break_log.stop_time, datetime.combine(getdate(), get_time("10:20:00")))

	def test_start_break_enforces_gap_after_previous_break(self):
		employee = make_employee("break_gap@example.com", company="_Test Company")
		break_type = make_break_type("Short Break", minimum_gap_after_previous_break_minutes=45)
		make_checkin(employee, datetime.combine(getdate(), get_time("09:00:00")))

		start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:00:00")))
		stop_employee_break(employee, datetime.combine(getdate(), get_time("10:10:00")))

		with self.assertRaises(frappe.ValidationError):
			start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:40:00")))

		break_log = start_employee_break(employee, break_type.name, datetime.combine(getdate(), get_time("10:55:00")))
		self.assertEqual(break_log.status, "Active")


def make_break_type(break_name, minimum_gap_after_previous_break_minutes=45):
	return frappe.get_doc(
		{
			"doctype": "Break Type",
			"break_name": break_name,
			"active": 1,
			"allow_employee_selection": 1,
			"minimum_gap_after_previous_break_minutes": minimum_gap_after_previous_break_minutes,
		}
	).insert()


def make_checkin(employee, time, log_type="IN"):
	return frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": employee,
			"time": time,
			"device_id": "device1",
			"log_type": log_type,
		}
	).insert()
