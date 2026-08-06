# Real-Time LAN Multiuser Code Editor — Developer Notes

## Overview

The Real-Time LAN Multiuser Code Editor is a FastAPI and WebSocket collaboration
application designed for trusted devices connected to the same local network.

- Backend: Python, FastAPI, Uvicorn, WebSockets
- Frontend: HTML, CSS, JavaScript, CodeMirror 5
- Languages: Python and C++ (`g++` or `clang++` is required to compile C++)
- Persistence: JSON files in `data/`
- Default file-tab limit: 6

## Testing credentials

These credentials are temporary development values:

```text
Admin password: 12345
Student password: test1
```

They can be overridden without editing source code:

```text
LIVE_EDITOR_ADMIN_PASSWORD
LIVE_EDITOR_STUDENT_PASSWORD
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

### Students

- Select the Student role.
- Enter Student ID, date of birth, and the shared testing password.
- The saved student name becomes the username automatically.
- Student IDs are unique.
- Dates are stored internally as `YYYY-MM-DD`.
- Only one active WebSocket session is allowed per student.

The seeded development students are:

```text
John Smith — ST001 — 15/06/2005
Bob        — ST002 — 01/01/2005
```

## Admin settings

The Admin settings dialog contains:

- Admin display-name editor
- Add-student form
- Student record list with removal controls
- File-tab limit setting
- Global code-access switches

Removing a student closes their active connection, revokes their sessions, and
removes their access grants. Historical code authorship and chat messages are kept.

## Multi-file tabs

- Only Admin can create or close files.
- The default and maximum limit is six open files.
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

Python and C++ execution accept up to 20,000 characters of standard input.
The frontend stores a separate input value for each file in browser
`localStorage` and sends it with the authenticated `/api/run` request. The
backend supplies that value to the child process through `stdin`. Program input
is not synchronized between users or stored in the server's `data/` directory.

Python is launched using the same interpreter that started the server, with
isolated mode enabled. Standard-library modules and third-party packages
installed into that interpreter's active virtual environment are available.
User-site-only packages, `PYTHONPATH`, local workspace tabs, and project-folder
imports are not available in the current single-file runner. Install trusted
packages from the host terminal, never from student code.

C++ supports the compiler's standard headers. The current single-source compile
command does not provide configurable third-party include paths, library paths,
linker flags, or multi-file builds.

If no compiler is available, the output console displays an installation message.
An explicit compiler executable can be configured with `LIVE_EDITOR_CPP_COMPILER`.

Important: input-size limits and process timeouts are not a complete security
sandbox. Only run this
application on a trusted classroom machine and network.

## Line ownership and access

Each non-empty line stores:

- Permanent owner account ID
- Current display name
- Cursor color

Default rules:

- Admin can edit every line.
- Students can edit their own lines.
- Blank lines are unclaimed.
- A student may grant another student access to all lines they own.
- Admin may give a student global access to all student code.
- Every access switch is off by default.

When a student presses Enter on a protected line, the original line is not split or
changed. The server inserts one or more blank lines directly below it. Ownership
indexes are shifted so existing code keeps its owner.

## Presence and cursors

- Remote cursors remain color-coded.
- The floating name bubble above a remote cursor is removed.
- Admin names include a crown.
- Active-line typing highlights fade automatically.

## Chat

- Group and direct messages use permanent account IDs.
- Student display-name changes do not break direct-message identity.
- Offline students remain available in conversation and access lists.
- Direct-message conversations are sorted by latest message.
- Read state is persisted in `chat_history.json`.
- The original sender may edit or delete a message.
- Admin may delete any message but cannot edit another participant's message.
- Edits and deletions are persisted and broadcast to the affected participants.

## Appearance and layout

- The main workspace uses the full browser area and contains adjustable panels.
- Light, dark, and automatic themes can be applied over a wallpaper.
- Wallpaper image and appearance preferences are saved in the current browser
  only; they are not synchronized or written to the server's `data/` directory.
- Wallpaper layout supports Fill and Fit, including a blurred ambient background
  for fitted images.
- Adaptive colours, dimming, visibility, and panel blur are user-adjustable.
- The Problems tab and controls without implemented actions are removed.

## Data files

```text
data/students.json             Student records
data/workspace_state.json      Open files, languages, code, revisions, tab limit
data/file_line_authors.json    Per-file line ownership
data/access_control.json       Owner grants and Admin global-access grants
data/chat_history.json         Group and direct messages
data/snapshots.json            File snapshots
data/code_state.json           Legacy single-file state
data/line_authors.json         Legacy single-file ownership
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

Run isolated tests:

```cmd
python test_app.py
python test_execution_matrix.py
```

The permanent suite contains 12 isolated tests. The separate execution matrix
contains 12 Python/C++ cases and requires a supported compiler for its C++
checks. Neither suite modifies the committed classroom data.
