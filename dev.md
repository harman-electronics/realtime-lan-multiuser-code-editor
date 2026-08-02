# Project Developer Memory & Tracking (`dev.md`)

This document serves as the persistent memory and architecture log for the **Live WiFi Code Editor** project. It tracks project structure, completed features, design decisions, and planned future enhancements.

---

## 📌 Project Overview

A modern, zero-config real-time collaborative code editor built for classroom environments operating over local WiFi networks (LAN). 

- **Backend**: Python 3 (`FastAPI` + `Uvicorn` + `WebSockets` + `qrcode` + `Pillow`)
- **Frontend**: Glassmorphic UI (`CodeMirror 6` + Vanilla CSS tokens + Lucide Icons)
- **Local Network Support**: Automatic LAN IP detection (`http://192.168.x.x:8000`) and QR Code generation for seamless student joining on mobile devices and laptops.

---

## ✅ Completed Features & History

### 1. Zero-Setup Local Network (LAN) Launcher & QR Code
- Multi-strategy LAN IP detection parsing system interfaces (`ifconfig` / `socket`).
- Integrated base64 QR Code generator modal (`/api/info`) for quick joining over WiFi.
- Uvicorn host binding to `0.0.0.0:8000` to serve all active WiFi/Ethernet network cards.

### 2. Predefined Usernames & Lecturer Admin Control Panel
- Initial Login Modal presented on page load.
- Student username validation against predefined allowed list (`data/users.json`).
- **Lecturer Control Panel**: Modal protected by PIN (`1234`) allowing lecturers to dynamically add, edit, or remove allowed student usernames live during class.

### 3. Username Uniqueness & Guest / Custom Name Support
- **Single-User Name Lock**: Prevents two students from logging in under the same username. Logged-in usernames are disabled in the dropdown as `(Currently Logged In)`.
- **Guest / Custom Name Option**: Students can select `✨ Other / Join as Guest (Type Name)...` to type their custom handle if they are not in the predefined list.

### 4. Exclusive User Color Reservation
- 12-color curated HSL palette (`#FF5722`, `#E91E63`, `#9C27B0`, etc.).
- **Exclusive Lock**: When a user picks a color, it is locked across WebSockets. Other students see a 🔒 lock badge and cannot claim it.
- Color dynamically styles remote cursors, selection overlays, avatar badges, line presence, and typing notifications.

### 5. Real-Time Collaboration & Presence Engine
- WebSocket connection with state synchronization (`init`, `user_joined`, `user_left`, `code_update`, `cursor_update`, `typing_update`).
- Live active student presence counter & avatar group in top header bar.
- Remote multi-cursor bookmark flags with student names.
- Animated "Who is editing live..." typing status banner.

### 6. Live Python Code Execution Runner
- Integrated **"Run Code (Python)"** button executing code securely on the server backend (`/api/run`).
- Interactive collapsible **Execution Output Console** displaying stdout, stderr, execution duration (e.g. `0.02s`), and return codes.

### 7. Themes & Typography Controls
- **Light / Dark Mode**: Dracula Dark glassmorphism and Eclipse Light theme toggle.
- **Font Size Adjuster**: Dynamic font scaling (12px to 28px) with instant CodeMirror re-rendering.

### 8. Revision Snapshots & Version History
- Save labeled code snapshots (e.g. *"Exercise 1 Complete"*).
- History drawer allowing lecturers and students to preview and restore past code snapshots.

### 9. Collapsible Group & Private Chat Sidebar
- **Collapsible Layout**: Glassmorphic right sidebar panel with local storage expanded/collapsed state persistence.
- **Group Classroom Channel**: Public chat room for all connected students and lecturer.
- **Private Direct Messages**: 1-on-1 private DMs between online students with isolated delivery.
- **Unread Badges**: Animated unread counter badge on top navigation bar when sidebar is collapsed.
- **Chat Persistence**: Saves conversation history to `data/chat_history.json`.

### 10. Discord-Style Direct Messaging & Clickable Toast Notifications
- **Clickable Toast Notifications**: Floating glassmorphic notifications popping up when receiving a DM.
- **Word-Count Preview Logic**: Shows full text if 5 words or fewer (`John: My name is Harman`); truncates with `...` if longer (`John: My name is Harman and...`).
- **Interactive Toast Navigation**: Clicking a notification opens the chat sidebar, switches to DM tab, selects the conversation, marks messages as read (`mark_read`), and scrolls to the message.
- **Discord-Style DM Conversation Sidebar**: Dedicated DM conversation list displaying user avatar, color, username, and live **Online (green dot) / Offline (gray dot)** status.
- **Persistent Read/Unread Tracking**: `read_by` array per message in backend and `mark_read` WebSocket handler maintain accurate unread counts across page refreshes.

