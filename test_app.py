import asyncio
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as app_module
import docker_execution as docker_module


def docker_cpp_runner_available():
    try:
        app_module.ensure_cpp_docker_ready()
        return True
    except app_module.DockerExecutionError:
        return False


def docker_python_runner_available():
    try:
        app_module.ensure_python_docker_ready()
        return True
    except app_module.DockerExecutionError:
        return False


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

    def test_root_prevents_stale_frontend_cache(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("cache-control"),
            "no-cache, no-store, must-revalidate",
        )
        self.assertIn("5.2-guest-cpp-1", response.text)

    def test_docker_resolver_supports_current_per_user_install_path(self):
        local_app_data = r"C:\Users\Test\AppData\Local"
        expected = os.path.join(
            local_app_data,
            "Programs",
            "DockerDesktop",
            "resources",
            "bin",
            "docker.exe",
        )
        with (
            patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}, clear=False),
            patch("docker_execution.shutil.which", return_value=None),
            patch(
                "docker_execution.os.path.isfile",
                side_effect=lambda path: path == expected,
            ),
        ):
            self.assertEqual(docker_module.resolve_docker_executable(), expected)

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

    def test_classroom_settings_default_and_admin_only_updates(self):
        info = self.client.get("/api/info")
        self.assertEqual(info.status_code, 200, info.text)
        self.assertEqual(info.json()["python_execution_mode"], "browser")
        self.assertFalse(info.json()["guest_auto_approval"])

        admin_token = self.login_admin()
        guest = self.approve_guest("Settings Guest", admin_token)
        forbidden = self.client.put(
            "/api/settings/guest-auto-approval",
            headers=self.auth_header(guest["token"]),
            json={"enabled": True},
        )
        self.assertEqual(forbidden.status_code, 403)

        with patch.object(app_module, "ensure_python_docker_ready", return_value="docker"):
            updated = self.client.put(
                "/api/settings/python-execution-mode",
                headers=self.auth_header(admin_token),
                json={"mode": "docker"},
            )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["python_execution_mode"], "docker")
        saved = json.loads(Path(app_module.ACCESS_FILE).read_text(encoding="utf-8"))
        self.assertEqual(saved["python_execution_mode"], "docker")

        invalid = self.client.put(
            "/api/settings/python-execution-mode",
            headers=self.auth_header(admin_token),
            json={"mode": "host"},
        )
        self.assertEqual(invalid.status_code, 422)

        static_directory = Path(app_module.STATIC_DIR)
        html = (static_directory / "index.html").read_text(encoding="utf-8")
        javascript = (static_directory / "app.js").read_text(encoding="utf-8")
        stylesheet = (static_directory / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="executionModeMenu"', html)
        self.assertIn('data-python-mode="browser"', html)
        self.assertIn('data-python-mode="docker"', html)
        self.assertIn('id="chkGuestAutoApproval"', html)
        self.assertIn("setPythonExecutionMode", javascript)
        self.assertIn("handlePythonModeMenuClick", javascript)
        self.assertIn("event.target.closest('[data-python-mode]')", javascript)
        self.assertIn("applyClassroomSettings", javascript)
        self.assertIn(".execution-mode-menu", stylesheet)
        self.assertIn(".execution-mode-option > *", stylesheet)
        self.assertIn(".classroom-setting-row", stylesheet)

    def test_auto_join_is_off_by_default_and_can_admit_guests_immediately(self):
        admin_token = self.login_admin()
        waiting = self.request_guest("Waiting Guest")
        self.assertEqual(waiting["status"], "pending")

        enabled = self.client.put(
            "/api/settings/guest-auto-approval",
            headers=self.auth_header(admin_token),
            json={"enabled": True},
        )
        self.assertEqual(enabled.status_code, 200, enabled.text)
        self.assertTrue(enabled.json()["guest_auto_approval"])
        self.assertEqual(enabled.json()["approved_names"], ["Waiting Guest"])

        waiting_status = self.client.get(
            f"/api/guest-requests/{waiting['request_id']}/status",
            params={"request_token": waiting["request_token"]},
        )
        self.assertEqual(waiting_status.status_code, 200, waiting_status.text)
        self.assertEqual(waiting_status.json()["status"], "approved")
        self.assertIn("token", waiting_status.json())

        immediate = self.request_guest("Immediate Guest")
        self.assertEqual(immediate["status"], "approved")
        self.assertEqual(immediate["user"]["username"], "Immediate Guest")
        self.assertIn("token", immediate)
        queue = self.client.get(
            "/api/join-requests",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(queue.json()["pending_count"], 0)

        duplicate = self.client.post(
            "/api/guest-requests",
            json={"full_name": "immediate guest"},
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["user"]["account_id"], immediate["user"]["account_id"])

        disabled = self.client.put(
            "/api/settings/guest-auto-approval",
            headers=self.auth_header(admin_token),
            json={"enabled": False},
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertFalse(disabled.json()["guest_auto_approval"])
        pending_again = self.request_guest("Manual Again")
        self.assertEqual(pending_again["status"], "pending")

    def test_classroom_settings_are_broadcast_to_connected_users(self):
        admin_token = self.login_admin()
        with self.client.websocket_connect("/ws/settings_broadcast") as websocket:
            self.join_admin_websocket(websocket, admin_token)
            response = self.client.put(
                "/api/settings/guest-auto-approval",
                headers=self.auth_header(admin_token),
                json={"enabled": True},
            )
            self.assertEqual(response.status_code, 200, response.text)
            event, _ = self.receive_websocket_type(
                websocket,
                "classroom_settings_updated",
            )
            self.assertTrue(event["guest_auto_approval"])
            self.assertEqual(event["python_execution_mode"], "browser")

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

    def test_join_requests_use_fifo_popover_queue(self):
        admin_token = self.login_admin()
        bob = self.request_guest("Bob")
        sarah = self.request_guest("Sarah")
        john = self.request_guest("John")

        queue = self.client.get(
            "/api/join-requests",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(queue.status_code, 200, queue.text)
        self.assertEqual(
            [request["full_name"] for request in queue.json()["requests"]],
            ["Bob", "Sarah", "John"],
        )

        out_of_order = self.client.post(
            f"/api/join-requests/{sarah['request_id']}/approve",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(out_of_order.status_code, 409, out_of_order.text)
        self.assertIn("oldest", out_of_order.json()["detail"].lower())

        accepted = self.client.post(
            f"/api/join-requests/{bob['request_id']}/approve",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        queue = self.client.get(
            "/api/join-requests",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(
            [request["full_name"] for request in queue.json()["requests"]],
            ["Sarah", "John"],
        )

        rejected = self.client.post(
            f"/api/join-requests/{sarah['request_id']}/reject",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(rejected.status_code, 200, rejected.text)
        queue = self.client.get(
            "/api/join-requests",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(
            [request["full_name"] for request in queue.json()["requests"]],
            ["John"],
        )
        self.assertEqual(queue.json()["requests"][0]["id"], john["request_id"])

        static_directory = Path(app_module.STATIC_DIR)
        html = (static_directory / "index.html").read_text(encoding="utf-8")
        javascript = (static_directory / "app.js").read_text(encoding="utf-8")
        stylesheet = (static_directory / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="joinRequestPopover"', html)
        self.assertIn('id="joinRequestPopoverList"', html)
        self.assertIn("renderJoinRequestPopover", javascript)
        self.assertIn("formatJoinRequestTime", javascript)
        self.assertIn("Next request opens after a decision", html)
        self.assertIn(".join-request-popover-row.is-active", stylesheet)
        self.assertIn(".join-request-popover-row.is-queued", stylesheet)
        self.assertIn("5.2-guest-cpp-1", html)

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

    def test_legacy_run_route_remains_admin_only(self):
        unauthenticated = self.client.post(
            "/api/run",
            json={"code": "print('blocked')", "language": "python"},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        admin_token = self.login_admin()
        python_response = self.client.post(
            "/api/run",
            headers=self.auth_header(admin_token),
            json={"code": "print('working')", "language": "python"},
        )
        self.assertEqual(python_response.status_code, 410)
        self.assertIn("browser", python_response.json()["detail"].lower())

        guest = self.approve_guest("Browser Bob", admin_token)
        guest_cpp = self.client.post(
            "/api/run",
            headers=self.auth_header(guest["token"]),
            json={
                "code": "int main() { return 0; }",
                "language": "cpp",
            },
        )
        self.assertEqual(guest_cpp.status_code, 403)
        self.assertIn("Admin", guest_cpp.json()["detail"])

        oversized_input = self.client.post(
            "/api/run",
            headers=self.auth_header(admin_token),
            json={
                "code": "int main() { return 0; }",
                "language": "cpp",
                "stdin": "x" * (app_module.MAX_STDIN_SIZE + 1),
            },
        )
        self.assertEqual(oversized_input.status_code, 413)

    def test_browser_python_runtime_is_local_and_pinned(self):
        static_directory = Path(app_module.STATIC_DIR)
        runtime = (static_directory / "python-runtime.mjs").read_text(encoding="utf-8")
        worker = (static_directory / "python-worker.mjs").read_text(encoding="utf-8")
        javascript = (static_directory / "app.js").read_text(encoding="utf-8")
        html = (static_directory / "index.html").read_text(encoding="utf-8")

        self.assertTrue((static_directory / "vendor" / "pyodide" / "pyodide.asm.wasm").is_file())
        self.assertTrue((static_directory / "vendor" / "pyodide" / "python_stdlib.zip").is_file())
        self.assertIn("BROWSER_PYTHON_VERSION = '314.0.5'", runtime)
        self.assertIn("replayBrowserPython", runtime)
        self.assertIn("new Worker('/static/python-worker.mjs?v=5.1-python-modes-1'", javascript)
        self.assertIn("Runs in this browser", html)
        self.assertNotIn("cdn.jsdelivr.net", runtime)
        self.assertIn("runtime_loading", worker)

    def test_cpp_docker_command_enforces_sandbox_boundaries(self):
        with tempfile.TemporaryDirectory() as source_directory:
            command = app_module.build_cpp_docker_command(
                "docker",
                source_directory,
                "wifi-codeshare-cpp-test",
                execution_seconds=7,
            )

        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--ipc none", joined)
        self.assertIn("--restart no", joined)
        self.assertIn("--init", command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("no-new-privileges:true", command)
        self.assertIn("--memory 512m", joined)
        self.assertIn("--memory-swap 512m", joined)
        self.assertIn("--cpus 1.0", joined)
        self.assertIn("--pids-limit 64", joined)
        self.assertIn("target=/source,readonly", joined)
        self.assertIn("LIVE_EDITOR_EXECUTION_TIMEOUT=7", command)
        self.assertIn("--user 10001:10001", joined)
        self.assertNotIn("--privileged", command)
        self.assertNotIn("docker.sock", joined)
        self.assertEqual(command[-1], app_module.CPP_DOCKER_IMAGE)

        root = Path(__file__).resolve().parent
        dockerfile = (root / "docker" / "cpp-runner" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        runner = (root / "docker" / "cpp-runner" / "runner.sh").read_text(
            encoding="utf-8"
        )
        setup_script = (root / "setup-docker.cmd").read_text(encoding="utf-8")
        self.assertIn("gcc:14.2.0-bookworm@sha256:", dockerfile)
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("__WIFI_CODESHARE_CPP_READY__", runner)
        self.assertIn('"%DOCKER_EXE%" build --pull', setup_script)
        self.assertIn("Programs\\DockerDesktop\\resources\\bin\\docker.exe", setup_script)

    def test_python_docker_image_and_command_use_the_same_sandbox_boundaries(self):
        with tempfile.TemporaryDirectory() as source_directory:
            command = app_module.build_python_docker_command(
                "docker",
                source_directory,
                "wifi-codeshare-python-test",
                execution_seconds=9,
            )
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--ipc none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("no-new-privileges:true", command)
        self.assertIn("--memory 512m", joined)
        self.assertIn("--pids-limit 64", joined)
        self.assertIn("target=/source,readonly", joined)
        self.assertIn("LIVE_EDITOR_EXECUTION_TIMEOUT=9", command)
        self.assertIn("--user 10001:10001", joined)
        self.assertEqual(command[-1], app_module.PYTHON_DOCKER_IMAGE)

        root = Path(__file__).resolve().parent
        dockerfile = (root / "docker" / "python-runner" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        runner = (root / "docker" / "python-runner" / "runner.sh").read_text(
            encoding="utf-8"
        )
        setup_script = (root / "setup-docker.cmd").read_text(encoding="utf-8")
        self.assertIn("python:3.14.0-slim-bookworm@sha256:", dockerfile)
        self.assertIn("numpy==2.5.2", dockerfile)
        self.assertIn("pandas==3.0.5", dockerfile)
        self.assertIn("matplotlib==3.11.1", dockerfile)
        self.assertIn("sympy==1.14.0", dockerfile)
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("__WIFI_CODESHARE_PYTHON_READY__", runner)
        self.assertIn("wifi-codeshare-python-runner:1.0", setup_script)

    def test_websocket_rejects_browser_python_and_routes_guest_cpp_to_docker(self):
        self.assertEqual(app_module.MAX_INTERACTIVE_EXECUTION_SECONDS, 60.0)
        self.assertEqual(app_module.MAX_INTERACTIVE_OUTPUT_CHARS, 100_000)
        self.assertEqual(app_module.MAX_INTERACTIVE_EXECUTIONS, 20)
        self.assertEqual(app_module.MAX_INTERACTIVE_INPUT_LINE, 4_096)
        self.assertEqual(app_module.MAX_INTERACTIVE_INPUT_TOTAL, 20_000)
        self.assertEqual(app_module.MAX_CONCURRENT_DOCKER_EXECUTIONS, 4)

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
            blocked, _ = self.receive_websocket_type(websocket, "terminal_error")
            self.assertIn("browser", blocked["message"].lower())

        cpp_file = self.manager.create_file("guest-docker.cpp", "cpp")
        guest = self.approve_guest("Guest Cpp", token)
        async def record_guest_cpp(connection_id, user, file_id, code, language):
            self.assertEqual(user["role"], "guest")
            self.assertEqual(file_id, cpp_file["id"])
            self.assertEqual(code, "int main() { return 0; }")
            self.assertEqual(language, "cpp")
            return "run_guest_cpp"

        with patch.object(
            self.manager,
            "start_interactive_execution",
            side_effect=record_guest_cpp,
        ) as start_execution:
            with self.client.websocket_connect("/ws/guest_cpp_docker") as websocket:
                self.join_admin_websocket(websocket, guest["token"])
                websocket.send_json(
                    {
                        "type": "terminal_run",
                        "file_id": cpp_file["id"],
                        "code": "int main() { return 0; }",
                    }
                )
                notice, _ = self.receive_websocket_type(websocket, "code_run_notice")
                self.assertEqual(notice["username"], "Guest Cpp")
                self.assertEqual(notice["role"], "guest")
            self.assertEqual(start_execution.await_count, 1)

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
        self.assertIn("runBrowserPython", javascript)
        self.assertIn("stopBrowserPython", javascript)
        self.assertNotIn("Admin-only Docker execution", javascript)
        self.assertNotIn("Guests cannot execute C++ yet.", javascript)
        self.assertIn("Runs in Docker", javascript)
        self.assertIn(".terminal-status", stylesheet)
        self.assertIn(".execution-mode-tag", stylesheet)
        self.assertIn(".terminal-resize-handle", stylesheet)
        self.assertIn("color: var(--warning-color);", stylesheet)

    @unittest.skipUnless(
        docker_python_runner_available(),
        "The restricted Docker Python image is not ready",
    )
    def test_guest_docker_python_accepts_input_and_approved_libraries(self):
        admin_token = self.login_admin()
        guest = self.approve_guest("Docker Python Guest", admin_token)
        self.manager.access_control["python_execution_mode"] = "docker"

        with self.client.websocket_connect("/ws/guest_python_docker") as websocket:
            self.join_admin_websocket(websocket, guest["token"])
            websocket.send_json(
                {
                    "type": "terminal_run",
                    "file_id": "file_main",
                    "code": (
                        "import numpy as np\n"
                        "import pandas as pd\n"
                        "import matplotlib\n"
                        "import sympy as sp\n"
                        "first = int(input('First: '))\n"
                        "second = int(input('Second: '))\n"
                        "print(f'Total: {first + second}')\n"
                        "print(np.array([2, 3]).sum())\n"
                        "print(pd.Series([4, 5]).sum())\n"
                        "print(matplotlib.__version__)\n"
                        "print(sp.factor(6 * 7))\n"
                    ),
                }
            )
            started, _ = self.receive_websocket_type(websocket, "terminal_started")
            self.assertEqual(started["language"], "python")
            self.assertEqual(started["image"], app_module.PYTHON_DOCKER_IMAGE)
            self.receive_websocket_type(websocket, "terminal_ready")

            execution = self.manager.execution_sessions[guest["user"]["account_id"]]
            inspect_process = subprocess.run(
                [
                    execution["docker"],
                    "container",
                    "inspect",
                    execution["container_name"],
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(inspect_process.returncode, 0, inspect_process.stderr)
            container = json.loads(inspect_process.stdout)[0]
            host_config = container["HostConfig"]
            self.assertEqual(container["Config"]["User"], "10001:10001")
            self.assertEqual(host_config["NetworkMode"], "none")
            self.assertTrue(host_config["ReadonlyRootfs"])
            self.assertIn("ALL", host_config["CapDrop"])
            self.assertIn("no-new-privileges:true", host_config["SecurityOpt"])

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
            self.assertIn("5\n", output)
            self.assertIn("9\n", output)
            self.assertIn("3.11.1", output)
            self.assertIn("42", output)
            self.assertEqual(finished["status"], "completed")

    @unittest.skipUnless(
        docker_cpp_runner_available(),
        "The restricted Docker C++ image is not ready",
    )
    def test_guest_interactive_cpp_terminal_accepts_live_input(self):
        cpp_file = self.manager.create_file("interactive.cpp", "cpp")
        admin_token = self.login_admin()
        guest = self.approve_guest("C++ Runner", admin_token)
        with self.client.websocket_connect("/ws/guest_cpp_terminal") as websocket:
            self.join_admin_websocket(websocket, guest["token"])
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
            execution = self.manager.execution_sessions[guest["user"]["account_id"]]
            inspect_process = subprocess.run(
                [
                    execution["docker"],
                    "container",
                    "inspect",
                    execution["container_name"],
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(inspect_process.returncode, 0, inspect_process.stderr)
            container = json.loads(inspect_process.stdout)[0]
            host_config = container["HostConfig"]
            self.assertEqual(container["Config"]["User"], "10001:10001")
            self.assertEqual(host_config["NetworkMode"], "none")
            self.assertEqual(host_config["IpcMode"], "none")
            self.assertEqual(host_config["RestartPolicy"]["Name"], "no")
            self.assertTrue(host_config["ReadonlyRootfs"])
            self.assertIn("ALL", host_config["CapDrop"])
            self.assertIn("no-new-privileges:true", host_config["SecurityOpt"])
            self.assertEqual(host_config["Memory"], 512 * 1024 * 1024)
            self.assertEqual(host_config["NanoCpus"], 1_000_000_000)
            self.assertEqual(host_config["PidsLimit"], 64)
            source_mount = next(
                mount for mount in container["Mounts"] if mount["Destination"] == "/source"
            )
            self.assertFalse(source_mount["RW"])
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

    def test_guest_cpp_preserves_per_account_execution_ownership(self):
        admin_token = self.login_admin()
        guest = self.approve_guest("Owned Runner", admin_token)
        cpp_file = self.manager.create_file("owned.cpp", "cpp")
        account_id = guest["user"]["account_id"]
        self.manager.execution_sessions[account_id] = {
            "connection_id": "original_connection",
        }

        with patch.object(
            app_module,
            "ensure_cpp_docker_ready",
            return_value="docker",
        ):
            with self.assertRaises(app_module.HTTPException) as duplicate:
                asyncio.run(
                    self.manager.start_interactive_execution(
                        "second_connection",
                        guest["user"],
                        cpp_file["id"],
                        "int main() { return 0; }",
                        "cpp",
                    )
                )
        self.assertEqual(duplicate.exception.status_code, 409)
        self.assertIn("already have a program running", str(duplicate.exception.detail))

        with self.assertRaises(app_module.HTTPException) as wrong_connection:
            asyncio.run(
                self.manager.send_interactive_input(
                    "second_connection",
                    guest["user"],
                    "10 5",
                )
            )
        self.assertEqual(wrong_connection.exception.status_code, 404)
        self.assertFalse(
            asyncio.run(
                self.manager.stop_interactive_execution(
                    "second_connection",
                    guest["user"],
                )
            )
        )
        self.manager.execution_sessions.clear()

    @unittest.skipUnless(
        docker_cpp_runner_available(),
        "The restricted Docker C++ image is not ready",
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
        python_problems = app_module.parse_execution_problems(
            {
                "stderr": (
                    "Traceback (most recent call last):\n"
                    "  File \"<string>\", line 1, in <module>\n"
                    "NameError: name 'missing_name' is not defined\n"
                ),
                "returncode": 1,
                "stage": "run",
            },
            "python",
        )
        problem = python_problems[0]
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
        self.assertIn("5.2-guest-cpp-1", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
