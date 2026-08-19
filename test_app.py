import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app as app_module


class LiveEditorTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        root = Path(self.temp_directory.name)
        self.path_names = (
            "STUDENTS_FILE",
            "GUESTS_FILE",
            "JOIN_REQUESTS_FILE",
            "WORKSPACE_FILE",
            "FILE_AUTHORS_FILE",
            "ACCESS_FILE",
            "SNAPSHOTS_FILE",
            "CHAT_FILE",
            "CODE_FILE",
            "LEGACY_LINE_AUTHORS_FILE",
        )
        self.original_paths = {
            name: getattr(app_module, name) for name in self.path_names
        }
        self.original_manager = app_module.manager

        replacement_paths = {
            "STUDENTS_FILE": root / "students.json",
            "GUESTS_FILE": root / "guests.json",
            "JOIN_REQUESTS_FILE": root / "join_requests.json",
            "WORKSPACE_FILE": root / "workspace_state.json",
            "FILE_AUTHORS_FILE": root / "file_line_authors.json",
            "ACCESS_FILE": root / "access_control.json",
            "SNAPSHOTS_FILE": root / "snapshots.json",
            "CHAT_FILE": root / "chat_history.json",
            "CODE_FILE": root / "code_state.json",
            "LEGACY_LINE_AUTHORS_FILE": root / "line_authors.json",
        }
        for name, path in replacement_paths.items():
            setattr(app_module, name, str(path))

        replacement_paths["STUDENTS_FILE"].write_text("[]", encoding="utf-8")
        replacement_paths["GUESTS_FILE"].write_text("[]", encoding="utf-8")
        replacement_paths["JOIN_REQUESTS_FILE"].write_text("[]", encoding="utf-8")
        replacement_paths["WORKSPACE_FILE"].write_text(
            json.dumps(
                {
                    "tab_limit": 6,
                    "files": [
                        {
                            "id": "file_main",
                            "name": "main.py",
                            "language": "python",
                            "code": "",
                            "revision": 0,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        replacement_paths["FILE_AUTHORS_FILE"].write_text(
            json.dumps({"file_main": {}}),
            encoding="utf-8",
        )
        replacement_paths["ACCESS_FILE"].write_text(
            json.dumps({"owner_grants": {}, "global_editors": []}),
            encoding="utf-8",
        )
        replacement_paths["SNAPSHOTS_FILE"].write_text("[]", encoding="utf-8")
        replacement_paths["CHAT_FILE"].write_text("[]", encoding="utf-8")
        replacement_paths["CODE_FILE"].write_text(
            json.dumps({"code": "", "language": "python"}),
            encoding="utf-8",
        )
        replacement_paths["LEGACY_LINE_AUTHORS_FILE"].write_text(
            "{}",
            encoding="utf-8",
        )

        self.manager = app_module.ConnectionManager()
        app_module.manager = self.manager
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.client.close()
        app_module.manager = self.original_manager
        for name, path in self.original_paths.items():
            setattr(app_module, name, path)
        self.temp_directory.cleanup()

    def login_admin(self):
        response = self.client.post(
            "/api/auth/login",
            json={"role": "admin", "password": "12345"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def request_guest(self, full_name):
        response = self.client.post(
            "/api/guest-requests",
            json={"full_name": full_name},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def approve_guest(self, full_name, admin_token=None):
        request = self.request_guest(full_name)
        admin_token = admin_token or self.login_admin()
        approved = self.client.post(
            f"/api/join-requests/{request['request_id']}/approve",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        status = self.client.get(
            f"/api/guest-requests/{request['request_id']}/status",
            params={"request_token": request["request_token"]},
        )
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json()["status"], "approved")
        return status.json()

    @staticmethod
    def auth_header(token):
        return {"Authorization": f"Bearer {token}"}

    def join_admin_websocket(self, websocket, token):
        self.assertEqual(websocket.receive_json()["type"], "init")
        websocket.send_json(
            {"type": "join", "token": token, "color": "#FF5722"}
        )
        self.assertEqual(websocket.receive_json()["type"], "join_success")
        self.assertEqual(websocket.receive_json()["type"], "presence_updated")

    def receive_websocket_type(self, websocket, expected_type, max_messages=60):
        messages = []
        for _ in range(max_messages):
            message = websocket.receive_json()
            messages.append(message)
            if message.get("type") == expected_type:
                return message, messages
        self.fail(
            f"Did not receive {expected_type!r}; received "
            f"{[message.get('type') for message in messages]}"
        )

    def test_admin_login_and_approved_guest_session(self):
        wrong_admin = self.client.post(
            "/api/auth/login",
            json={"role": "admin", "password": "wrong"},
        )
        self.assertEqual(wrong_admin.status_code, 401)

        guest_login = self.client.post(
            "/api/auth/login",
            json={"role": "guest", "password": ""},
        )
        self.assertEqual(guest_login.status_code, 422)
        self.assertIn("request access", guest_login.json()["detail"])

        request = self.request_guest("Bob")
        pending = self.client.get(
            f"/api/guest-requests/{request['request_id']}/status",
            params={"request_token": request["request_token"]},
        )
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.json()["status"], "pending")

        admin_token = self.login_admin()
        approved = self.client.post(
            f"/api/join-requests/{request['request_id']}/approve",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(approved.status_code, 200, approved.text)

        admitted = self.client.get(
            f"/api/guest-requests/{request['request_id']}/status",
            params={"request_token": request["request_token"]},
        ).json()
        self.assertEqual(admitted["user"]["username"], "Bob")
        self.assertEqual(admitted["user"]["role"], "guest")

        current = self.client.get(
            "/api/auth/me",
            headers=self.auth_header(admitted["token"]),
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["user"], admitted["user"])

    def test_guest_request_rejection_and_secret_validation(self):
        request = self.request_guest("Rejected Guest")
        pending_name = self.client.get(
            "/api/guest-name-availability",
            params={"full_name": "  rejected   guest  "},
        )
        self.assertEqual(pending_name.status_code, 200)
        self.assertFalse(pending_name.json()["available"])
        self.assertEqual(pending_name.json()["reason"], "pending")
        duplicate_request = self.client.post(
            "/api/guest-requests",
            json={"full_name": "REJECTED GUEST"},
        )
        self.assertEqual(duplicate_request.status_code, 409)

        hidden = self.client.get(
            f"/api/guest-requests/{request['request_id']}/status",
            params={"request_token": "wrong-secret"},
        )
        self.assertEqual(hidden.status_code, 404)

        admin_token = self.login_admin()
        rejected = self.client.post(
            f"/api/join-requests/{request['request_id']}/reject",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(rejected.status_code, 200, rejected.text)
        status = self.client.get(
            f"/api/guest-requests/{request['request_id']}/status",
            params={"request_token": request["request_token"]},
        )
        self.assertEqual(status.json()["status"], "rejected")

    def test_admin_receives_live_guest_join_notification(self):
        admin_token = self.login_admin()
        with self.client.websocket_connect("/ws/admin_join_requests") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {"type": "join", "token": admin_token, "color": "#FF5722"}
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(websocket.receive_json()["type"], "presence_updated")

            request = self.request_guest("Bob")
            notification = websocket.receive_json()
            self.assertEqual(notification["type"], "join_request_created")
            self.assertEqual(notification["request"]["full_name"], "Bob")
            self.assertEqual(notification["pending_count"], 1)
            self.assertEqual(notification["request"]["id"], request["request_id"])

        static_directory = Path(app_module.STATIC_DIR)
        html = (static_directory / "index.html").read_text(encoding="utf-8")
        javascript = (static_directory / "app.js").read_text(encoding="utf-8")
        stylesheet = (static_directory / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="adminSettingsScroll"', html)
        self.assertIn('aria-label="Close Admin Settings"', html)
        self.assertIn("scrollAdminSettingsToSection", javascript)
        self.assertIn("elements.dlgAdminSettings.scrollTop = 0", javascript)
        self.assertNotIn("joinRequestsSection.scrollIntoView", javascript)
        self.assertIn(".settings-dialog-close", stylesheet)
        self.assertIn("scrollbar-gutter: stable", stylesheet)
        self.assertIn('<i data-lucide="qr-code"></i>', html)
        self.assertIn(".toolbar-icon-action", stylesheet)
        self.assertIn("flex: 0 0 42px", stylesheet)
        self.assertIn("justify-content: center", stylesheet)
        self.assertIn('id="guestNameAvailability"', html)
        self.assertIn('id="btnRequestGuestJoin" type="submit" disabled', html)
        self.assertIn("/api/guest-name-availability", javascript)
        self.assertIn("scheduleGuestNameAvailabilityCheck", javascript)
        self.assertIn(".guest-name-availability.unavailable", stylesheet)
        self.assertIn('#txtGuestName[aria-invalid="true"]', stylesheet)

    def test_manual_student_creation_is_removed_and_admin_can_remove_guest(self):
        admin_token = self.login_admin()
        old_add = self.client.post(
            "/api/students",
            headers=self.auth_header(admin_token),
            json={
                "full_name": "Old Student",
                "student_id": "ST003",
                "date_of_birth": "2005-02-20",
            },
        )
        self.assertEqual(old_add.status_code, 404)

        admitted = self.approve_guest("Alice Jones", admin_token)
        account_id = admitted["user"]["account_id"]
        guests = self.client.get(
            "/api/guests",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(guests.status_code, 200)
        self.assertEqual(guests.json()["guests"][0]["full_name"], "Alice Jones")

        removed = self.client.delete(
            f"/api/guests/{account_id}",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(self.manager.get_guest(account_id))

    def test_only_one_active_guest_session(self):
        admitted = self.approve_guest("John Smith")
        offline_name = self.client.get(
            "/api/guest-name-availability",
            params={"full_name": "john smith"},
        )
        self.assertEqual(offline_name.status_code, 200)
        self.assertTrue(offline_name.json()["available"])

        with self.client.websocket_connect("/ws/john_first") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {
                    "type": "join",
                    "token": admitted["token"],
                    "color": "#2196F3",
                }
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(websocket.receive_json()["type"], "presence_updated")

            active_name = self.client.get(
                "/api/guest-name-availability",
                params={"full_name": "  JOHN   SMITH "},
            )
            self.assertEqual(active_name.status_code, 200)
            self.assertFalse(active_name.json()["available"])
            self.assertEqual(active_name.json()["reason"], "active")
            self.assertIn("Name taken", active_name.json()["message"])

            duplicate_request = self.client.post(
                "/api/guest-requests",
                json={"full_name": "John Smith"},
            )
            self.assertEqual(duplicate_request.status_code, 409)
            self.assertIn("Name taken", duplicate_request.json()["detail"])

        available_after_disconnect = self.client.get(
            "/api/guest-name-availability",
            params={"full_name": "John Smith"},
        )
        self.assertEqual(available_after_disconnect.status_code, 200)
        self.assertTrue(available_after_disconnect.json()["available"])

    def test_admin_file_tabs_and_fifteen_tab_limit(self):
        admin_token = self.login_admin()
        updated_limit = self.client.put(
            "/api/settings/tab-limit",
            headers=self.auth_header(admin_token),
            json={"tab_limit": 15},
        )
        self.assertEqual(updated_limit.status_code, 200, updated_limit.text)
        self.assertEqual(updated_limit.json()["tab_limit"], 15)

        with self.client.websocket_connect("/ws/admin_files") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {"type": "join", "token": admin_token, "color": "#FF5722"}
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(websocket.receive_json()["type"], "presence_updated")

            for index in range(1, 15):
                language = "cpp" if index % 2 else "python"
                websocket.send_json(
                    {
                        "type": "create_file",
                        "name": f"lesson_{index}",
                        "language": language,
                    }
                )
                self.assertEqual(
                    websocket.receive_json()["type"],
                    "workspace_updated",
                )

            self.assertEqual(len(self.manager.workspace["files"]), 15)
            self.assertEqual(
                self.manager.workspace["files"][1]["name"],
                "lesson_1.cpp",
            )
            websocket.send_json(
                {
                    "type": "create_file",
                    "name": "too_many",
                    "language": "python",
                }
            )
            error = websocket.receive_json()
            self.assertEqual(error["type"], "error")
            self.assertIn("tab limit", error["message"].lower())

    def test_line_insertion_and_access_permissions(self):
        john = {
            "account_id": "guest_john",
            "username": "John Smith",
            "role": "guest",
            "color": "#2196F3",
        }
        bob = {
            "account_id": "guest_bob",
            "username": "Bob",
            "role": "guest",
            "color": "#9C27B0",
        }
        self.manager.workspace["files"][0]["code"] = "print('John')"
        self.manager.line_authors["file_main"] = {
            "0": {
                "account_id": john["account_id"],
                "author": john["username"],
                "color": john["color"],
            }
        }
        self.assertFalse(
            self.manager.can_user_edit_range(bob, "file_main", 0, 0)
        )

        file_data = self.manager.insert_blank_lines(
            "file_main",
            after_line=0,
            count=3,
        )
        self.assertEqual(file_data["code"], "print('John')\n\n\n")
        self.assertEqual(
            self.manager.line_authors["file_main"]["0"]["account_id"],
            "guest_john",
        )

        self.manager.access_control["owner_grants"] = {
            "guest_john": ["guest_bob"]
        }
        self.assertTrue(
            self.manager.can_user_edit_range(bob, "file_main", 0, 0)
        )
        self.manager.access_control["owner_grants"] = {}
        self.manager.access_control["global_editors"] = ["guest_bob"]
        self.assertTrue(
            self.manager.can_user_edit_range(bob, "file_main", 0, 0)
        )

    def test_consecutive_guest_lines_keep_guest_ownership(self):
        admitted = self.approve_guest("Bob")
        bob_id = admitted["user"]["account_id"]
        admin_owner = {
            "account_id": "admin",
            "author": "Admin",
            "color": "#FF5722",
        }
        file_data = self.manager.workspace["files"][0]
        file_data["code"] = "admin 1\nadmin 2\nadmin 3\nadmin 4\nadmin 5"
        file_data["revision"] = 0
        self.manager.line_authors["file_main"] = {
            str(index): dict(admin_owner) for index in range(5)
        }

        with self.client.websocket_connect("/ws/bob_consecutive_lines") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {
                    "type": "join",
                    "token": admitted["token"],
                    "color": "#9C27B0",
                }
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(websocket.receive_json()["type"], "presence_updated")

            websocket.send_json(
                {
                    "type": "insert_lines",
                    "file_id": "file_main",
                    "after_line": 2,
                    "count": 1,
                }
            )
            inserted = websocket.receive_json()
            self.assertEqual(inserted["type"], "file_state")
            self.assertEqual(inserted["focus_line"], 3)

            changes = (
                ({"line": 3, "ch": 0}, ["bob"], 1),
                ({"line": 3, "ch": 3}, ["", ""], 2),
                ({"line": 4, "ch": 0}, ["word"], 3),
                ({"line": 4, "ch": 4}, [" more"], 4),
            )
            last_ack = None
            revision = inserted["file"]["revision"]
            for position, text, sequence in changes:
                websocket.send_json(
                    {
                        "type": "code_delta",
                        "file_id": "file_main",
                        "from": position,
                        "to": position,
                        "text": text,
                        "revision": revision,
                        "client_sequence": sequence,
                    }
                )
                last_ack = websocket.receive_json()
                self.assertEqual(last_ack["type"], "code_delta_ack")
                self.assertEqual(last_ack["client_sequence"], sequence)
                revision = last_ack["revision"]

            self.assertEqual(
                self.manager.workspace["files"][0]["code"],
                "admin 1\nadmin 2\nadmin 3\nbob\nword more\nadmin 4\nadmin 5",
            )
            self.assertEqual(
                self.manager.line_authors["file_main"]["3"]["account_id"],
                bob_id,
            )
            self.assertEqual(
                self.manager.line_authors["file_main"]["4"]["account_id"],
                bob_id,
            )
            self.assertEqual(last_ack["line_authors"]["4"]["account_id"], bob_id)

        javascript = (Path(app_module.STATIC_DIR) / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function applyLocalAuthorDelta", javascript)
        self.assertIn("client_sequence: state.deltaSequence", javascript)
        self.assertIn("case 'code_delta_ack':", javascript)
        self.assertIn("state.lineAuthors[fileId] = newAuthors", javascript)

    def test_access_settings_report_incoming_and_global_permissions(self):
        john = self.approve_guest("John Smith")
        bob = self.approve_guest("Bob")
        admin_token = self.login_admin()
        john_id = john["user"]["account_id"]
        bob_id = bob["user"]["account_id"]

        owner_grant = self.client.put(
            f"/api/access/owner/{bob_id}",
            headers=self.auth_header(john["token"]),
            json={"enabled": True},
        )
        self.assertEqual(owner_grant.status_code, 200)

        bob_access = self.client.get(
            "/api/access",
            headers=self.auth_header(bob["token"]),
        )
        self.assertEqual(bob_access.status_code, 200)
        self.assertIn(john_id, bob_access.json()["editable_owner_ids"])

        global_grant = self.client.put(
            f"/api/access/global/{bob_id}",
            headers=self.auth_header(admin_token),
            json={"enabled": True},
        )
        self.assertEqual(global_grant.status_code, 200)
        bob_access = self.client.get(
            "/api/access",
            headers=self.auth_header(bob["token"]),
        )
        self.assertTrue(bob_access.json()["global_editor"])

    def test_admin_name_and_role_data(self):
        admin_token = self.login_admin()
        response = self.client.put(
            "/api/admin/name",
            headers=self.auth_header(admin_token),
            json={"display_name": "Professor Ada"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "Professor Ada")
        self.assertEqual(self.manager.get_session(admin_token)["role"], "admin")

    def test_python_execution_requires_login(self):
        unauthenticated = self.client.post(
            "/api/run",
            json={"code": "print('blocked')", "language": "python"},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        token = self.login_admin()
        response = self.client.post(
            "/api/run",
            headers=self.auth_header(token),
            json={"code": "print('working')", "language": "python"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stdout"].strip(), "working")

        input_response = self.client.post(
            "/api/run",
            headers=self.auth_header(token),
            json={
                "code": "name = input()\nprint(f'Hello, {name}!')",
                "language": "python",
                "stdin": "LAN guest\n",
            },
        )
        self.assertEqual(input_response.status_code, 200, input_response.text)
        self.assertEqual(input_response.json()["stdout"].strip(), "Hello, LAN guest!")

        oversized_input = self.client.post(
            "/api/run",
            headers=self.auth_header(token),
            json={
                "code": "print('blocked')",
                "language": "python",
                "stdin": "x" * (app_module.MAX_STDIN_SIZE + 1),
            },
        )
        self.assertEqual(oversized_input.status_code, 413)

    def test_python_control_flow_functions_classes_and_imports(self):
        token = self.login_admin()
        response = self.client.post(
            "/api/run",
            headers=self.auth_header(token),
            json={
                "language": "python",
                "code": (
                    "import math\n"
                    "from collections import Counter\n"
                    "def factorial(value):\n"
                    "    return 1 if value <= 1 else value * factorial(value - 1)\n"
                    "class Greeter:\n"
                    "    def __init__(self, name):\n"
                    "        self.name = name\n"
                    "    def message(self):\n"
                    "        return f'Hello, {self.name}!'\n"
                    "total = 0\n"
                    "for number in range(1, 5):\n"
                    "    if number % 2 == 0:\n"
                    "        total += number\n"
                    "remaining = 2\n"
                    "while remaining > 0:\n"
                    "    total += 1\n"
                    "    remaining -= 1\n"
                    "print(factorial(5))\n"
                    "print(Greeter('Bob').message())\n"
                    "print(total, math.isqrt(81), Counter('banana')['a'])\n"
                ),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["returncode"], 0, result.get("stderr"))
        self.assertEqual(result["stdout"].strip(), "120\nHello, Bob!\n8 9 3")

    def test_interactive_python_terminal_accepts_live_input_and_stop(self):
        self.assertEqual(app_module.MAX_INTERACTIVE_EXECUTION_SECONDS, 60.0)
        self.assertEqual(app_module.MAX_INTERACTIVE_OUTPUT_CHARS, 100_000)
        self.assertEqual(app_module.MAX_INTERACTIVE_EXECUTIONS, 20)
        self.assertEqual(app_module.MAX_INTERACTIVE_INPUT_LINE, 4_096)
        self.assertEqual(app_module.MAX_INTERACTIVE_INPUT_TOTAL, 20_000)
        self.assertEqual(app_module.MAX_CONCURRENT_CPP_COMPILATIONS, 4)

        token = self.login_admin()
        with self.client.websocket_connect("/ws/admin_python_terminal") as websocket:
            self.join_admin_websocket(websocket, token)
            websocket.send_json(
                {
                    "type": "terminal_run",
                    "file_id": "file_main",
                    "code": (
                        "first = int(input('First: '))\n"
                        "second = int(input('Second: '))\n"
                        "print(f'Total: {first + second}')\n"
                    ),
                }
            )
            started, _ = self.receive_websocket_type(websocket, "terminal_started")
            self.assertEqual(started["limits"]["execution_seconds"], 60.0)
            self.receive_websocket_type(websocket, "terminal_ready")

            websocket.send_json({"type": "terminal_input", "text": "10"})
            self.receive_websocket_type(websocket, "terminal_input_echo")
            websocket.send_json({"type": "terminal_input", "text": "5"})
            finished, messages = self.receive_websocket_type(
                websocket,
                "terminal_finished",
            )
            output = "".join(
                message.get("text", "")
                for message in messages
                if message.get("type") == "terminal_output"
            )
            self.assertIn("Total: 15", output)
            self.assertEqual(finished["status"], "completed")
            self.assertEqual(finished["returncode"], 0)

            websocket.send_json(
                {
                    "type": "terminal_run",
                    "file_id": "file_main",
                    "code": "input('Waiting: ')\n",
                }
            )
            self.receive_websocket_type(websocket, "terminal_started")
            self.receive_websocket_type(websocket, "terminal_ready")
            websocket.send_json({"type": "terminal_stop"})
            stopped, _ = self.receive_websocket_type(
                websocket,
                "terminal_finished",
            )
            self.assertEqual(stopped["status"], "stopped")

        html = (Path(app_module.STATIC_DIR) / "index.html").read_text(
            encoding="utf-8"
        )
        javascript = (Path(app_module.STATIC_DIR) / "app.js").read_text(
            encoding="utf-8"
        )
        stylesheet = (Path(app_module.STATIC_DIR) / "style.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="terminalInput"', html)
        self.assertIn('id="btnStopCode"', html)
        self.assertIn('id="terminalResizeHandle"', html)
        self.assertNotIn('id="programInput"', html)
        self.assertIn("stream === 'status'", javascript)
        self.assertIn("TERMINAL_HEIGHT_STORAGE_KEY", javascript)
        self.assertIn("initializeTerminalResize", javascript)
        self.assertIn(".terminal-status", stylesheet)
        self.assertIn(".terminal-resize-handle", stylesheet)
        self.assertIn("color: var(--warning-color);", stylesheet)

    @unittest.skipUnless(
        shutil.which("g++") or shutil.which("clang++"),
        "g++ or clang++ is not installed on the host",
    )
    def test_interactive_cpp_terminal_accepts_live_input(self):
        cpp_file = self.manager.create_file("interactive.cpp", "cpp")
        token = self.login_admin()
        with self.client.websocket_connect("/ws/admin_cpp_terminal") as websocket:
            self.join_admin_websocket(websocket, token)
            websocket.send_json(
                {
                    "type": "terminal_run",
                    "file_id": cpp_file["id"],
                    "code": (
                        "#include <iostream>\n"
                        "int main() {\n"
                        "  int first = 0, second = 0;\n"
                        "  std::cout << \"Enter two numbers: \";\n"
                        "  std::cin >> first >> second;\n"
                        "  std::cout << \"Total: \" << first + second << '\\n';\n"
                        "  return 0;\n"
                        "}\n"
                    ),
                }
            )
            self.receive_websocket_type(websocket, "terminal_started")
            self.receive_websocket_type(websocket, "terminal_ready")
            websocket.send_json({"type": "terminal_input", "text": "10 5"})
            finished, messages = self.receive_websocket_type(
                websocket,
                "terminal_finished",
            )
            output = "".join(
                message.get("text", "")
                for message in messages
                if message.get("type") == "terminal_output"
            )
            self.assertIn("Total: 15", output)
            self.assertEqual(finished["status"], "completed")
            self.assertEqual(finished["returncode"], 0)

    @unittest.skipUnless(
        shutil.which("g++") or shutil.which("clang++"),
        "g++ or clang++ is not installed on the host",
    )
    def test_cpp17_compilation_and_execution_with_input(self):
        token = self.login_admin()
        response = self.client.post(
            "/api/run",
            headers=self.auth_header(token),
            json={
                "code": (
                    "#include <algorithm>\n"
                    "#include <iostream>\n"
                    "#include <vector>\n"
                    "int square(int value) { return value * value; }\n"
                    "int main() {\n"
                    "    int first = 0;\n"
                    "    int second = 0;\n"
                    "    if (!(std::cin >> first >> second)) return 1;\n"
                    "    std::vector<int> values{3, 1, 2};\n"
                    "    std::sort(values.begin(), values.end());\n"
                    "    int square_total = 0;\n"
                    "    for (int value : values) square_total += square(value);\n"
                    "    int countdown = 2;\n"
                    "    while (countdown > 0) --countdown;\n"
                    "    std::cout << \"Sum: \" << first + second << std::endl;\n"
                    "    std::cout << \"Product: \" << first * second << std::endl;\n"
                    "    std::cout << \"Squares: \" << square_total << std::endl;\n"
                    "    std::cout << \"Countdown: \" << countdown << std::endl;\n"
                    "    return 0;\n"
                    "}\n"
                ),
                "language": "cpp",
                "stdin": "12 5\n",
                "timeout": 5,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["returncode"], 0, result.get("stderr"))
        self.assertEqual(result["stage"], "run")
        self.assertEqual(
            result["stdout"].strip(),
            "Sum: 17\nProduct: 60\nSquares: 14\nCountdown: 0",
        )

    def test_chat_message_edit_and_delete_permissions(self):
        message = {
            "id": 1001,
            "sender_account_id": "guest_john",
            "sender": "John Smith",
            "sender_role": "guest",
            "target": "group",
            "text": "Original message",
        }
        self.manager.add_chat_message(message)
        john = {
            "account_id": "guest_john",
            "username": "John Smith",
            "role": "guest",
        }
        bob = {
            "account_id": "guest_bob",
            "username": "Bob",
            "role": "guest",
        }
        admin = {
            "account_id": "admin",
            "username": "Admin",
            "role": "admin",
        }

        edited = self.manager.edit_chat_message(1001, john, "Updated message")
        self.assertEqual(edited["text"], "Updated message")
        self.assertTrue(edited["edited"])
        with self.assertRaises(app_module.HTTPException) as context:
            self.manager.edit_chat_message(1001, bob, "Not allowed")
        self.assertEqual(context.exception.status_code, 403)
        with self.assertRaises(app_module.HTTPException) as context:
            self.manager.delete_chat_message(1001, bob)
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            self.manager.delete_chat_message(1001, admin)["id"],
            1001,
        )

    def test_chat_delete_websocket_removes_and_broadcasts_message(self):
        admin_token = self.login_admin()
        with self.client.websocket_connect("/ws/admin_chat_delete") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {"type": "join", "token": admin_token, "color": "#FF5722"}
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(websocket.receive_json()["type"], "presence_updated")
            websocket.send_json(
                {
                    "type": "chat_message",
                    "target": "group",
                    "text": "Delete this message",
                }
            )
            created_event = websocket.receive_json()
            message_id = created_event["message"]["id"]
            websocket.send_json(
                {"type": "chat_delete", "message_id": message_id}
            )
            deleted_event = websocket.receive_json()
            self.assertEqual(deleted_event["type"], "chat_message_deleted")
            self.assertEqual(deleted_event["message_id"], message_id)
            self.assertIsNone(self.manager.get_chat_message(message_id))

    def test_execution_problem_parsers_keep_source_details(self):
        token = self.login_admin()
        response = self.client.post(
            "/api/run",
            headers=self.auth_header(token),
            json={"code": "print(missing_name)", "language": "python"},
        )
        problem = response.json()["problems"][0]
        self.assertEqual(problem["type"], "NameError")
        self.assertEqual(problem["line"], 1)

        cpp_problems = app_module.parse_execution_problems(
            {
                "stderr": (
                    "C:/tmp/main.cpp:7:14: error: expected ';' "
                    "before 'return'\n"
                ),
                "returncode": 1,
                "stage": "compile",
            },
            "cpp",
        )
        self.assertEqual(cpp_problems[0]["line"], 7)
        self.assertEqual(cpp_problems[0]["column"], 14)

    def test_line_typing_labels_replace_top_banner_and_cursor_names(self):
        static_directory = Path(app_module.STATIC_DIR)
        html = (static_directory / "index.html").read_text(encoding="utf-8")
        javascript = (static_directory / "app.js").read_text(encoding="utf-8")
        stylesheet = (static_directory / "style.css").read_text(encoding="utf-8")

        self.assertNotIn('id="typingBanner"', html)
        self.assertNotIn("typingBanner:", javascript)
        self.assertNotIn("is editing...", javascript)
        self.assertNotIn(".typing-banner", stylesheet)
        self.assertNotIn("remote-cursor-flag", javascript)
        self.assertNotIn("remote-cursor-flag", stylesheet)
        self.assertIn("typing_line_update", javascript)
        self.assertIn("updateRemoteLineHighlight", javascript)
        self.assertIn("lineTypingIndicators: new Map()", javascript)
        self.assertIn("line-typing-badge", javascript)
        self.assertIn("line-typing-badge-dot", javascript)
        self.assertIn("`${data.username}${data.role === 'admin' ? ' ♛' : ''} is typing`", javascript)
        self.assertIn("removeRemoteLineTypingIndicator", javascript)
        self.assertIn("placeRemoteLineTypingBadge", javascript)
        self.assertIn("clearAllRemoteLineTypingIndicators", javascript)
        self.assertIn("removeInactiveLineTypingIndicators", javascript)
        self.assertIn("stopLocalTyping", javascript)
        self.assertIn(".line-typing-badge", stylesheet)
        self.assertIn("--typing-color", stylesheet)
        self.assertIn(".line-typing-badge-label", stylesheet)
        self.assertIn("margin-left: 3ch;", stylesheet)
        self.assertIn(".remote-cursor > .line-typing-badge", stylesheet)
        self.assertIn("left: 3ch;", stylesheet)
        self.assertIn("4.2.1-line-typing-labels-3", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
