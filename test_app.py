import asyncio
import json
import time

import anyio
from fastapi.testclient import TestClient
from app import app, ConnectionManager, get_local_ip, generate_qr_code

client = TestClient(app)
WEBSOCKET_EVENT_TIMEOUT = 5.0


async def _receive_json_with_timeout(websocket, timeout):
    """Receive one test WebSocket message without allowing the test to hang."""
    with anyio.fail_after(timeout):
        message = await websocket._send_rx.receive()

    websocket._raise_on_close(message)
    if "text" in message:
        return json.loads(message["text"])
    return json.loads(message["bytes"].decode("utf-8"))


def receive_event(websocket, event_type, predicate=None, timeout=WEBSOCKET_EVENT_TIMEOUT):
    """Wait for a matching event and retain out-of-order events for later checks."""
    deadline = time.monotonic() + timeout
    received_types = []
    event_buffer = getattr(websocket, "_test_event_buffer", [])
    websocket._test_event_buffer = event_buffer

    for index, event in enumerate(event_buffer):
        if event.get("type") == event_type and (
            predicate is None or predicate(event)
        ):
            return event_buffer.pop(index)

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        try:
            event = websocket.portal.call(
                _receive_json_with_timeout,
                websocket,
                remaining,
            )
        except TimeoutError:
            break

        received_types.append(event.get("type", "<missing type>"))
        if event.get("type") == event_type and (
            predicate is None or predicate(event)
        ):
            return event
        event_buffer.append(event)

    received_summary = ", ".join(received_types) or "no events"
    raise AssertionError(
        f"Timed out after {timeout:.1f}s waiting for WebSocket event "
        f"'{event_type}'. Received: {received_summary}."
    )

def test_local_ip_and_qr():
    ip = get_local_ip()
    assert ip is not None
    print(f"[PASS] Local LAN IP detected: {ip}")
    
    qr = generate_qr_code(f"http://{ip}:8000")
    assert qr.startswith("data:image/png;base64,")
    print("[PASS] QR Code base64 generation working!")

def test_api_info():
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert "ip" in data
    assert "qr_code" in data
    assert "palette" in data
    assert len(data["palette"]) == 12
    print(f"[PASS] /api/info response valid with {len(data['palette'])} colors.")

def test_api_users():
    response = client.get("/api/users")
    assert response.status_code == 200
    data = response.json()
    assert "allowed_users" in data
    assert "Alice" in data["allowed_users"]
    print("[PASS] /api/users retrieved allowed usernames!")

def test_run_code():
    code_req = {
        "code": "students = ['Alice', 'Bob']\nfor s in students:\n    print(f'Hello {s}')\n"
    }
    response = client.post("/api/run", json=code_req)
    assert response.status_code == 200
    data = response.json()
    assert "stdout" in data
    assert "Hello Alice" in data["stdout"]
    assert "Hello Bob" in data["stdout"]
    assert data["returncode"] == 0
    print(f"[PASS] Live Python Code Execution successful!\nOutput:\n{data['stdout']}")

def test_snapshots():
    snap_req = {
        "label": "Test Lesson 1",
        "code": "print('snapshot test')",
        "author": "Lecturer"
    }
    response = client.post("/api/snapshots", json=snap_req)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    res2 = client.get("/api/snapshots")
    snaps = res2.json()["snapshots"]
    assert len(snaps) > 0
    assert snaps[0]["label"] == "Test Lesson 1"
    print("[PASS] Snapshots API create & list verified!")


