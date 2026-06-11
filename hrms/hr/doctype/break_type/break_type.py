from frappe.model.document import Document


class BreakType(Document):
	def validate(self):
		if self.minimum_gap_after_previous_break_minutes is None:
			self.minimum_gap_after_previous_break_minutes = 45
