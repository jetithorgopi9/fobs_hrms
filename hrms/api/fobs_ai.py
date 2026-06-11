import requests

import frappe
from frappe import _


@frappe.whitelist()
def send_message(message: str, session: str | None = None) -> dict:
	if not message or not message.strip():
		frappe.throw(_("Message is required."))

	settings = frappe.get_single("FOBS AI Settings")
	if not settings.enabled:
		frappe.throw(_("FOBS AI is disabled."))

	chat_session = get_or_create_session(session, message)
	assert_session_access(chat_session)

	save_message(chat_session.name, "user", message)
	assistant_reply = call_ai_provider(settings, chat_session.name, message)
	save_message(chat_session.name, "assistant", assistant_reply, settings.model)

	return {
		"session": chat_session.name,
		"reply": assistant_reply,
	}


@frappe.whitelist()
def get_sessions() -> list[dict]:
	filters = {}
	if not user_has_hr_access():
		filters["user"] = frappe.session.user

	return frappe.get_all(
		"FOBS Chat Session",
		filters=filters,
		fields=["name", "title", "employee", "employee_name", "status", "modified"],
		order_by="modified desc",
		limit_page_length=50,
	)


def get_or_create_session(session: str | None, message: str):
	if session:
		return frappe.get_doc("FOBS Chat Session", session)

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	return frappe.get_doc(
		{
			"doctype": "FOBS Chat Session",
			"user": frappe.session.user,
			"employee": employee,
			"title": message.strip()[:120],
			"status": "Open",
		}
	).insert(ignore_permissions=True)


def assert_session_access(chat_session):
	if user_has_hr_access():
		return

	if chat_session.user != frappe.session.user:
		frappe.throw(_("You do not have access to this chat session."))


def call_ai_provider(settings, session: str, message: str) -> str:
	base_url = (settings.base_url or "").rstrip("/")
	model = settings.model

	if not base_url or not model:
		frappe.throw(_("FOBS AI provider URL and model are required."))

	endpoint = base_url
	if not endpoint.endswith("/chat/completions"):
		endpoint = f"{endpoint}/chat/completions" if endpoint.endswith("/v1") else f"{endpoint}/v1/chat/completions"

	headers = {"Content-Type": "application/json"}
	api_key = settings.get_password("api_key")
	if api_key:
		headers["Authorization"] = f"Bearer {api_key}"

	response = requests.post(
		endpoint,
		headers=headers,
		json={
			"model": model,
			"messages": build_messages(session, message),
			"temperature": 0.2,
		},
		timeout=settings.request_timeout_seconds or 60,
	)
	response.raise_for_status()
	payload = response.json()

	try:
		return payload["choices"][0]["message"]["content"]
	except (KeyError, IndexError, TypeError):
		frappe.throw(_("FOBS AI provider returned an invalid response."))


def build_messages(session: str, message: str) -> list[dict]:
	messages = [{"role": "system", "content": build_system_prompt()}]
	history = frappe.get_all(
		"FOBS Chat Message",
		filters={"session": session},
		fields=["role", "content"],
		order_by="creation asc",
		limit_page_length=20,
	)
	messages.extend({"role": row.role, "content": row.content} for row in history)
	messages.append({"role": "user", "content": message})
	return messages


def build_system_prompt() -> str:
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user},
		["name", "employee_name", "company", "department", "designation"],
		as_dict=True,
	)
	access_scope = "HR/Admin access" if user_has_hr_access() else "own employee record only"

	return "\n".join(
		[
			"You are the FOBS HR assistant running on the company's own server.",
			"Follow strict role-based access. Do not reveal another employee's data to ESS users.",
			f"Current user: {frappe.session.user}. Access scope: {access_scope}.",
			f"Current employee context: {frappe.as_json(employee) if employee else 'No linked employee.'}",
			"You may help with HR questions, Excel formulas, summaries, and writing corrections.",
			"Do not claim access to records unless they are present in the supplied context.",
		]
	)


def save_message(session: str, role: str, content: str, provider_model: str | None = None):
	frappe.get_doc(
		{
			"doctype": "FOBS Chat Message",
			"session": session,
			"role": role,
			"content": content,
			"provider_model": provider_model,
		}
	).insert(ignore_permissions=True)


def user_has_hr_access() -> bool:
	roles = set(frappe.get_roles(frappe.session.user))
	return bool(roles.intersection({"HR Manager", "System Manager", "Administrator"}))