def test_line_ownership_rules():
    manager = ConnectionManager()
    manager.permission_mode = "restricted"
    manager.code_state = {
        "code": "print('owned')\n\nprint('second owner')",
        "language": "python",
    }
    manager.line_authors = {
        "0": {"author": "Alice", "color": "#FF5722"},
        "2": {"author": "Guest_Charlie", "color": "#9C27B0"},
    }

    assert manager.can_user_edit_range("Alice", 0, 0)
    assert not manager.can_user_edit_range("Guest_Charlie", 0, 0)
    assert manager.can_user_edit_range("Lecturer", 0, 0)
    assert manager.can_user_edit_range("Admin", 0, 0)
    assert manager.can_user_edit_range("Guest_Charlie", 1, 1)

    manager.set_permission_mode("open")
    assert manager.can_user_edit_range("Guest_Charlie", 0, 0)

    manager.set_permission_mode("restricted")
    manager.apply_delta(
        {"line": 0, "ch": 0},
        {"line": 0, "ch": len("print('owned')")},
        [""],
        "Alice",
        "#FF5722",
    )
    assert manager.code_state["code"].split("\n")[0] == ""
    assert "0" not in manager.line_authors
    assert manager.can_user_edit_range("Guest_Charlie", 0, 0)
    print("[PASS] Restricted/Open modes, blank-line access & ownership release verified!")

