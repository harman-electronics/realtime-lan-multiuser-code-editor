# Real-Time LAN Multiuser Code Editor — Developer Notes

## Overview

This FastAPI and WebSocket application provides a real-time collaborative code
workspace for a trusted class, lab, or small group on the same local network.

- Backend: Python, FastAPI, Uvicorn, WebSockets
- Frontend: HTML, CSS, JavaScript, CodeMirror 5
- Languages: Python and C++ (`g++` or `clang++` is required to compile C++)
- Persistence: JSON files in `data/`
- Default file-tab limit: 6; Admin-configurable maximum: 15
- Per-file Program Input supports Python `input()` and C++ `std::cin`, is limited
  to 20,000 characters, and is saved only in that browser.

## Testing credentials

These credentials are temporary development values:

```text
Admin password: 12345
```

They can be overridden without editing source code:

```text
LIVE_EDITOR_ADMIN_PASSWORD
```

The data directory can also be overridden for isolated testing:

```text
LIVE_EDITOR_DATA_DIR
```

## Login and accounts

### Admin

- Selects the Admin role and enters the Admin password.
- Receives an authenticated server session.
- Can change the displayed Admin name after login.
- Is identified internally by the permanent account ID `admin`.
- Displays a crown after the Admin name.
- Can always edit every code line.

### Guests

- Select the Guest role and enter a full name.
- Choose a cursor colour and send a join request.
- The Admin receives a live notification such as `Bob wants to join`.
- The Guest waits on the login screen until the Admin accepts or rejects the request.
- Accepted requests automatically create or restore the Guest identity and session.
- Rejected and expired requests return a clear message to the Guest.
- Only one active WebSocket session is allowed per approved Guest identity.
- Pending requests expire after 30 minutes.

## Admin settings

The Admin settings dialog contains:

- Admin display-name editor
- Join Requests list with green Accept and red Reject controls
- Approved Guest list with removal controls
- File-tab limit setting
- Global code-access switches

Removing a Guest closes their active connection, revokes their sessions, and
removes their access grants. Historical code authorship and chat messages are kept.
Guests cannot be added manually; every new Guest must be accepted from a join request.

## Multi-file tabs

- Only Admin can create or close files.
- The default limit is six open files, and the Admin can raise it to a maximum of 15.
- Admin may lower the limit while the number of open files is not above the new limit.
- New files require a name and language.
- Python files use `.py`.
- C++ files use `.cpp`.
- Every file has independent code, revision state, and line ownership.
- Users may switch between files independently.

## Code execution

Python files run with the current Python interpreter in isolated interpreter mode.

C++ files are:

1. Written to a temporary directory.
2. Compiled using `g++` or `clang++` with C++17.
3. Executed only when compilation succeeds.
4. Removed with the temporary directory after execution.

If no compiler is available, the output console displays an installation message.
An explicit compiler executable can be configured with `LIVE_EDITOR_CPP_COMPILER`.

Python `input()` values for separate calls must be entered on separate lines.
C++ `std::cin` accepts whitespace-separated values on one or multiple lines.

Important: process timeouts are not a complete security sandbox. Run this
application only on a trusted host and trusted local network.

## Line ownership and access

Each non-empty line stores:

- Permanent owner account ID
- Current display name
- Cursor color

Default rules:

- Admin can edit every line.
- Guests can edit their own lines.
- Blank lines are unclaimed.
- A Guest may grant another Guest access to all lines they own.
- Admin may give a Guest global access to all Guest code.
- Every access switch is off by default.

When a Guest presses Enter on a protected line, the original line is not split or
changed. The server inserts one or more blank lines directly below it. Ownership
indexes are shifted so existing code keeps its owner.

## Presence and cursors

- Remote cursors remain color-coded.
- The floating name bubble above a remote cursor is removed.
- Active-line typing highlights fade automatically.

## Chat

- Group and direct messages use permanent account IDs.
- Guest account IDs keep direct-message identity stable.
- Offline approved Guests remain available in conversation and access lists.
- Direct-message conversations are sorted by latest message.
- Read state is persisted in `chat_history.json`.
- A sender can edit their own message.
- A sender or Admin can delete a message.
- Edits and deletions are persisted and synchronized in real time.

## Appearance and layout

- The workspace, output drawer, chat, and Admin Settings panels are adjustable.
- Light, dark, and automatic themes are available.
- A wallpaper can be saved locally in the current browser using Fill or Fit.
- Dimming, wallpaper visibility, panel blur, adaptive colours, and a blurred
  ambient background can be adjusted without changing shared application data.

## Data files

```text
data/guests.json               Approved Guest identities
data/join_requests.json        Pending and resolved Guest join requests
data/students.json             Legacy student records used once for migration
data/workspace_state.json      Open files, languages, code, revisions, tab limit
data/file_line_authors.json    Per-file line ownership
data/access_control.json       Owner grants and Admin global-access grants
data/chat_history.json         Group and direct messages
data/snapshots.json            File snapshots
data/code_state.json           Legacy single-file state
data/line_authors.json         Legacy single-file ownership
data/users.json                Legacy username configuration
```

The backend writes JSON using temporary files followed by atomic replacement.

## Running the project

Install requirements:

```bash
python -m pip install -r requirements.txt
```

Start the server:

```bash
python app.py
```

Run the permanent isolated suite and the Python/C++ execution matrix:

```bash
python test_app.py
python test_execution_matrix.py
```

Version 4.0 passes 17 permanent tests and 12 execution-matrix cases. Both suites
use temporary directories and do not modify committed collaboration data.
