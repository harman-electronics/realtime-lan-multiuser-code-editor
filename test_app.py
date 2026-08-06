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

        replacement_paths["STUDENTS_FILE"].write_text(
            json.dumps(app_module.DEFAULT_STUDENTS),
            encoding="utf-8",
        )
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

    def login_student(self, student_id="ST001", dob="2005-06-15"):
        response = self.client.post(
            "/api/auth/login",
            json={
                "role": "student",
                "student_id": student_id,
                "date_of_birth": dob,
                "password": "test1",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    @staticmethod
    def auth_header(token):
        return {"Authorization": f"Bearer {token}"}

    def test_role_logins_and_saved_student_name(self):
        wrong_admin = self.client.post(
            "/api/auth/login",
            json={"role": "admin", "password": "wrong"},
        )
        self.assertEqual(wrong_admin.status_code, 401)
        self.assertEqual(
            wrong_admin.json()["detail"],
            "Incorrect Admin password.",
        )

        wrong_student = self.client.post(
            "/api/auth/login",
            json={
                "role": "student",
                "student_id": "ST001",
                "date_of_birth": "2000-01-01",
                "password": "test1",
            },
        )
        self.assertEqual(wrong_student.status_code, 401)

        token = self.login_student()
        current = self.client.get(
            "/api/auth/me",
            headers=self.auth_header(token),
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(
            current.json()["user"],
            {
                "account_id": "student_st001",
                "username": "John Smith",
                "role": "student",
            },
        )

    def test_admin_can_add_and_remove_students(self):
        admin_token = self.login_admin()
        added = self.client.post(
            "/api/students",
            headers=self.auth_header(admin_token),
            json={
                "full_name": "Alice Jones",
                "student_id": "ST003",
                "date_of_birth": "20/02/2005",
                "other_info": {"class": "A"},
            },
        )
        self.assertEqual(added.status_code, 200, added.text)
        student = added.json()["student"]
        self.assertEqual(student["date_of_birth"], "2005-02-20")
        self.assertEqual(
            self.manager.get_student_by_id("ST003")["full_name"],
            "Alice Jones",
        )

        duplicate = self.client.post(
            "/api/students",
            headers=self.auth_header(admin_token),
            json={
                "full_name": "Duplicate",
                "student_id": "ST003",
                "date_of_birth": "2005-02-20",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        removed = self.client.delete(
            f"/api/students/{student['account_id']}",
            headers=self.auth_header(admin_token),
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(self.manager.get_student_by_id("ST003"))

    def test_only_one_active_student_session(self):
        token = self.login_student()
        with self.client.websocket_connect("/ws/john_first") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {"type": "join", "token": token, "color": "#2196F3"}
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(
                websocket.receive_json()["type"],
                "presence_updated",
            )

            duplicate = self.client.post(
                "/api/auth/login",
                json={
                    "role": "student",
                    "student_id": "ST001",
                    "date_of_birth": "2005-06-15",
                    "password": "test1",
                },
            )
            self.assertEqual(duplicate.status_code, 409)
            self.assertIn("active session", duplicate.json()["detail"])

    def test_admin_file_tabs_and_six_tab_limit(self):
        admin_token = self.login_admin()
        with self.client.websocket_connect("/ws/admin_files") as websocket:
            self.assertEqual(websocket.receive_json()["type"], "init")
            websocket.send_json(
                {"type": "join", "token": admin_token, "color": "#FF5722"}
            )
            self.assertEqual(websocket.receive_json()["type"], "join_success")
            self.assertEqual(
                websocket.receive_json()["type"],
                "presence_updated",
            )

            for index in range(1, 6):
                language = "cpp" if index % 2 else "python"
                websocket.send_json(
                    {
                        "type": "create_file",
                        "name": f"lesson_{index}",
                        "language": language,
                    }
                )
                update = websocket.receive_json()
                self.assertEqual(update["type"], "workspace_updated")

            self.assertEqual(len(self.manager.workspace["files"]), 6)
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
            "account_id": "student_st001",
            "username": "John Smith",
            "role": "student",
            "color": "#2196F3",
        }
        bob = {
            "account_id": "student_st002",
            "username": "Bob",
            "role": "student",
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
            "student_st001",
        )

        self.manager.access_control["owner_grants"] = {
            "student_st001": ["student_st002"]
        }
        self.assertTrue(
            self.manager.can_user_edit_range(bob, "file_main", 0, 0)
        )

        self.manager.access_control["owner_grants"] = {}
        self.manager.access_control["global_editors"] = ["student_st002"]
        self.assertTrue(
            self.manager.can_user_edit_range(bob, "file_main", 0, 0)
        )

    def test_access_settings_report_incoming_and_global_permissions(self):
        john_token = self.login_student("ST001", "2005-06-15")
        bob_token = self.login_student("ST002", "2005-01-01")
        admin_token = self.login_admin()

        owner_grant = self.client.put(
            "/api/access/owner/student_st002",
            headers=self.auth_header(john_token),
            json={"enabled": True},
        )
        self.assertEqual(owner_grant.status_code, 200)

        bob_access = self.client.get(
            "/api/access",
            headers=self.auth_header(bob_token),
        )
        self.assertEqual(bob_access.status_code, 200)
        self.assertIn(
            "student_st001",
            bob_access.json()["editable_owner_ids"],
        )

        global_grant = self.client.put(
            "/api/access/global/student_st002",
            headers=self.auth_header(admin_token),
            json={"enabled": True},
        )
        self.assertEqual(global_grant.status_code, 200)
        bob_access = self.client.get(
            "/api/access",
            headers=self.auth_header(bob_token),
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
        self.assertEqual(
            self.manager.get_session(admin_token)["role"],
            "admin",
        )
        self.assertEqual(
            self.manager.get_session(admin_token)["username"],
            "Professor Ada",
        )

    def test_chat_message_editing_enforces_ownership_and_persists(self):
        message = {
            "id": 101,
            "sender_account_id": "student_st001",
            "sender": "John Smith",
            "sender_role": "student",
            "target": "group",
            "text": "Original message",
        }
        self.manager.add_chat_message(message)
        john = {"account_id": "student_st001", "role": "student"}
        bob = {"account_id": "student_st002", "role": "student"}

        with self.assertRaises(app_module.HTTPException) as denied:
            self.manager.edit_chat_message(101, bob, "Changed by Bob")
        self.assertEqual(denied.exception.status_code, 403)

        edited = self.manager.edit_chat_message(101, john, "Updated safely")
        self.assertEqual(edited["text"], "Updated safely")
        self.assertTrue(edited["edited"])
        stored = json.loads(Path(app_module.CHAT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(stored[0]["text"], "Updated safely")

    def test_chat_message_deletion_permissions_and_persistence(self):
        message = {
            "id": 202,
            "sender_account_id": "student_st001",
            "sender": "John Smith",
            "sender_role": "student",
            "target": "group",
            "text": "Remove this message",
        }
        self.manager.add_chat_message(message)
        bob = {"account_id": "student_st002", "role": "student"}
        admin = {"account_id": "admin", "role": "admin"}

        with self.assertRaises(app_module.HTTPException) as denied:
            self.manager.delete_chat_message(202, bob)
        self.assertEqual(denied.exception.status_code, 403)

        deleted = self.manager.delete_chat_message(202, admin)
        self.assertEqual(deleted["id"], 202)
        self.assertEqual(self.manager.chat_history, [])
        stored = json.loads(Path(app_module.CHAT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(stored, [])

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
                "stdin": "LAN student\n",
            },
        )
        self.assertEqual(input_response.status_code, 200, input_response.text)
        self.assertEqual(input_response.json()["stdout"].strip(), "Hello, LAN student!")

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
        self.assertEqual(
            result["stdout"].strip(),
            "120\nHello, Bob!\n8 9 3",
        )

    @unittest.skipUnless(
        shutil.which("g++") or shutil.which("clang++"),
        "g++ or clang++ is not installed on the host",
    )
    def test_cpp17_compilation_and_execution(self):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