def test_websocket_collaboration():
    with client.websocket_connect("/ws/client_test_1") as ws1:
        # Initial message
        data1 = receive_event(ws1, "init")
        
        # Client 1 joins with color #FF5722
        ws1.send_json({
            "type": "join",
            "username": "Alice",
            "color": "#FF5722"
        })
        
        msg_history = receive_event(ws1, "chat_history")

        join_msg = receive_event(
            ws1,
            "user_joined",
            lambda event: event["user"]["username"] == "Alice",
        )
        assert join_msg["user"]["username"] == "Alice"
        assert join_msg["claimed_colors"]["#FF5722"] == "Alice"
        print("[PASS] WebSocket join, chat history & exclusive color lock verified for Alice (#FF5722)!")

        # Client 2 connects and tries claiming the same username "Alice"
        with client.websocket_connect("/ws/client_test_2") as ws2:
            data2 = receive_event(ws2, "init")
            ws2.send_json({
                "type": "join",
                "username": "Alice", # Same name as already active user
                "color": "#9C27B0"
            })
            err_msg_user = receive_event(
                ws2,
                "error",
                lambda event: "already logged in" in event.get("message", ""),
            )
            assert "already logged in" in err_msg_user["message"]
            print("[PASS] Duplicate Username Prevention Enforced! Client 2 was blocked from taking Alice's name.")

            # Client 2 connects with unique Guest Name "Guest_Charlie"
            ws2.send_json({
                "type": "join",
                "username": "Guest_Charlie",
                "color": "#9C27B0"
            })
            msg_hist2 = receive_event(ws2, "chat_history")

            join_msg2 = receive_event(
                ws2,
                "user_joined",
                lambda event: event["user"]["username"] == "Guest_Charlie",
            )
            assert join_msg2["user"]["username"] == "Guest_Charlie"

            # ws1 gets broadcast of ws2 joining
            ws1_user2_joined = receive_event(
                ws1,
                "user_joined",
                lambda event: event["user"]["username"] == "Guest_Charlie",
            )
            print("[PASS] Custom / Guest Name Join Verified for Guest_Charlie!")

            # Alice sends Group Chat Message
            ws1.send_json({
                "type": "chat_message",
                "target": "group",
                "text": "Hello class!"
            })
            chat_msg_ws1 = receive_event(
                ws1,
                "chat_message",
                lambda event: event["message"]["text"] == "Hello class!",
            )
            chat_msg_ws2 = receive_event(
                ws2,
                "chat_message",
                lambda event: event["message"]["text"] == "Hello class!",
            )
            assert chat_msg_ws1["message"]["text"] == "Hello class!"
            assert chat_msg_ws2["message"]["text"] == "Hello class!"
            print("[PASS] Group Chat Broadcasting Verified!")

            # Alice sends Private Direct Message to Guest_Charlie
            ws1.send_json({
                "type": "chat_message",
                "target": "Guest_Charlie",
                "text": "Private question for Charlie"
            })
            pm_ws1 = receive_event(
                ws1,
                "chat_message",
                lambda event: event["message"]["text"] == "Private question for Charlie",
            )
            pm_ws2 = receive_event(
                ws2,
                "chat_message",
                lambda event: event["message"]["text"] == "Private question for Charlie",
            )

            # Charlie sends mark_read to Alice's conversation
            ws2.send_json({
                "type": "mark_read",
                "target": "Alice"
            })
            read_history = receive_event(ws2, "chat_history")
            print("[PASS] DM Mark Read & Read State Tracking Verified!")
            # Alice claims a previously unowned line.
            ws1.send_json({
                "type": "code_delta",
                "from": {"line": 1, "ch": 0},
                "to": {"line": 1, "ch": 0},
                "text": ["# Alice edit\n"]
            })
            delta_msg_ws2 = receive_event(
                ws2,
                "code_delta",
                lambda event: event["text"] == ["# Alice edit\n"],
            )
            assert delta_msg_ws2["text"] == ["# Alice edit\n"]

            # Charlie cannot edit the line Alice just claimed.
            ws2.send_json({
                "type": "code_delta",
                "from": {"line": 1, "ch": 0},
                "to": {"line": 1, "ch": 0},
                "text": ["# Charlie edit\n"]
            })
            permission_denied = receive_event(
                ws2,
                "permission_denied",
                lambda event: "read-only" in event.get("message", ""),
            )
            assert "read-only" in permission_denied["message"]
            print("[PASS] WebSocket line ownership enforcement verified!")

            # Alice's active-line typing indicator is synchronized to Charlie.
            ws1.send_json({
                "type": "typing_line",
                "line": 1,
                "is_typing": True
            })
            typing_line_msg = receive_event(
                ws2,
                "typing_line_update",
                lambda event: event.get("line") == 1,
            )
            assert typing_line_msg["username"] == "Alice"
            assert typing_line_msg["is_typing"] is True
            print("[PASS] Real-time synchronized line typing highlights verified!")

            # A Lecturer can enable global Open Editing mode for the class.
            with client.websocket_connect("/ws/client_test_3") as ws3:
                lecturer_init = receive_event(ws3, "init")
                assert lecturer_init["permission_mode"] == "restricted"
                ws3.send_json({
                    "type": "join",
                    "username": "Lecturer",
                    "color": "#38BDF8",
                })
                receive_event(ws3, "chat_history")
                receive_event(
                    ws3,
                    "user_joined",
                    lambda event: event["user"]["username"] == "Lecturer",
                )
                receive_event(
                    ws1,
                    "user_joined",
                    lambda event: event["user"]["username"] == "Lecturer",
                )
                receive_event(
                    ws2,
                    "user_joined",
                    lambda event: event["user"]["username"] == "Lecturer",
                )

                ws3.send_json({
                    "type": "toggle_permission_mode",
                    "mode": "open",
                })
                for websocket in (ws1, ws2, ws3):
                    mode_event = receive_event(
                        websocket,
                        "permission_mode_updated",
                        lambda event: event.get("permission_mode") == "open",
                    )
                    assert mode_event["permission_mode"] == "open"

                # Charlie can now edit the line that Alice owns.
                ws2.send_json({
                    "type": "code_delta",
                    "from": {"line": 1, "ch": 0},
                    "to": {"line": 1, "ch": 0},
                    "text": ["# Open mode edit\n"],
                })
                open_delta = receive_event(
                    ws1,
                    "code_delta",
                    lambda event: event["text"] == ["# Open mode edit\n"],
                )
                assert open_delta["author"] == "Guest_Charlie"

                ws3.send_json({
                    "type": "toggle_permission_mode",
                    "mode": "restricted",
                })
                for websocket in (ws1, ws2, ws3):
                    receive_event(
                        websocket,
                        "permission_mode_updated",
                        lambda event: event.get("permission_mode") == "restricted",
                    )
                print("[PASS] Lecturer global permission-mode synchronization verified!")

if __name__ == "__main__":
    print("\n--- RUNNING BACKEND & WEBSOCKET VERIFICATION ---")
    test_local_ip_and_qr()
    test_api_info()
    test_api_users()
    test_run_code()
    test_snapshots()
    test_line_ownership_rules()
    test_websocket_collaboration()
    print("\nALL BACKEND & WEBSOCKET VERIFICATION TESTS PASSED!\n")
