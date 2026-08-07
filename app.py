import asyncio
import base64
import hmac
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import qrcode
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI(title="Live Code Editor")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("LIVE_EDITOR_DATA_DIR", os.path.join(BASE_DIR, "data"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")  # Kept for legacy data compatibility.
CODE_FILE = os.path.join(DATA_DIR, "code_state.json")
LEGACY_LINE_AUTHORS_FILE = os.path.join(DATA_DIR, "line_authors.json")
STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
GUESTS_FILE = os.path.join(DATA_DIR, "guests.json")
JOIN_REQUESTS_FILE = os.path.join(DATA_DIR, "join_requests.json")
WORKSPACE_FILE = os.path.join(DATA_DIR, "workspace_state.json")
FILE_AUTHORS_FILE = os.path.join(DATA_DIR, "file_line_authors.json")
ACCESS_FILE = os.path.join(DATA_DIR, "access_control.json")
SNAPSHOTS_FILE = os.path.join(DATA_DIR, "snapshots.json")
CHAT_FILE = os.path.join(DATA_DIR, "chat_history.json")

ADMIN_PASSWORD = os.environ.get("LIVE_EDITOR_ADMIN_PASSWORD", "12345")
SESSION_LIFETIME_SECONDS = 12 * 60 * 60
JOIN_REQUEST_TTL_SECONDS = 30 * 60
MAX_MESSAGE_LENGTH = 5000
MAX_CODE_SIZE = 500_000
MAX_STDIN_SIZE = 20_000
MAX_TAB_LIMIT = 15

COLOR_PALETTE = [
    "#FF5722", "#E91E63", "#9C27B0", "#673AB7",
    "#3F51B5", "#2196F3", "#00BCD4", "#009688",
    "#4CAF50", "#8BC34A", "#FF9800", "#795548",
]

DEFAULT_STUDENTS = [
    {
        "account_id": "student_st001",
        "full_name": "John Smith",
        "student_id": "ST001",
        "date_of_birth": "2005-06-15",
        "other_info": {},
        "active": True,
    },
    {
        "account_id": "student_st002",
        "full_name": "Bob",
        "student_id": "ST002",
        "date_of_birth": "2005-01-01",
        "other_info": {},
        "active": True,
    },
]


def load_json(filepath: str, default: Any) -> Any:
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def save_json(filepath: str, data: Any) -> None:
    """Write JSON atomically so an interrupted save cannot corrupt the live file."""
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, filepath)


def normalize_date(value: str) -> str:
    value = (value or "").strip()
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise HTTPException(
        status_code=422,
        detail="Date of birth must use YYYY-MM-DD or DD/MM/YYYY.",
    )


def normalize_student_id(value: str) -> str:
    student_id = re.sub(r"\s+", "", (value or "").strip().upper())
    if not re.fullmatch(r"[A-Z0-9_-]{2,30}", student_id):
        raise HTTPException(
            status_code=422,
            detail="Student ID must contain 2-30 letters, numbers, underscores, or hyphens.",
        )
    return student_id


def normalize_display_name(value: str) -> str:
    name = re.sub(r"\s+", " ", (value or "").strip())
    if not 1 <= len(name) <= 50:
        raise HTTPException(status_code=422, detail="Name must contain 1-50 characters.")
    return name


def normalize_file_name(value: str, language: str) -> str:
    name = os.path.basename((value or "").strip())
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        raise HTTPException(status_code=422, detail="File name cannot be empty.")
    if len(name) > 60:
        raise HTTPException(status_code=422, detail="File name cannot exceed 60 characters.")
    expected_extension = ".cpp" if language == "cpp" else ".py"
    root, extension = os.path.splitext(name)
    if extension.lower() not in (".py", ".cpp"):
        name += expected_extension
    elif extension.lower() != expected_extension:
        name = root + expected_extension
    return name


def get_local_ip() -> str:
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.connect(("8.8.8.8", 80))
        ip = udp_socket.getsockname()[0]
        udp_socket.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def generate_qr_code(url: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#1E293B", back_color="#FFFFFF")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def pos_to_offset(code: str, line: int, ch: int) -> int:
    lines = code.split("\n")
    safe_line = max(0, min(int(line), len(lines) - 1))
    safe_ch = max(0, min(int(ch), len(lines[safe_line])))
    return sum(len(item) + 1 for item in lines[:safe_line]) + safe_ch


def apply_delta_to_code(
    code: str,
    from_pos: Dict[str, int],
    to_pos: Dict[str, int],
    text_lines: List[str],
) -> str:
    start = pos_to_offset(code, from_pos.get("line", 0), from_pos.get("ch", 0))
    end = pos_to_offset(code, to_pos.get("line", 0), to_pos.get("ch", 0))
    if end < start:
        start, end = end, start
    replacement = "\n".join(text_lines)
    return code[:start] + replacement + code[end:]


class LoginRequest(BaseModel):
    role: str
    password: str


class GuestJoinRequest(BaseModel):
    full_name: str


class AdminNameRequest(BaseModel):
    display_name: str


class ToggleRequest(BaseModel):
    enabled: bool


class TabLimitRequest(BaseModel):
    tab_limit: int


class RunCodeRequest(BaseModel):
    code: str
    language: str = "python"
    stdin: str = ""
    timeout: Optional[float] = 5.0


class SnapshotRequest(BaseModel):
    label: str
    code: str
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    language: str = "python"


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_data: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.state_lock = asyncio.Lock()
        self.guests: List[Dict[str, Any]] = self._load_guests()
        self.join_requests: List[Dict[str, Any]] = load_json(
            JOIN_REQUESTS_FILE,
            [],
        )
        self.workspace = self._load_workspace()
        self.line_authors = self._load_line_authors()
        self.access_control = load_json(
            ACCESS_FILE,
            {"owner_grants": {}, "global_editors": []},
        )
        self.chat_history: List[Dict[str, Any]] = load_json(CHAT_FILE, [])

    def _load_workspace(self) -> Dict[str, Any]:
        legacy = load_json(
            CODE_FILE,
            {"code": "# Write code here...\n", "language": "python"},
        )
        default_workspace = {
            "tab_limit": 6,
            "files": [
                {
                    "id": "file_main",
                    "name": "main.py",
                    "language": legacy.get("language", "python"),
                    "code": legacy.get("code", ""),
                    "revision": 0,
                }
            ],
        }
        workspace = load_json(WORKSPACE_FILE, default_workspace)
        files = workspace.get("files")
        if not isinstance(files, list) or not files:
            workspace = default_workspace
        workspace["tab_limit"] = max(
            1,
            min(int(workspace.get("tab_limit", 6)), MAX_TAB_LIMIT),
        )
        for file_data in workspace["files"]:
            file_data.setdefault("revision", 0)
            file_data["language"] = (
                "cpp" if file_data.get("language") == "cpp" else "python"
            )
        return workspace

    def _load_guests(self) -> List[Dict[str, Any]]:
        if os.path.exists(GUESTS_FILE):
            guests = load_json(GUESTS_FILE, [])
            return guests if isinstance(guests, list) else []
        legacy_students = load_json(
            STUDENTS_FILE,
            json.loads(json.dumps(DEFAULT_STUDENTS)),
        )
        migrated = [
            {
                "account_id": student.get("account_id")
                or f"guest_{uuid.uuid4().hex[:16]}",
                "full_name": student.get("full_name", "Guest"),
                "active": bool(student.get("active", True)),
                "joined_at": student.get("joined_at")
                or datetime.now().isoformat(timespec="seconds"),
            }
            for student in legacy_students
            if isinstance(student, dict) and student.get("full_name")
        ]
        save_json(GUESTS_FILE, migrated)
        return migrated

    def _load_line_authors(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        saved = load_json(FILE_AUTHORS_FILE, {})
        if saved:
            return saved
        first_file_id = self.workspace["files"][0]["id"]
        legacy = load_json(LEGACY_LINE_AUTHORS_FILE, {})
        migrated: Dict[str, Dict[str, str]] = {}
        code_lines = self.workspace["files"][0]["code"].split("\n")
        for line_key, info in legacy.items():
            try:
                line_index = int(line_key)
            except (TypeError, ValueError):
                continue
            if not 0 <= line_index < len(code_lines) or not code_lines[line_index].strip():
                continue
            author = info.get("author", "")
            migrated[str(line_index)] = {
                "account_id": "admin" if author.lower() == "lecturer" else "",
                "author": "Admin" if author.lower() == "lecturer" else author,
                "color": info.get("color", "#38BDF8"),
            }
        return {first_file_id: migrated}

    def save_guests(self) -> None:
        save_json(GUESTS_FILE, self.guests)

    def save_join_requests(self) -> None:
        save_json(JOIN_REQUESTS_FILE, self.join_requests)

    def save_workspace(self) -> None:
        save_json(WORKSPACE_FILE, self.workspace)

    def save_line_authors(self) -> None:
        save_json(FILE_AUTHORS_FILE, self.line_authors)

    def save_access(self) -> None:
        save_json(ACCESS_FILE, self.access_control)

    def get_guest(self, account_id: str) -> Optional[Dict[str, Any]]:
        return next(
            (guest for guest in self.guests if guest["account_id"] == account_id),
            None,
        )

    def get_guest_by_name(self, full_name: str) -> Optional[Dict[str, Any]]:
        normalized = normalize_display_name(full_name).casefold()
        return next(
            (
                guest
                for guest in self.guests
                if guest.get("active", True)
                and str(guest.get("full_name", "")).casefold() == normalized
            ),
            None,
        )

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        return next(
            (file_data for file_data in self.workspace["files"] if file_data["id"] == file_id),
            None,
        )

    def public_workspace(self) -> Dict[str, Any]:
        return {
            "tab_limit": self.workspace["tab_limit"],
            "files": self.workspace["files"],
        }

    def public_guests(self) -> List[Dict[str, Any]]:
        connected_ids = {
            user.get("account_id")
            for user in self.user_data.values()
            if user.get("account_id")
        }
        return [
            {
                "account_id": guest["account_id"],
                "full_name": guest["full_name"],
                "online": guest["account_id"] in connected_ids,
            }
            for guest in self.guests
            if guest.get("active", True)
        ]

    def expire_join_requests(self) -> bool:
        now = time.time()
        changed = False
        for request in self.join_requests:
            if (
                request.get("status") == "pending"
                and now - float(request.get("created_at_epoch", now))
                > JOIN_REQUEST_TTL_SECONDS
            ):
                request["status"] = "expired"
                request["resolved_at"] = datetime.now().isoformat(timespec="seconds")
                changed = True
        if changed:
            self.save_join_requests()
        return changed

    def public_join_requests(self) -> List[Dict[str, Any]]:
        self.expire_join_requests()
        return [
            {
                "id": request["id"],
                "full_name": request["full_name"],
                "status": request["status"],
                "requested_at": request["requested_at"],
            }
            for request in reversed(self.join_requests)
            if request.get("status") == "pending"
        ]

    def create_guest_join_request(self, full_name: str) -> Dict[str, Any]:
        name = normalize_display_name(full_name)
        self.expire_join_requests()
        if any(
            request.get("status") == "pending"
            and str(request.get("full_name", "")).casefold() == name.casefold()
            for request in self.join_requests
        ):
            raise HTTPException(
                status_code=409,
                detail=f"A join request for {name} is already waiting for Admin approval.",
            )
        pending_count = sum(
            request.get("status") == "pending"
            for request in self.join_requests
        )
        if pending_count >= 50:
            raise HTTPException(
                status_code=429,
                detail="Too many join requests are waiting. Ask the Admin to review them.",
            )
        request = {
            "id": f"request_{uuid.uuid4().hex[:16]}",
            "request_token": secrets.token_urlsafe(32),
            "full_name": name,
            "status": "pending",
            "requested_at": datetime.now().isoformat(timespec="seconds"),
            "created_at_epoch": time.time(),
            "account_id": None,
            "session_token": None,
        }
        self.join_requests.append(request)
        self.join_requests = self.join_requests[-200:]
        self.save_join_requests()
        return request

    def get_join_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return next(
            (
                request
                for request in self.join_requests
                if request.get("id") == request_id
            ),
            None,
        )

    def approve_guest_join_request(self, request_id: str) -> Dict[str, Any]:
        request = self.get_join_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Join request not found.")
        if request.get("status") != "pending":
            raise HTTPException(status_code=409, detail="This join request was already resolved.")
        guest = self.get_guest_by_name(request["full_name"])
        if guest and self.is_account_connected(guest["account_id"]):
            raise HTTPException(
                status_code=409,
                detail=f"{guest['full_name']} already has an active session.",
            )
        if not guest:
            guest = {
                "account_id": f"guest_{uuid.uuid4().hex[:16]}",
                "full_name": request["full_name"],
                "active": True,
                "joined_at": datetime.now().isoformat(timespec="seconds"),
            }
            self.guests.append(guest)
            self.save_guests()
        self.revoke_account_sessions(guest["account_id"])
        request["status"] = "approved"
        request["account_id"] = guest["account_id"]
        request["resolved_at"] = datetime.now().isoformat(timespec="seconds")
        self.save_join_requests()
        return request

    def reject_guest_join_request(self, request_id: str) -> Dict[str, Any]:
        request = self.get_join_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Join request not found.")
        if request.get("status") != "pending":
            raise HTTPException(status_code=409, detail="This join request was already resolved.")
        request["status"] = "rejected"
        request["resolved_at"] = datetime.now().isoformat(timespec="seconds")
        self.save_join_requests()
        return request

    def get_guest_join_status(
        self,
        request_id: str,
        request_token: str,
    ) -> Dict[str, Any]:
        self.expire_join_requests()
        request = self.get_join_request(request_id)
        if (
            not request
            or not request.get("request_token")
            or not hmac.compare_digest(
                str(request["request_token"]),
                str(request_token),
            )
        ):
            raise HTTPException(status_code=404, detail="Join request not found.")
        response: Dict[str, Any] = {
            "status": request.get("status", "expired"),
            "full_name": request.get("full_name", "Guest"),
        }
        if request.get("status") != "approved":
            return response
        guest = self.get_guest(str(request.get("account_id", "")))
        if not guest or not guest.get("active", True):
            raise HTTPException(status_code=410, detail="This Guest account is no longer available.")
        token = request.get("session_token")
        if not token or not self.get_session(token):
            if self.is_account_connected(guest["account_id"]):
                raise HTTPException(
                    status_code=409,
                    detail="This Guest already has an active session.",
                )
            token = self.create_session(
                "guest",
                guest["account_id"],
                guest["full_name"],
            )
            request["session_token"] = token
            request["consumed_at"] = datetime.now().isoformat(timespec="seconds")
            self.save_join_requests()
        response.update(
            {
                "token": token,
                "user": {
                    "account_id": guest["account_id"],
                    "username": guest["full_name"],
                    "role": "guest",
                },
            }
        )
        return response

    def create_session(self, role: str, account_id: str, username: str) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            "token": token,
            "role": role,
            "account_id": account_id,
            "username": username,
            "expires_at": time.time() + SESSION_LIFETIME_SECONDS,
        }
        return token

    def get_session(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        session = self.sessions.get(token)
        if not session:
            return None
        if session["expires_at"] <= time.time():
            self.sessions.pop(token, None)
            return None
        return session

    def revoke_session(self, token: str) -> None:
        self.sessions.pop(token, None)

    def revoke_account_sessions(self, account_id: str) -> None:
        for token, session in list(self.sessions.items()):
            if session.get("account_id") == account_id:
                self.sessions.pop(token, None)

    def is_account_connected(
        self,
        account_id: str,
        exclude_connection_id: Optional[str] = None,
    ) -> bool:
        return any(
            connection_id != exclude_connection_id
            and user.get("account_id") == account_id
            for connection_id, user in self.user_data.items()
        )

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.user_data[connection_id] = {
            "id": connection_id,
            "account_id": None,
            "username": None,
            "role": None,
            "color": None,
            "cursor": None,
            "file_id": None,
            "is_typing": False,
            "session_token": None,
        }

    def disconnect(self, connection_id: str) -> Optional[Dict[str, Any]]:
        self.active_connections.pop(connection_id, None)
        return self.user_data.pop(connection_id, None)

    async def kick_account(self, account_id: str) -> None:
        connection_ids = [
            connection_id
            for connection_id, user in self.user_data.items()
            if user.get("account_id") == account_id
        ]
        for connection_id in connection_ids:
            websocket = self.active_connections.get(connection_id)
            self.disconnect(connection_id)
            if websocket:
                try:
                    await websocket.close(code=4003, reason="Account removed by Admin")
                except Exception:
                    pass
        self.revoke_account_sessions(account_id)

    def get_claimed_colors(self) -> Dict[str, str]:
        return {
            user["color"]: user["username"]
            for user in self.user_data.values()
            if user.get("color") and user.get("username")
        }

    def get_active_users(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": user["id"],
                "account_id": user.get("account_id"),
                "username": user.get("username"),
                "role": user.get("role"),
                "color": user.get("color"),
                "cursor": user.get("cursor"),
                "file_id": user.get("file_id"),
                "is_typing": user.get("is_typing", False),
            }
            for user in self.user_data.values()
            if user.get("username")
        ]

    async def broadcast(
        self,
        message: Dict[str, Any],
        exclude: Optional[str] = None,
    ) -> None:
        payload = json.dumps(message)
        failed: List[str] = []
        for connection_id, websocket in list(self.active_connections.items()):
            if connection_id == exclude:
                continue
            try:
                await websocket.send_text(payload)
            except Exception:
                failed.append(connection_id)
        for connection_id in failed:
            self.disconnect(connection_id)

    async def send_private_message(
        self,
        sender_id: str,
        recipient_account_id: str,
        message: Dict[str, Any],
    ) -> None:
        payload = json.dumps(message)
        recipient_connections = [
            connection_id
            for connection_id, user in self.user_data.items()
            if user.get("account_id") == recipient_account_id
        ]
        for connection_id in set(recipient_connections + [sender_id]):
            websocket = self.active_connections.get(connection_id)
            if websocket:
                try:
                    await websocket.send_text(payload)
                except Exception:
                    self.disconnect(connection_id)

    async def send_to_accounts(
        self,
        account_ids: List[str],
        message: Dict[str, Any],
    ) -> None:
        payload = json.dumps(message)
        target_ids = {account_id for account_id in account_ids if account_id}
        connection_ids = [
            connection_id
            for connection_id, user in self.user_data.items()
            if user.get("account_id") in target_ids
        ]
        for connection_id in set(connection_ids):
            websocket = self.active_connections.get(connection_id)
            if websocket:
                try:
                    await websocket.send_text(payload)
                except Exception:
                    self.disconnect(connection_id)

    async def send_to_role(
        self,
        role: str,
        message: Dict[str, Any],
    ) -> None:
        payload = json.dumps(message)
        connection_ids = [
            connection_id
            for connection_id, user in self.user_data.items()
            if user.get("role") == role
        ]
        for connection_id in connection_ids:
            websocket = self.active_connections.get(connection_id)
            if websocket:
                try:
                    await websocket.send_text(payload)
                except Exception:
                    self.disconnect(connection_id)

    def can_edit_owner(self, actor: Dict[str, Any], owner_account_id: str) -> bool:
        actor_id = actor.get("account_id")
        if actor.get("role") == "admin":
            return True
        if actor_id in self.access_control.get("global_editors", []):
            return True
        if not owner_account_id or owner_account_id == actor_id:
            return True
        grants = self.access_control.get("owner_grants", {}).get(owner_account_id, [])
        return actor_id in grants

    def is_line_empty(self, file_id: str, line_index: int) -> bool:
        file_data = self.get_file(file_id)
        if not file_data:
            return True
        lines = file_data["code"].split("\n")
        return not (0 <= line_index < len(lines)) or not lines[line_index].strip()

    def can_user_edit_range(
        self,
        actor: Dict[str, Any],
        file_id: str,
        start_line: int,
        end_line: int,
    ) -> bool:
        authors = self.line_authors.setdefault(file_id, {})
        for line_index in range(max(0, start_line), max(start_line, end_line) + 1):
            if self.is_line_empty(file_id, line_index):
                continue
            info = authors.get(str(line_index), {})
            if info and not self.can_edit_owner(actor, info.get("account_id", "")):
                return False
        return True

    def apply_delta(
        self,
        file_id: str,
        from_pos: Dict[str, int],
        to_pos: Dict[str, int],
        text_lines: List[str],
        actor: Dict[str, Any],
    ) -> Dict[str, Any]:
        file_data = self.get_file(file_id)
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found.")

        old_code = file_data["code"]
        old_lines = old_code.split("\n")
        start_line = max(0, min(int(from_pos.get("line", 0)), len(old_lines) - 1))
        end_line = max(start_line, min(int(to_pos.get("line", start_line)), len(old_lines) - 1))
        new_code = apply_delta_to_code(old_code, from_pos, to_pos, text_lines)
        if len(new_code) > MAX_CODE_SIZE:
            raise HTTPException(status_code=413, detail="File is too large.")

        old_authors = self.line_authors.setdefault(file_id, {})
        replacement_count = len(text_lines)
        removed_count = end_line - start_line + 1
        line_shift = replacement_count - removed_count
        new_authors: Dict[str, Dict[str, str]] = {}

        for key, info in old_authors.items():
            index = int(key)
            if index < start_line:
                new_authors[str(index)] = info
            elif index > end_line:
                new_authors[str(index + line_shift)] = info

        preserved_owner = old_authors.get(str(start_line))
        actor_owner = {
            "account_id": actor.get("account_id", ""),
            "author": actor.get("username", "Guest"),
            "color": actor.get("color", "#38BDF8"),
        }
        resulting_lines = new_code.split("\n")
        for offset in range(replacement_count):
            index = start_line + offset
            if index >= len(resulting_lines) or not resulting_lines[index].strip():
                continue
            if offset == 0 and preserved_owner:
                new_authors[str(index)] = preserved_owner
            else:
                new_authors[str(index)] = actor_owner

        file_data["code"] = new_code
        file_data["revision"] = int(file_data.get("revision", 0)) + 1
        self.line_authors[file_id] = new_authors
        self.save_workspace()
        self.save_line_authors()
        return file_data

    def insert_blank_lines(
        self,
        file_id: str,
        after_line: int,
        count: int,
    ) -> Dict[str, Any]:
        file_data = self.get_file(file_id)
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found.")
        lines = file_data["code"].split("\n")
        safe_line = max(-1, min(int(after_line), len(lines) - 1))
        count = max(1, min(int(count), 20))
        insert_at = safe_line + 1
        lines[insert_at:insert_at] = [""] * count
        file_data["code"] = "\n".join(lines)
        file_data["revision"] = int(file_data.get("revision", 0)) + 1

        authors = self.line_authors.setdefault(file_id, {})
        shifted: Dict[str, Dict[str, str]] = {}
        for key, info in authors.items():
            index = int(key)
            shifted[str(index + count if index >= insert_at else index)] = info
        self.line_authors[file_id] = shifted
        self.save_workspace()
        self.save_line_authors()
        return file_data

    def create_file(self, name: str, language: str) -> Dict[str, Any]:
        language = "cpp" if language == "cpp" else "python"
        if len(self.workspace["files"]) >= self.workspace["tab_limit"]:
            raise HTTPException(
                status_code=409,
                detail=f"The current tab limit is {self.workspace['tab_limit']}.",
            )
        normalized_name = normalize_file_name(name, language)
        if any(
            file_data["name"].lower() == normalized_name.lower()
            for file_data in self.workspace["files"]
        ):
            raise HTTPException(status_code=409, detail="A file with that name already exists.")
        file_data = {
            "id": f"file_{uuid.uuid4().hex[:12]}",
            "name": normalized_name,
            "language": language,
            "code": "",
            "revision": 0,
        }
        self.workspace["files"].append(file_data)
        self.line_authors[file_data["id"]] = {}
        self.save_workspace()
        self.save_line_authors()
        return file_data

    def delete_file(self, file_id: str) -> None:
        if len(self.workspace["files"]) <= 1:
            raise HTTPException(status_code=409, detail="At least one file must remain open.")
        file_data = self.get_file(file_id)
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found.")
        self.workspace["files"] = [
            item for item in self.workspace["files"] if item["id"] != file_id
        ]
        self.line_authors.pop(file_id, None)
        self.save_workspace()
        self.save_line_authors()

    def add_chat_message(self, message: Dict[str, Any]) -> None:
        self.chat_history.append(message)
        self.chat_history = self.chat_history[-300:]
        save_json(CHAT_FILE, self.chat_history)

    def get_chat_message(self, message_id: Any) -> Optional[Dict[str, Any]]:
        return next(
            (
                message
                for message in self.chat_history
                if str(message.get("id")) == str(message_id)
            ),
            None,
        )

    def edit_chat_message(
        self,
        message_id: Any,
        actor: Dict[str, Any],
        text: str,
    ) -> Dict[str, Any]:
        message = self.get_chat_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found.")
        sender_account_id = message.get("sender_account_id")
        if not sender_account_id:
            raise HTTPException(
                status_code=409,
                detail="This older message cannot be edited safely.",
            )
        if sender_account_id != actor.get("account_id"):
            raise HTTPException(
                status_code=403,
                detail="You can edit only your own messages.",
            )
        cleaned_text = str(text).strip()[:MAX_MESSAGE_LENGTH]
        if not cleaned_text:
            raise HTTPException(status_code=422, detail="A message cannot be empty.")
        message["text"] = cleaned_text
        message["edited"] = True
        message["edited_at"] = datetime.now().isoformat(timespec="seconds")
        save_json(CHAT_FILE, self.chat_history)
        return message

    def delete_chat_message(
        self,
        message_id: Any,
        actor: Dict[str, Any],
    ) -> Dict[str, Any]:
        message = self.get_chat_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found.")
        is_owner = (
            bool(message.get("sender_account_id"))
            and message.get("sender_account_id") == actor.get("account_id")
        )
        if not is_owner and actor.get("role") != "admin":
            raise HTTPException(
                status_code=403,
                detail="You can delete only your own messages.",
            )
        self.chat_history = [
            item
            for item in self.chat_history
            if str(item.get("id")) != str(message_id)
        ]
        save_json(CHAT_FILE, self.chat_history)
        return message

    def get_chat_history_for_user(self, account_id: str) -> List[Dict[str, Any]]:
        return [
            message
            for message in self.chat_history
            if message.get("target") == "group"
            or message.get("target_account_id") == account_id
            or message.get("sender_account_id") == account_id
        ]

    def mark_chat_read(self, account_id: str, target_account_id: str) -> None:
        changed = False
        for message in self.chat_history:
            participants = {
                message.get("sender_account_id"),
                message.get("target_account_id"),
            }
            if participants == {account_id, target_account_id}:
                read_by = message.setdefault("read_by", [])
                if account_id not in read_by:
                    read_by.append(account_id)
                    changed = True
        if changed:
            save_json(CHAT_FILE, self.chat_history)

    def rename_account(self, account_id: str, new_name: str) -> None:
        for session in self.sessions.values():
            if session.get("account_id") == account_id:
                session["username"] = new_name
        for user in self.user_data.values():
            if user.get("account_id") == account_id:
                user["username"] = new_name
        for file_authors in self.line_authors.values():
            for info in file_authors.values():
                if info.get("account_id") == account_id:
                    info["author"] = new_name
        self.save_line_authors()


manager = ConnectionManager()


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return authorization.split(" ", 1)[1].strip()


def require_session(
    authorization: Optional[str],
    role: Optional[str] = None,
) -> Dict[str, Any]:
    token = extract_bearer_token(authorization)
    session = manager.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    if role and session.get("role") != role:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return session


@app.get("/api/info")
def get_info() -> Dict[str, Any]:
    ip = get_local_ip()
    port = 8000
    lan_url = f"http://{ip}:{port}"
    return {
        "ip": ip,
        "port": port,
        "lan_url": lan_url,
        "qr_code": generate_qr_code(lan_url),
        "palette": COLOR_PALETTE,
        "claimed_colors": manager.get_claimed_colors(),
        "active_users": manager.get_active_users(),
    }


@app.post("/api/auth/login")
async def login(request: LoginRequest) -> Dict[str, Any]:
    role = request.role.strip().lower()
    if role != "admin":
        raise HTTPException(
            status_code=422,
            detail="Guests must request access from the Guest login option.",
        )
    if not hmac.compare_digest(request.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Incorrect Admin password.")
    token = manager.create_session("admin", "admin", "Admin")
    return {
        "token": token,
        "user": {"account_id": "admin", "username": "Admin", "role": "admin"},
    }


@app.get("/api/auth/me")
async def get_current_session(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    session = require_session(authorization)
    return {
        "user": {
            "account_id": session["account_id"],
            "username": session["username"],
            "role": session["role"],
        }
    }


@app.post("/api/auth/logout")
async def logout(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    token = extract_bearer_token(authorization)
    session = manager.get_session(token)
    if session:
        await manager.kick_account(session["account_id"])
    manager.revoke_session(token)
    await manager.broadcast(
        {
            "type": "presence_updated",
            "active_users": manager.get_active_users(),
            "claimed_colors": manager.get_claimed_colors(),
        }
    )
    return {"status": "success"}


@app.post("/api/guest-requests")
async def create_guest_request(
    request: GuestJoinRequest,
) -> Dict[str, Any]:
    join_request = manager.create_guest_join_request(request.full_name)
    public_request = {
        "id": join_request["id"],
        "full_name": join_request["full_name"],
        "status": join_request["status"],
        "requested_at": join_request["requested_at"],
    }
    await manager.send_to_role(
        "admin",
        {
            "type": "join_request_created",
            "request": public_request,
            "pending_count": len(manager.public_join_requests()),
        },
    )
    return {
        "request_id": join_request["id"],
        "request_token": join_request["request_token"],
        "status": join_request["status"],
        "full_name": join_request["full_name"],
    }


@app.get("/api/guest-requests/{request_id}/status")
async def get_guest_request_status(
    request_id: str,
    request_token: str,
) -> Dict[str, Any]:
    return manager.get_guest_join_status(request_id, request_token)


@app.get("/api/join-requests")
async def get_join_requests(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization, role="admin")
    requests = manager.public_join_requests()
    return {"requests": requests, "pending_count": len(requests)}


@app.post("/api/join-requests/{request_id}/approve")
async def approve_join_request(
    request_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization, role="admin")
    request = manager.approve_guest_join_request(request_id)
    await manager.send_to_role(
        "admin",
        {
            "type": "join_requests_updated",
            "pending_count": len(manager.public_join_requests()),
        },
    )
    await manager.broadcast(
        {
            "type": "guest_records_updated",
            "guests": manager.public_guests(),
        }
    )
    return {
        "status": "success",
        "request": {
            "id": request["id"],
            "full_name": request["full_name"],
            "status": request["status"],
        },
    }


@app.post("/api/join-requests/{request_id}/reject")
async def reject_join_request(
    request_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization, role="admin")
    request = manager.reject_guest_join_request(request_id)
    await manager.send_to_role(
        "admin",
        {
            "type": "join_requests_updated",
            "pending_count": len(manager.public_join_requests()),
        },
    )
    return {
        "status": "success",
        "request": {
            "id": request["id"],
            "full_name": request["full_name"],
            "status": request["status"],
        },
    }


@app.get("/api/guests")
async def get_guests(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization, role="admin")
    return {"guests": manager.public_guests()}


@app.delete("/api/guests/{account_id}")
async def remove_guest(
    account_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    require_session(authorization, role="admin")
    guest = manager.get_guest(account_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found.")
    await manager.kick_account(account_id)
    manager.guests = [
        item for item in manager.guests if item["account_id"] != account_id
    ]
    manager.access_control.get("owner_grants", {}).pop(account_id, None)
    for grants in manager.access_control.get("owner_grants", {}).values():
        while account_id in grants:
            grants.remove(account_id)
    manager.access_control["global_editors"] = [
        item
        for item in manager.access_control.get("global_editors", [])
        if item != account_id
    ]
    manager.save_guests()
    manager.save_access()
    await manager.broadcast(
        {
            "type": "guest_records_updated",
            "guests": manager.public_guests(),
            "active_users": manager.get_active_users(),
        }
    )
    return {"status": "success"}


@app.put("/api/admin/name")
async def change_admin_name(
    request: AdminNameRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    session = require_session(authorization, role="admin")
    new_name = normalize_display_name(request.display_name)
    manager.rename_account("admin", new_name)
    session["username"] = new_name
    await manager.broadcast(
        {
            "type": "account_name_updated",
            "account_id": "admin",
            "username": new_name,
            "active_users": manager.get_active_users(),
        }
    )
    return {"status": "success", "username": new_name}


@app.get("/api/access")
async def get_access_settings(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    session = require_session(authorization)
    users = manager.public_guests()
    if session["role"] == "admin":
        enabled_ids = set(manager.access_control.get("global_editors", []))
        return {
            "mode": "global",
            "users": [
                {**user, "enabled": user["account_id"] in enabled_ids}
                for user in users
            ],
        }
    grants = set(
        manager.access_control.get("owner_grants", {}).get(
            session["account_id"],
            [],
        )
    )
    editable_owner_ids = [
        owner_account_id
        for owner_account_id, owner_grants in manager.access_control.get(
            "owner_grants",
            {},
        ).items()
        if session["account_id"] in owner_grants
    ]
    global_editor = session["account_id"] in manager.access_control.get(
        "global_editors",
        [],
    )
    return {
        "mode": "owner",
        "global_editor": global_editor,
        "editable_owner_ids": editable_owner_ids,
        "users": [
            {**user, "enabled": user["account_id"] in grants}
            for user in users
            if user["account_id"] != session["account_id"]
        ],
    }


@app.put("/api/access/owner/{grantee_account_id}")
async def update_owner_access(
    grantee_account_id: str,
    request: ToggleRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    session = require_session(authorization)
    if session["role"] != "guest":
        raise HTTPException(status_code=403, detail="Guest access setting required.")
    if not manager.get_guest(grantee_account_id):
        raise HTTPException(status_code=404, detail="Guest not found.")
    grants = manager.access_control.setdefault("owner_grants", {}).setdefault(
        session["account_id"],
        [],
    )
    if request.enabled and grantee_account_id not in grants:
        grants.append(grantee_account_id)
    if not request.enabled and grantee_account_id in grants:
        grants.remove(grantee_account_id)
    manager.save_access()
    await manager.broadcast({"type": "access_updated"})
    return {"status": "success"}


@app.put("/api/access/global/{guest_account_id}")
async def update_global_access(
    guest_account_id: str,
    request: ToggleRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    require_session(authorization, role="admin")
    if not manager.get_guest(guest_account_id):
        raise HTTPException(status_code=404, detail="Guest not found.")
    global_editors = manager.access_control.setdefault("global_editors", [])
    if request.enabled and guest_account_id not in global_editors:
        global_editors.append(guest_account_id)
    if not request.enabled and guest_account_id in global_editors:
        global_editors.remove(guest_account_id)
    manager.save_access()
    await manager.broadcast({"type": "access_updated"})
    return {"status": "success"}


@app.put("/api/settings/tab-limit")
async def update_tab_limit(
    request: TabLimitRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization, role="admin")
    if not 1 <= request.tab_limit <= MAX_TAB_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=f"Tab limit must be between 1 and {MAX_TAB_LIMIT}.",
        )
    if request.tab_limit < len(manager.workspace["files"]):
        raise HTTPException(
            status_code=409,
            detail="Close files before lowering the limit below the current tab count.",
        )
    manager.workspace["tab_limit"] = request.tab_limit
    manager.save_workspace()
    await manager.broadcast(
        {
            "type": "workspace_updated",
            "workspace": manager.public_workspace(),
            "line_authors": manager.line_authors,
        }
    )
    return {"status": "success", "tab_limit": request.tab_limit}


PYTHON_PROBLEM_EXPLANATIONS = {
    "SyntaxError": "Python could not understand the statement. Check punctuation, brackets, and the structure near this line.",
    "IndentationError": "The indentation level is invalid. Align this line with the block it belongs to.",
    "TabError": "Tabs and spaces are mixed inconsistently. Use one indentation style throughout the block.",
    "NameError": "A name is being used before Python can find a matching variable, function, or import.",
    "TypeError": "An operation received a value of the wrong type or an unsupported combination of types.",
    "ValueError": "The value has the correct general type, but its content is not valid for this operation.",
    "ZeroDivisionError": "The code attempted to divide by zero. Check the divisor before performing the calculation.",
    "IndexError": "A list, tuple, or string position is outside the available range.",
    "KeyError": "The requested dictionary key does not exist.",
    "AttributeError": "This value does not provide the requested attribute or method.",
    "ImportError": "Python could not import the requested name or module.",
    "ModuleNotFoundError": "The requested Python module is not installed or cannot be found.",
    "RecursionError": "The function called itself too many times without reaching a stopping condition.",
    "AssertionError": "An assertion condition evaluated to false.",
}


def explain_cpp_problem(message: str, severity: str) -> str:
    lowered = message.lower()
    if "was not declared" in lowered or "undeclared identifier" in lowered:
        return "This name is not declared in the current scope. Check its spelling and declaration."
    if "expected" in lowered:
        return "The compiler expected another token or statement here. Check nearby brackets, semicolons, and syntax."
    if "no matching function" in lowered:
        return "No available function accepts the arguments used in this call."
    if "invalid conversion" in lowered or "cannot convert" in lowered:
        return "The value cannot be converted to the required type without changing the code."
    if "redefinition" in lowered:
        return "This name or function has already been defined in the same scope."
    if "missing terminating" in lowered:
        return "A string or character literal is missing its closing quotation mark."
    if severity == "warning":
        return "The program can compile, but this line may cause unexpected behaviour."
    if severity == "note":
        return "The compiler included this related location to explain another problem."
    return "The C++ compiler rejected this statement. Review the message and the code around this location."


def parse_execution_problems(
    result: Dict[str, Any],
    language: str,
) -> List[Dict[str, Any]]:
    stderr = str(result.get("stderr") or "")
    returncode = int(result.get("returncode") or 0)
    stage = str(result.get("stage") or "run")
    if not stderr and returncode == 0:
        return []

    if language == "cpp":
        problems: List[Dict[str, Any]] = []
        pattern = re.compile(
            r"^.*?:(\d+):(\d+):\s*(fatal error|error|warning|note):\s*(.+)$",
            re.IGNORECASE,
        )
        for raw_line in stderr.splitlines():
            match = pattern.match(raw_line.strip())
            if not match:
                continue
            severity_text = match.group(3).lower()
            severity = (
                "error"
                if severity_text in {"error", "fatal error"}
                else severity_text
            )
            message = match.group(4).strip()
            problems.append(
                {
                    "line": int(match.group(1)),
                    "column": int(match.group(2)),
                    "severity": severity,
                    "type": "C++ Compiler Error" if severity == "error" else f"C++ {severity.title()}",
                    "message": message,
                    "explanation": explain_cpp_problem(message, severity),
                }
            )
        if problems:
            return problems
        if stderr or returncode != 0:
            message = stderr.strip() or f"Program exited with code {returncode}."
            return [
                {
                    "line": None,
                    "column": None,
                    "severity": "error",
                    "type": "C++ Compiler Error" if stage == "compile" else "C++ Runtime Error",
                    "message": message,
                    "explanation": (
                        "The compiler could not run in this environment."
                        if "compiler not found" in message.lower()
                        else "The program failed without a source location. Check the Terminal output for the complete details."
                    ),
                }
            ]
        return []

    traceback_lines = stderr.splitlines()
    source_line = None
    column = None
    for index, raw_line in enumerate(traceback_lines):
        match = re.search(r'File "<string>", line (\d+)', raw_line)
        if not match:
            continue
        source_line = int(match.group(1))
        if index + 2 < len(traceback_lines):
            caret_line = traceback_lines[index + 2]
            caret_position = caret_line.find("^")
            if caret_position >= 0:
                column = max(1, caret_position - 3)

    problem_type = "Python Runtime Error"
    message = stderr.strip() or f"Program exited with code {returncode}."
    for raw_line in reversed(traceback_lines):
        match = re.match(
            r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::\s*(.*))?$",
            raw_line.strip(),
        )
        if match:
            problem_type = match.group(1)
            message = match.group(2) or match.group(1)
            break

    return [
        {
            "line": source_line,
            "column": column,
            "severity": "error",
            "type": problem_type,
            "message": message,
            "explanation": PYTHON_PROBLEM_EXPLANATIONS.get(
                problem_type,
                "Python stopped while running this code. Check the marked line and the Terminal traceback for context.",
            ),
        }
    ]


def run_python(code: str, stdin: str, timeout: float) -> Dict[str, Any]:
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "stdout": process.stdout,
        "stderr": process.stderr,
        "returncode": process.returncode,
        "stage": "run",
    }


def run_cpp(code: str, stdin: str, timeout: float) -> Dict[str, Any]:
    configured_compiler = os.environ.get("LIVE_EDITOR_CPP_COMPILER")
    compiler = (
        configured_compiler
        if configured_compiler and os.path.isfile(configured_compiler)
        else shutil.which("g++") or shutil.which("clang++")
    )
    if not compiler:
        return {
            "stdout": "",
            "stderr": (
                "C++ compiler not found. Install g++ or clang++, add it to PATH, "
                "or set LIVE_EDITOR_CPP_COMPILER."
            ),
            "returncode": -1,
            "stage": "compile",
        }
    with tempfile.TemporaryDirectory(prefix="live_editor_cpp_") as temp_dir:
        source_path = os.path.join(temp_dir, "main.cpp")
        output_path = os.path.join(
            temp_dir,
            "program.exe" if os.name == "nt" else "program",
        )
        with open(source_path, "w", encoding="utf-8") as source_file:
            source_file.write(code)
        compile_process = subprocess.run(
            [compiler, source_path, "-std=c++17", "-O0", "-o", output_path],
            capture_output=True,
            text=True,
            timeout=min(timeout * 2, 15),
        )
        if compile_process.returncode != 0:
            return {
                "stdout": compile_process.stdout,
                "stderr": compile_process.stderr,
                "returncode": compile_process.returncode,
                "stage": "compile",
            }
        run_process = subprocess.run(
            [output_path],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=temp_dir,
        )
        return {
            "stdout": run_process.stdout,
            "stderr": run_process.stderr,
            "returncode": run_process.returncode,
            "stage": "run",
        }


@app.post("/api/run")
async def run_code(
    request: RunCodeRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization)
    if len(request.code) > MAX_CODE_SIZE:
        raise HTTPException(status_code=413, detail="Code is too large.")
    if len(request.stdin) > MAX_STDIN_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Program input cannot exceed {MAX_STDIN_SIZE:,} characters.",
        )
    timeout = min(max(request.timeout or 5.0, 1.0), 10.0)
    started = time.time()
    try:
        result = (
            run_cpp(request.code, request.stdin, timeout)
            if request.language == "cpp"
            else run_python(request.code, request.stdin, timeout)
        )
        result.update(
            {
                "elapsed": round(time.time() - started, 3),
                "timed_out": False,
            }
        )
        result["problems"] = parse_execution_problems(result, request.language)
        return result
    except subprocess.TimeoutExpired:
        result = {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "returncode": -1,
            "elapsed": round(time.time() - started, 3),
            "timed_out": True,
            "stage": "run",
        }
        result["problems"] = parse_execution_problems(result, request.language)
        return result


@app.get("/api/snapshots")
async def get_snapshots(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_session(authorization)
    return {"snapshots": load_json(SNAPSHOTS_FILE, [])}


@app.post("/api/snapshots")
async def create_snapshot(
    request: SnapshotRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    session = require_session(authorization)
    snapshots = load_json(SNAPSHOTS_FILE, [])
    snapshot = {
        "id": int(time.time() * 1000),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "label": request.label[:100],
        "code": request.code[:MAX_CODE_SIZE],
        "author": session["username"],
        "author_account_id": session["account_id"],
        "file_id": request.file_id,
        "file_name": request.file_name,
        "language": "cpp" if request.language == "cpp" else "python",
    }
    snapshots.insert(0, snapshot)
    save_json(SNAPSHOTS_FILE, snapshots[:200])
    await manager.broadcast({"type": "snapshot_created", "snapshot": snapshot})
    return {"status": "success", "snapshot": snapshot}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    await manager.connect(websocket, client_id)
    try:
        await websocket.send_json(
            {
                "type": "init",
                "workspace": manager.public_workspace(),
                "line_authors": manager.line_authors,
                "palette": COLOR_PALETTE,
                "claimed_colors": manager.get_claimed_colors(),
                "active_users": manager.get_active_users(),
                "guests": manager.public_guests(),
            }
        )

        while True:
            try:
                data = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "message": "Invalid WebSocket message."}
                )
                continue

            message_type = data.get("type")
            user = manager.user_data.get(client_id, {})

            if message_type == "join":
                token = data.get("token")
                session = manager.get_session(token)
                color = data.get("color")
                if not session:
                    await websocket.send_json(
                        {"type": "auth_error", "message": "Session expired. Please log in again."}
                    )
                    continue
                if (
                    session["role"] == "guest"
                    and manager.is_account_connected(
                        session["account_id"],
                        exclude_connection_id=client_id,
                    )
                ):
                    await websocket.send_json(
                        {
                            "type": "auth_error",
                            "message": "This Guest already has an active session.",
                        }
                    )
                    continue
                if color not in COLOR_PALETTE:
                    await websocket.send_json(
                        {"type": "error", "message": "Choose a valid color."}
                    )
                    continue
                claimed = manager.get_claimed_colors()
                if color in claimed and claimed[color] != session["username"]:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"That color is already used by {claimed[color]}.",
                        }
                    )
                    continue
                user.update(
                    {
                        "account_id": session["account_id"],
                        "username": session["username"],
                        "role": session["role"],
                        "color": color,
                        "session_token": token,
                    }
                )
                await websocket.send_json(
                    {
                        "type": "join_success",
                        "user": {
                            "account_id": user["account_id"],
                            "username": user["username"],
                            "role": user["role"],
                            "color": user["color"],
                        },
                        "messages": manager.get_chat_history_for_user(user["account_id"]),
                        "guests": manager.public_guests(),
                        "join_request_count": (
                            len(manager.public_join_requests())
                            if user["role"] == "admin"
                            else 0
                        ),
                    }
                )
                await manager.broadcast(
                    {
                        "type": "presence_updated",
                        "active_users": manager.get_active_users(),
                        "claimed_colors": manager.get_claimed_colors(),
                        "guests": manager.public_guests(),
                    }
                )
                continue

            session = manager.get_session(user.get("session_token"))
            if not session or not user.get("account_id"):
                await websocket.send_json(
                    {"type": "auth_error", "message": "Please log in first."}
                )
                continue

            if message_type == "code_delta":
                file_id = str(data.get("file_id", ""))
                from_pos = data.get("from")
                to_pos = data.get("to")
                text_lines = data.get("text")
                if (
                    not isinstance(from_pos, dict)
                    or not isinstance(to_pos, dict)
                    or not isinstance(text_lines, list)
                    or not all(isinstance(item, str) for item in text_lines)
                ):
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid code change."}
                    )
                    continue
                start_line = int(from_pos.get("line", 0))
                end_line = int(to_pos.get("line", start_line))
                if not manager.can_user_edit_range(
                    user,
                    file_id,
                    start_line,
                    end_line,
                ):
                    file_data = manager.get_file(file_id)
                    await websocket.send_json(
                        {
                            "type": "permission_denied",
                            "message": "This line is read-only. Use Enter to add a new line below it.",
                            "file": file_data,
                            "line_authors": manager.line_authors.get(file_id, {}),
                        }
                    )
                    continue
                async with manager.state_lock:
                    file_data = manager.apply_delta(
                        file_id,
                        from_pos,
                        to_pos,
                        text_lines,
                        user,
                    )
                client_sequence = data.get("client_sequence")
                if not isinstance(client_sequence, int) or isinstance(
                    client_sequence,
                    bool,
                ):
                    client_sequence = None
                await websocket.send_json(
                    {
                        "type": "code_delta_ack",
                        "file_id": file_id,
                        "revision": file_data["revision"],
                        "line_authors": manager.line_authors.get(file_id, {}),
                        "client_sequence": client_sequence,
                    }
                )
                await manager.broadcast(
                    {
                        "type": "code_delta",
                        "file_id": file_id,
                        "from": from_pos,
                        "to": to_pos,
                        "text": text_lines,
                        "revision": file_data["revision"],
                        "line_authors": manager.line_authors.get(file_id, {}),
                    },
                    exclude=client_id,
                )

            elif message_type == "insert_lines":
                file_id = str(data.get("file_id", ""))
                after_line = int(data.get("after_line", 0))
                count = int(data.get("count", 1))
                async with manager.state_lock:
                    file_data = manager.insert_blank_lines(file_id, after_line, count)
                await manager.broadcast(
                    {
                        "type": "file_state",
                        "file": file_data,
                        "line_authors": manager.line_authors.get(file_id, {}),
                        "requester_id": client_id,
                        "focus_line": after_line + count,
                    }
                )

            elif message_type == "create_file":
                if user.get("role") != "admin":
                    await websocket.send_json(
                        {"type": "permission_denied", "message": "Only Admin can create files."}
                    )
                    continue
                try:
                    async with manager.state_lock:
                        file_data = manager.create_file(
                            str(data.get("name", "")),
                            str(data.get("language", "python")),
                        )
                    await manager.broadcast(
                        {
                            "type": "workspace_updated",
                            "workspace": manager.public_workspace(),
                            "line_authors": manager.line_authors,
                            "created_file_id": file_data["id"],
                            "requester_id": client_id,
                        }
                    )
                except HTTPException as exc:
                    await websocket.send_json(
                        {"type": "error", "message": str(exc.detail)}
                    )

            elif message_type == "delete_file":
                if user.get("role") != "admin":
                    await websocket.send_json(
                        {"type": "permission_denied", "message": "Only Admin can close files."}
                    )
                    continue
                try:
                    async with manager.state_lock:
                        manager.delete_file(str(data.get("file_id", "")))
                    await manager.broadcast(
                        {
                            "type": "workspace_updated",
                            "workspace": manager.public_workspace(),
                            "line_authors": manager.line_authors,
                        }
                    )
                except HTTPException as exc:
                    await websocket.send_json(
                        {"type": "error", "message": str(exc.detail)}
                    )

            elif message_type == "cursor_change":
                user["cursor"] = data.get("cursor")
                user["file_id"] = data.get("file_id")
                await manager.broadcast(
                    {
                        "type": "cursor_update",
                        "id": client_id,
                        "account_id": user["account_id"],
                        "username": user["username"],
                        "role": user["role"],
                        "color": user["color"],
                        "cursor": user["cursor"],
                        "file_id": user["file_id"],
                    },
                    exclude=client_id,
                )

            elif message_type == "typing":
                user["is_typing"] = bool(data.get("is_typing", False))
                await manager.broadcast(
                    {
                        "type": "typing_update",
                        "id": client_id,
                        "username": user["username"],
                        "role": user["role"],
                        "is_typing": user["is_typing"],
                    },
                    exclude=client_id,
                )

            elif message_type == "typing_line":
                await manager.broadcast(
                    {
                        "type": "typing_line_update",
                        "id": client_id,
                        "username": user["username"],
                        "role": user["role"],
                        "color": user["color"],
                        "line": int(data.get("line", 0)),
                        "file_id": data.get("file_id"),
                        "is_typing": bool(data.get("is_typing", False)),
                    },
                    exclude=client_id,
                )

            elif message_type == "chat_message":
                text = str(data.get("text", "")).strip()[:MAX_MESSAGE_LENGTH]
                target = str(data.get("target", "group"))
                target_account_id = data.get("target_account_id")
                if not text:
                    continue
                message = {
                    "id": int(time.time() * 1000),
                    "timestamp": time.strftime("%H:%M"),
                    "sender_id": client_id,
                    "sender_account_id": user["account_id"],
                    "sender": user["username"],
                    "sender_role": user["role"],
                    "color": user["color"],
                    "target": target,
                    "target_account_id": target_account_id,
                    "text": text,
                    "read_by": [user["account_id"]],
                }
                manager.add_chat_message(message)
                if target == "group":
                    await manager.broadcast({"type": "chat_message", "message": message})
                elif target_account_id:
                    await manager.send_private_message(
                        client_id,
                        target_account_id,
                        {"type": "chat_message", "message": message},
                    )

            elif message_type == "chat_edit":
                try:
                    async with manager.state_lock:
                        edited_message = manager.edit_chat_message(
                            data.get("message_id"),
                            user,
                            str(data.get("text", "")),
                        )
                    payload = {
                        "type": "chat_message_updated",
                        "message": edited_message,
                    }
                    if edited_message.get("target") == "group":
                        await manager.broadcast(payload)
                    else:
                        await manager.send_to_accounts(
                            [
                                edited_message.get("sender_account_id", ""),
                                edited_message.get("target_account_id", ""),
                            ],
                            payload,
                        )
                except HTTPException as exc:
                    await websocket.send_json(
                        {"type": "error", "message": str(exc.detail)}
                    )

            elif message_type == "chat_delete":
                try:
                    async with manager.state_lock:
                        deleted_message = manager.delete_chat_message(
                            data.get("message_id"),
                            user,
                        )
                    payload = {
                        "type": "chat_message_deleted",
                        "message_id": deleted_message.get("id"),
                    }
                    if deleted_message.get("target") == "group":
                        await manager.broadcast(payload)
                    else:
                        await manager.send_to_accounts(
                            [
                                deleted_message.get("sender_account_id", ""),
                                deleted_message.get("target_account_id", ""),
                            ],
                            payload,
                        )
                except HTTPException as exc:
                    await websocket.send_json(
                        {"type": "error", "message": str(exc.detail)}
                    )

            elif message_type == "mark_read":
                target_account_id = str(data.get("target_account_id", ""))
                manager.mark_chat_read(user["account_id"], target_account_id)
                await websocket.send_json(
                    {
                        "type": "chat_history",
                        "messages": manager.get_chat_history_for_user(user["account_id"]),
                    }
                )

            elif message_type == "code_run_notice":
                await manager.broadcast(
                    {
                        "type": "code_run_notice",
                        "username": user["username"],
                        "role": user["role"],
                        "color": user["color"],
                        "file_id": data.get("file_id"),
                    }
                )

            elif message_type == "code_change":
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Full-document changes are disabled. Use synchronized edits.",
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        disconnected = manager.disconnect(client_id)
        if disconnected and disconnected.get("username"):
            await manager.broadcast(
                {
                    "type": "presence_updated",
                    "active_users": manager.get_active_users(),
                    "claimed_colors": manager.get_claimed_colors(),
                    "guests": manager.public_guests(),
                }
            )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def read_root() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn

    local_ip = get_local_ip()
    print("=" * 60)
    print("🚀 LIVE CODE EDITOR FOR LOCAL WIFI NETWORK")
    print("👉 Local Access:   http://localhost:8000")
    print(f"📡 WiFi/LAN Access: http://{local_ip}:8000")
    print("=" * 60)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