### 11. Production-Ready Resizable Drag-to-Adjust Side Chat Panel
- **Left Border Drag-to-Resize Handle**: Visible handle on hover (`col-resize` cursor) allowing real-time width adjustment between `320px` and `700px`.
- **Width & State Persistence**: Panel width (`chat_sidebar_width`) and open/closed state (`chat_collapsed`) persist in `localStorage`.
- **Auto-Growing Textarea Input**: Multi-line input expanding up to 120px height (`Enter` to send, `Shift + Enter` for new line).
- **Responsive Mobile Overlay (<768px)**: Converts automatically to a full-screen glassmorphic overlay drawer on mobile screens.
- **Keyboard Shortcuts**: `ESC` key press anywhere closes/collapses the panel smoothly.

### 12. Line/Snippet Ownership & Read-Only Permissions (Option A on Feature Branch)
- **Option A Unclaimed Blank Lines**: Any empty line or line with only spaces is **Unclaimed / Open to All**.
- **Auto-Claiming & Auto-Release**: Typing on a blank line claims ownership. Clearing all text on a line automatically releases the lock.
- **Creator Lock**: Non-empty lines track creator username and assigned color. Other students trying to edit non-empty lines are blocked with a read-only lock.
- **Lecturer Global Permission Control**: Lecturer can toggle between **🔒 Restricted Mode** (default locks) and **🔓 Open Editing Mode** (allows all students to edit any line across the document).
- **Live Broadcast**: Switching permission modes broadcasts `permission_mode_updated` instantly across WebSockets.
- **Creator Hover Tooltip**: Hovering over any line displays a glassmorphic tooltip: `"Created by: <creator's name>"`.

### 13. Real-Time Synchronized Line Typing Highlights (On Feature Branch)
- **20% Opacity Color Highlight**: Typing on a line highlights that entire line in the user's assigned color at 20% opacity (`rgba(color, 0.20)`).
- **End-of-Line Name Badge**: Displays a floating badge with the active user's name at the end of the line (e.g., `Alice ✏️`).
- **Auto-Fade**: Disappears 1.5 seconds after typing stops.
- **WebSocket Synchronization**: Synchronized live across all connected screens with minimal latency.

### 14. Precise Delta Real-Time Text Synchronization
- **CodeMirror Delta Sync (`code_delta`)**: Replaced naive full-document string overwrites with precise range replacement (`editor.replaceRange(text, from, to, 'remote')`).
- **Concurrent Typing Protection**: Multiple students can type simultaneously anywhere in the codebase without deleting or affecting each other's code.

### 15. Verification & Test Suite
- Automated test suite `test_app.py` covering LAN IP detection, API endpoints, Python code execution, snapshots, WebSocket color/name reservation, group chat broadcasting, private DM delivery, read state tracking, line ownership permissions, typing line highlights, and concurrent delta patching.

---

## 📂 Project Architecture & File System

```
live_code_editor/
├── dev.md                   # Project Developer Memory & Tracking
├── app.py                   # FastAPI app, WebSockets router & LAN IP detector
├── requirements.txt         # Dependencies (fastapi, uvicorn, websockets, qrcode, pillow, pydantic)
├── test_app.py              # Automated test suite
├── venv/                    # Isolated Python virtual environment
├── data/
│   ├── users.json           # Allowed usernames & Lecturer Admin PIN
│   ├── code_state.json      # Persisted editor buffer state
│   └── snapshots.json       # Saved document snapshots
└── static/
    ├── index.html           # Main HTML5 application UI
    ├── style.css            # CSS design system (glassmorphism, CSS variables, dark/light themes)
    └── app.js               # Frontend WebSocket client, CodeMirror & UI controller
```

---

## 🔮 Planned Future Enhancements & Roadmap

- [ ] **Multi-File Workspace Support**: Sidebar file tree for managing multiple files (e.g., `main.py`, `helper.py`, `data.csv`).
- [ ] **HTML/CSS/JS Live Web Preview**: Dual-mode runner supporting live HTML/JS rendering alongside Python.
- [ ] **Classroom Diff & Comparison Tool**: Lecturer view to highlight changes made by individual students.
- [ ] **Student Passcode Protection**: Optional password protection for student accounts to prevent impersonation.
- [ ] **Session Package Export**: One-click download of the complete session (code, snapshots, and logs) as a `.zip` archive.

---

## 🛠️ CLI Quick Reference

```bash
# Start the live application server:
./venv/bin/python app.py

# Run the automated test suite:
./venv/bin/python test_app.py
```
