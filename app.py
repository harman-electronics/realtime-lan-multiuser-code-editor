import os
import sys
import json
import time
import socket
import io
import base64
import subprocess
import asyncio
from typing import Dict, List, Set, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import qrcode

app = FastAPI(title="Live Code Editor")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CODE_FILE = os.path.join(DATA_DIR, "code_state.json")
SNAPSHOTS_FILE = os.path.join(DATA_DIR, "snapshots.json")
CHAT_FILE = os.path.join(DATA_DIR, "chat_history.json")

# Available color palette (12 distinct vibrant colors)
COLOR_PALETTE = [
    "#FF5722", "#E91E63", "#9C27B0", "#673AB7",
    "#3F51B5", "#2196F3", "#00BCD4", "#009688",
    "#4CAF50", "#8BC34A", "#FF9800", "#795548"
]

def load_json(filepath: str, default: Any) -> Any:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath: str, data: Any):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_local_ip() -> str:
    """Detect local WiFi / LAN IP address across all operating systems and network setups."""
    # Strategy 1: Outbound UDP socket to external IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass

    # Strategy 2: Parse system network interfaces (ifconfig / ipconfig)
    try:
        import subprocess
        import re
        res = subprocess.run(["ifconfig"], capture_output=True, text=True)
        matches = re.findall(r'inet\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)', res.stdout)
        if matches:
            return matches[0]
    except Exception:
        pass

    # Strategy 3: Inspect socket hostnames
    try:
        host_name = socket.gethostname()
        for ip in socket.gethostbyname_ex(host_name)[2]:
            if not ip.startswith('127.'):
                return ip
    except Exception:
        pass

    return '127.0.0.1'

def pos_to_offset(code: str, line: int, ch: int) -> int:
    lines = code.split('\n')
    offset = 0
    for i in range(min(line, len(lines))):
        offset += len(lines[i]) + 1
    if line < len(lines):
        offset += min(ch, len(lines[line]))
    return min(offset, len(code))

def apply_delta_to_code(code: str, from_pos: dict, to_pos: dict, text_lines: List[str]) -> str:
    try:
        start_off = pos_to_offset(code, from_pos.get('line', 0), from_pos.get('ch', 0))
        end_off = pos_to_offset(code, to_pos.get('line', 0), to_pos.get('ch', 0))
        replacement = '\n'.join(text_lines)
        return code[:start_off] + replacement + code[end_off:]
    except Exception:
        return code

def generate_qr_code(url: str) -> str:
    """Generate base64 encoded PNG QR Code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1E293B", back_color="#FFFFFF")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

LINE_AUTHORS_FILE = os.path.join(DATA_DIR, "line_authors.json")
PERMISSION_MODE_FILE = os.path.join(DATA_DIR, "permission_mode.json")

# Global State Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # connection_id -> websocket
        self.user_data: Dict[str, Dict[str, Any]] = {}      # connection_id -> {username, color, cursor, selection, is_typing}
        self.code_state: Dict[str, Any] = load_json(CODE_FILE, {
            "code": "# Write code here...\nprint('Hello World!')\n",
            "language": "python"
        })
        self.chat_history: List[Dict[str, Any]] = load_json(CHAT_FILE, [])
        self.line_authors: Dict[str, Dict[str, str]] = load_json(LINE_AUTHORS_FILE, {
            "0": {"author": "Lecturer", "color": "#38BDF8"},
            "1": {"author": "Lecturer", "color": "#38BDF8"}
        })
        self.permission_mode: str = load_json(PERMISSION_MODE_FILE, {"mode": "restricted"}).get("mode", "restricted")

    def set_permission_mode(self, mode: str):
        self.permission_mode = mode
        save_json(PERMISSION_MODE_FILE, {"mode": mode})

    def is_line_empty(self, line_idx: int) -> bool:
        lines = self.code_state["code"].split('\n')
        if 0 <= line_idx < len(lines):
            return lines[line_idx].strip() == ""
        return True

    def can_user_edit_range(self, username: str, start_line: int, end_line: int) -> bool:
        if self.permission_mode == "open":
            return True
        if not username:
            return False
        if username.strip().lower() in ["lecturer", "admin"]:
            return True
        for line_idx in range(start_line, end_line + 1):
            if self.is_line_empty(line_idx):
                continue
            key = str(line_idx)
            if key in self.line_authors:
                author = self.line_authors[key].get("author", "")
                if author and author.strip().lower() != username.strip().lower():
                    return False
        return True

    def record_line_authors(self, start_line: int, num_lines: int, username: str, color: str):
        for i in range(start_line, start_line + num_lines):
            self.line_authors[str(i)] = {"author": username, "color": color}
        save_json(LINE_AUTHORS_FILE, self.line_authors)

    def cleanup_empty_line_authors(self):
        lines = self.code_state["code"].split('\n')
        new_authors = {}
        for i, line_content in enumerate(lines):
            if line_content.strip() != "":
                if str(i) in self.line_authors:
                    new_authors[str(i)] = self.line_authors[str(i)]
        self.line_authors = new_authors
        save_json(LINE_AUTHORS_FILE, self.line_authors)

    def apply_delta(self, from_pos: dict, to_pos: dict, text_lines: List[str], username: str, color: str):
        new_code = apply_delta_to_code(self.code_state["code"], from_pos, to_pos, text_lines)
        self.code_state["code"] = new_code
        save_json(CODE_FILE, self.code_state)

        # Cleanup released empty lines & record line authors for modified non-empty lines
        start_line = from_pos.get('line', 0)
        self.cleanup_empty_line_authors()

        non_empty_lines = [l for l in text_lines if l.strip() != ""]
        if non_empty_lines or len(text_lines) > 0:
            self.record_line_authors(start_line, len(text_lines), username, color)

    def add_chat_message(self, msg: dict):
        self.chat_history.append(msg)
        if len(self.chat_history) > 300:
            self.chat_history = self.chat_history[-300:]
        save_json(CHAT_FILE, self.chat_history)

    def mark_chat_read(self, username: str, target: str):
        if not username or not target:
            return
        user_lower = username.strip().lower()
        target_lower = target.strip().lower()
        updated = False
        for m in self.chat_history:
            m_target = (m.get("target") or "group").lower()
            m_sender = (m.get("sender") or "").lower()
            if (m_target == user_lower and m_sender == target_lower) or (m_target == target_lower and m_sender == user_lower):
                read_by = m.get("read_by", [])
                if username not in read_by:
                    read_by.append(username)
                    m["read_by"] = read_by
                    updated = True
        if updated:
            save_json(CHAT_FILE, self.chat_history)

    def get_chat_history_for_user(self, username: Optional[str]) -> List[Dict[str, Any]]:
        if not username:
            return [m for m in self.chat_history if m.get("target") == "group"]
        user_lower = username.strip().lower()
        filtered = []
        for m in self.chat_history:
            target = (m.get("target") or "group").strip().lower()
            sender = (m.get("sender") or "").strip().lower()
            if target == "group" or target == user_lower or sender == user_lower:
                filtered.append(m)
        return filtered

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.user_data[connection_id] = {
            "id": connection_id,
            "username": None,
            "color": None,
            "cursor": None,
            "selection": None,
            "is_typing": False
        }

    def disconnect(self, connection_id: str) -> Optional[Dict[str, Any]]:
        ws = self.active_connections.pop(connection_id, None)
        u_info = self.user_data.pop(connection_id, None)
        return u_info

    def get_claimed_colors(self) -> Dict[str, str]:
        """Returns dict of color -> username for currently claimed colors."""
        claimed = {}
        for conn_id, u in self.user_data.items():
            if u["color"] and u["username"]:
                claimed[u["color"]] = u["username"]
        return claimed

    def get_active_users(self) -> List[Dict[str, Any]]:
        users = []
        for conn_id, u in self.user_data.items():
            if u["username"]:
                users.append(u)
        return users

    def get_active_usernames(self, exclude_id: Optional[str] = None) -> List[str]:
        """Returns list of active usernames (trimmed)."""
        names = []
        for conn_id, u in self.user_data.items():
            if exclude_id and conn_id == exclude_id:
                continue
            if u.get("username"):
                names.append(u["username"].strip())
        return names

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        msg_str = json.dumps(message)
        for conn_id, ws in list(self.active_connections.items()):
            if exclude and conn_id == exclude:
                continue
            try:
                await ws.send_text(msg_str)
            except Exception:
                pass

    async def send_private_message(self, sender_id: str, recipient_name: str, message: dict):
        msg_str = json.dumps(message)
        rec_lower = recipient_name.strip().lower()
        # Deliver to recipient connection(s)
        for conn_id, u in self.user_data.items():
            if u.get("username") and u["username"].strip().lower() == rec_lower:
                ws = self.active_connections.get(conn_id)
                if ws:
                    try:
                        await ws.send_text(msg_str)
                    except Exception:
                        pass
        # Deliver back to sender connection
        sender_ws = self.active_connections.get(sender_id)
        if sender_ws:
            try:
                await sender_ws.send_text(msg_str)
            except Exception:
                pass

    def update_code(self, new_code: str):
        self.code_state["code"] = new_code
        save_json(CODE_FILE, self.code_state)

manager = ConnectionManager()

# Models
class RunCodeRequest(BaseModel):
    code: str
    timeout: Optional[float] = 5.0

class UserListRequest(BaseModel):
    allowed_users: List[str]
    admin_pin: Optional[str] = None

class SnapshotRequest(BaseModel):
    label: str
    code: str
    author: str

# API Routes
@app.get("/api/info")
def get_info():
    ip = get_local_ip()
    port = 8000
    lan_url = f"http://{ip}:{port}"
    qr_data = generate_qr_code(lan_url)
    users_data = load_json(USERS_FILE, {"allowed_users": [], "admin_pin": "1234"})
    return {
        "ip": ip,
        "port": port,
        "lan_url": lan_url,
        "qr_code": qr_data,
        "palette": COLOR_PALETTE,
        "claimed_colors": manager.get_claimed_colors(),
        "allowed_users": users_data.get("allowed_users", []),
        "active_users": manager.get_active_users()
    }

@app.get("/api/users")
def get_allowed_users():
    users_data = load_json(USERS_FILE, {"allowed_users": [], "admin_pin": "1234"})
    return {
        "allowed_users": users_data.get("allowed_users", []),
        "claimed_colors": manager.get_claimed_colors()
    }

@app.post("/api/users")
async def update_allowed_users(req: UserListRequest):
    users_data = load_json(USERS_FILE, {"allowed_users": [], "admin_pin": "1234"})
    if req.admin_pin and req.admin_pin != users_data.get("admin_pin", "1234"):
        raise HTTPException(status_code=403, detail="Invalid Lecturer Admin PIN")
    
    users_data["allowed_users"] = [u.strip() for u in req.allowed_users if u.strip()]
    save_json(USERS_FILE, users_data)
    
    # Broadcast updated allowed users list to all clients
    await manager.broadcast({
        "type": "allowed_users_updated",
        "allowed_users": users_data["allowed_users"]
    })
    return {"status": "success", "allowed_users": users_data["allowed_users"]}

@app.post("/api/run")
def run_code(req: RunCodeRequest):
    code = req.code
    timeout = min(max(req.timeout or 5.0, 1.0), 10.0) # max 10s
    
    start_time = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = round(time.time() - start_time, 3)
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "elapsed": elapsed,
            "timed_out": False
        }
    except subprocess.TimeoutExpired as e:
        elapsed = round(time.time() - start_time, 3)
        return {
            "stdout": e.stdout or "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "returncode": -1,
            "elapsed": elapsed,
            "timed_out": True
        }
    except Exception as ex:
        elapsed = round(time.time() - start_time, 3)
        return {
            "stdout": "",
            "stderr": str(ex),
            "returncode": -1,
            "elapsed": elapsed,
            "timed_out": False
        }

@app.get("/api/snapshots")
def get_snapshots():
    snapshots = load_json(SNAPSHOTS_FILE, [])
    return {"snapshots": snapshots}

@app.post("/api/snapshots")
async def create_snapshot(req: SnapshotRequest):
    snapshots = load_json(SNAPSHOTS_FILE, [])
    new_snapshot = {
        "id": int(time.time() * 1000),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "label": req.label,
        "code": req.code,
        "author": req.author
    }
    snapshots.insert(0, new_snapshot)
    save_json(SNAPSHOTS_FILE, snapshots)
    
    # Broadcast snapshot notification
    await manager.broadcast({
        "type": "snapshot_created",
        "snapshot": new_snapshot
    })
    return {"status": "success", "snapshot": new_snapshot}

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        # Send initial state
        users_data = load_json(USERS_FILE, {"allowed_users": []})
        await websocket.send_text(json.dumps({
            "type": "init",
            "code": manager.code_state["code"],
            "claimed_colors": manager.get_claimed_colors(),
            "palette": COLOR_PALETTE,
            "allowed_users": users_data.get("allowed_users", []),
            "active_users": manager.get_active_users(),
            "line_authors": manager.line_authors,
            "permission_mode": manager.permission_mode
        }))

        while True:
            data_text = await websocket.receive_text()
            data = json.loads(data_text)
            msg_type = data.get("type")

            if msg_type == "join":
                username = (data.get("username") or "").strip()
                color = data.get("color")

                if not username:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Username cannot be blank."
                    }))
                    continue

                # Enforce Username Uniqueness across active clients
                active_usernames = [u.lower() for u in manager.get_active_usernames(exclude_id=client_id)]
                if username.lower() in active_usernames:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Username '{username}' is already logged in by another student. Only one student can pick each name."
                    }))
                    continue
                
                # Check if color is already claimed by someone else
                claimed = manager.get_claimed_colors()
                if color in claimed and claimed[color] != username:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Color {color} is already selected by {claimed[color]}."
                    }))
                    continue
                
                manager.user_data[client_id]["username"] = username
                manager.user_data[client_id]["color"] = color
                
                # Send chat history for this user
                await websocket.send_text(json.dumps({
                    "type": "chat_history",
                    "messages": manager.get_chat_history_for_user(username)
                }))

                # Broadcast updated presence & color claims
                await manager.broadcast({
                    "type": "user_joined",
                    "user": manager.user_data[client_id],
                    "claimed_colors": manager.get_claimed_colors(),
                    "active_users": manager.get_active_users()
                })

            elif msg_type == "code_delta":
                from_pos = data.get("from")
                to_pos = data.get("to")
                text_lines = data.get("text", [])
                author = manager.user_data[client_id].get("username") or "Guest"
                color = manager.user_data[client_id].get("color") or "#38BDF8"
                
                if from_pos and to_pos and isinstance(text_lines, list):
                    start_line = from_pos.get('line', 0)
                    end_line = to_pos.get('line', 0)
                    
                    if not manager.can_user_edit_range(author, start_line, end_line):
                        await websocket.send_text(json.dumps({
                            "type": "permission_denied",
                            "message": f"Line {start_line + 1} was created by another user and is read-only. Only the creator or Lecturer can edit it."
                        }))
                        continue

                    manager.apply_delta(from_pos, to_pos, text_lines, author, color)
                    await manager.broadcast({
                        "type": "code_delta",
                        "from": from_pos,
                        "to": to_pos,
                        "text": text_lines,
                        "author": author,
                        "color": color,
                        "line_authors": manager.line_authors
                    }, exclude=client_id)

            elif msg_type == "code_change":
                new_code = data.get("code")
                author = manager.user_data[client_id].get("username")
                manager.update_code(new_code)
                await manager.broadcast({
                    "type": "code_update",
                    "code": new_code,
                    "author": author,
                    "color": manager.user_data[client_id].get("color")
                }, exclude=client_id)

            elif msg_type == "cursor_change":
                cursor = data.get("cursor")
                selection = data.get("selection")
                manager.user_data[client_id]["cursor"] = cursor
                manager.user_data[client_id]["selection"] = selection
                await manager.broadcast({
                    "type": "cursor_update",
                    "id": client_id,
                    "username": manager.user_data[client_id].get("username"),
                    "color": manager.user_data[client_id].get("color"),
                    "cursor": cursor,
                    "selection": selection
                }, exclude=client_id)

            elif msg_type == "typing":
                is_typing = data.get("is_typing", False)
                manager.user_data[client_id]["is_typing"] = is_typing
                await manager.broadcast({
                    "type": "typing_update",
                    "id": client_id,
                    "username": manager.user_data[client_id].get("username"),
                    "color": manager.user_data[client_id].get("color"),
                    "is_typing": is_typing
                }, exclude=client_id)

            elif msg_type == "toggle_permission_mode":
                new_mode = data.get("mode", "restricted")
                username = manager.user_data[client_id].get("username")
                if username and (username.strip().lower() in ["lecturer", "admin"] or "lecturer" in username.lower()):
                    manager.set_permission_mode(new_mode)
                    await manager.broadcast({
                        "type": "permission_mode_updated",
                        "permission_mode": manager.permission_mode
                    })

            elif msg_type == "typing_line":
                line = data.get("line", 0)
                is_typing = data.get("is_typing", False)
                await manager.broadcast({
                    "type": "typing_line_update",
                    "id": client_id,
                    "username": manager.user_data[client_id].get("username"),
                    "color": manager.user_data[client_id].get("color"),
                    "line": line,
                    "is_typing": is_typing
                }, exclude=client_id)

            elif msg_type == "chat_message":
                text = (data.get("text") or "").strip()
                target = (data.get("target") or "group").strip()
                username = manager.user_data[client_id].get("username")
                color = manager.user_data[client_id].get("color")
                
                if text and username:
                    msg_obj = {
                        "id": int(time.time() * 1000),
                        "timestamp": time.strftime("%H:%M"),
                        "sender_id": client_id,
                        "sender": username,
                        "color": color,
                        "target": target,
                        "text": text,
                        "read_by": [username]
                    }
                    manager.add_chat_message(msg_obj)
                    if target == "group":
                        await manager.broadcast({
                            "type": "chat_message",
                            "message": msg_obj
                        })
                    else:
                        await manager.send_private_message(client_id, target, {
                            "type": "chat_message",
                            "message": msg_obj
                        })

            elif msg_type == "mark_read":
                target = (data.get("target") or "").strip()
                username = manager.user_data[client_id].get("username")
                if username and target:
                    manager.mark_chat_read(username, target)
                    await websocket.send_text(json.dumps({
                        "type": "chat_history",
                        "messages": manager.get_chat_history_for_user(username)
                    }))

            elif msg_type == "code_run_notice":
                # Broadcast that someone is running code
                await manager.broadcast({
                    "type": "code_run_notice",
                    "username": manager.user_data[client_id].get("username"),
                    "color": manager.user_data[client_id].get("color")
                })

    except WebSocketDisconnect:
        disconnected_user = manager.disconnect(client_id)
        if disconnected_user and disconnected_user.get("username"):
            await manager.broadcast({
                "type": "user_left",
                "id": client_id,
                "user": disconnected_user,
                "claimed_colors": manager.get_claimed_colors(),
                "active_users": manager.get_active_users()
            })

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if __name__ == "__main__":
    import uvicorn
    ip = get_local_ip()
    print("=" * 60)
    print("🚀 LIVE CODE EDITOR FOR LOCAL WIFI NETWORK")
    print(f"👉 Local Access:   http://localhost:8000")
    print(f"📡 WiFi/LAN Access: http://{ip}:8000")
    print("=" * 60)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
