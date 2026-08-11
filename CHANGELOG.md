# Changelog

All notable changes to the Real-Time LAN Multiuser Code Editor will be recorded
in this file.

## Version 4.2 — Guest Name Validation and Interface Corrections

Version 4.2 adds Guest-name validation and groups three interface corrections
for the Version 4.1 workspace without changing its collaboration or execution
behaviour.

### Added

- Added a live, case-insensitive availability check while a Guest enters their
  name.
- Displayed a green availability message for a valid name and a red **Name
  taken** message when an active participant already uses it.
- Kept **Request to join** disabled while the name is empty, being checked,
  already active, or already attached to a pending join request.
- Rechecked availability on the server when the request is submitted, preventing
  duplicate active names even if two requests are attempted at nearly the same
  time.
- Refreshed the form automatically when participant presence changes, while
  allowing an approved but offline Guest to request access again.

### Fixed and changed

- Fixed the Admin notification shortcut scrolling the entire Settings dialog
  upward and hiding its header and close button.
- Join Requests now scrolls only inside the settings content area while the
  dialog header remains fixed and the close control stays visible.
- Improved the Admin Settings overflow, scrollbar stability, close-button hit
  area, keyboard focus style, and accessible label at compact window sizes.
- Centred the Save Snapshot and Copy Code icons inside stable 42px circular
  hover and click targets.
- Replaced the generic file icon for **Share WiFi connection** with a QR-code
  icon that better represents the action.
- Updated the CSS and JavaScript cache identifiers so upgrading users receive
  the Version 4.2 interface after restarting and pressing `Ctrl+F5`.

### Verification

- Extended the permanent Guest and notification tests with active-name,
  pending-name, server-enforcement, disabled-button, Admin Settings, toolbar
  alignment, and QR-icon regression checks.
- Re-ran all 19 permanent tests and the 12-case Python/C++ execution matrix.
- Captured Version 4.2 screenshots showing the QR-code sharing shortcut and the
  disabled Guest request button with its red active-name warning.

### Main components changed

- `app.py`: Guest-name availability API and request-time enforcement.
- `static/index.html`, `static/app.js`, and `static/style.css`: Guest form
  feedback, button state, presence refresh, interface fixes, and cache update.
- `docs/images/`: Version 4.2 QR-sharing and Guest-validation screenshots.
- `test_app.py`: Version 4.2 regression coverage.

## Version 4.1 — Interactive Input Terminal

Version 4.1 replaces the saved input-before-run workflow with a live terminal
for Python and C++ programs.

### Added and changed

- Added streamed standard output and errors while a program is still running.
- Displayed normal run and completion status messages in yellow, reserving red
  terminal text for genuine errors, timeouts, and limit failures.
- Slightly narrowed the desktop workspace sidebar and its controls to provide
  more horizontal space for code without reducing usability.
- Added a draggable terminal divider with keyboard controls, sensible height
  limits, double-click reset, and per-browser height storage.
- Added a terminal input row that sends one line to the running process when the
  user presses `Enter` or selects **Send**.
- Added a Stop control and automatic process cleanup when the browser
  disconnects, the account logs out, or the server shuts down.
- Limited each account to one running program at a time. Programs execute on the
  host, with a maximum of 20 active runs and four simultaneous C++ compilations.
- Added safeguards of 60 seconds per run, 100,000 output characters, 4,096
  characters per input line, and 20,000 input characters per run.
- Kept Python in unbuffered isolated-interpreter mode so `input()` prompts are
  visible immediately, and kept automatic `g++`/`clang++` C++17 compilation.
- Changed the normal Windows launch from auto-reload mode to one stable Uvicorn
  process so the event loop supports live subprocess pipes. Startup labels now
  use CMD-safe text instead of characters that can fail in legacy encodings.
- Removed the visible per-file Program Input box and its browser storage because
  input is now supplied only when the running program requests it.
- Updated local CSS and JavaScript cache identifiers for Version 4.1. Users
  upgrading from an earlier release should restart the server and press
  `Ctrl+F5`.

### Verification

- Added live WebSocket tests for two separate Python `input()` prompts, C++
  `std::cin` input, streamed results, and stopping a waiting process.
- Expanded the permanent isolated suite to 19 tests; all 19 pass.
- Re-ran the 12-case Python/C++ execution matrix; all 12 cases pass.

### Documentation correction

- Replaced the current README's Version 4.0 screenshot references with genuine
  Version 4.1 captures of the light theme, dark theme, and dark fitted-wallpaper
  interface.
- The new captures show the current Python/C++ tabs, narrower workspace rail,
  interactive terminal, submitted input colours, and yellow completion status.
- Retained the earlier Version 4.0 images in `docs/images/` as historical release
  material; they are no longer presented as the current interface.

### Security note

- Interactive programs still execute on the trusted host without a complete
  security sandbox. Version 4.1 must remain limited to trusted participants on
  a trusted LAN.

## Version 4.0 — Guest Approval and Final Collaboration Workflow

Version 4.0 replaces the registered Student login introduced in Version 2.0
with a live Admin-approved Guest workflow. It includes the complete Version 3.0
interface and appearance system together with all later approved collaboration,
execution, and cleanup changes.

### Guest access and administration

- Replaced Student ID, date-of-birth, and shared-password login with a Guest
  form that asks for a full name and cursor colour.
- Added live join requests and an Admin notification such as
  `Bob wants to join`.
- Added a Join Requests screen in Admin Settings with green Accept and red
  Reject controls.
- Accepted requests automatically create or restore the Guest identity and
  enter the workspace; rejected or expired requests show a clear result.
- Added a 30-minute expiry for unanswered join requests.
- Retained one-active-session enforcement for each approved Guest identity.
- Replaced manual Student creation with an approved Guest list and Admin removal
  controls. Removing a Guest closes active connections, revokes sessions, and
  removes access grants while retaining historical authorship and messages.
- Changed the default Admin password to `12345`. It remains configurable with
  `LIVE_EDITOR_ADMIN_PASSWORD`.

### Workspace, collaboration, and messaging

- Raised the Admin-configurable file-tab maximum from 6 to 15 while retaining a
  clean default limit of 6.
- Retained Python and C++ tabs, persistent line ownership, blank-line insertion,
  per-owner access, Admin global access, snapshots, and real-time synchronization.
- Retained the full-screen adjustable layout, redesigned themes, per-PC
  wallpapers, Fill/Fit, adaptive colours, ambient background, dimming,
  visibility, and panel blur from Version 3.0.
- Retained started-conversation Direct Messages, unread alerts, and synchronized
  Telegram-style message editing and deletion.
- Removed the floating name cloud above remote typing cursors while preserving
  colour-coded cursors and active-line typing highlights.
- Fixed consecutive blank-line ownership so the creator's browser and all other
  clients keep the same owner after repeated Enter presses and continued typing.
- Added immediate local ownership remapping plus an authoritative server
  acknowledgement for each accepted code change, preventing the creator's
  browser from using stale line indexes.
- Kept the unused Problems tab and non-working workspace controls removed.

### Execution and verification

- Retained the corrected per-file Program Input path for Python `input()` and
  C++ `std::cin`, with a 20,000-character limit and per-browser storage.
- Clarified in the interface that separate Python `input()` calls need one value
  per line, while C++ `std::cin` accepts spaces or new lines.
- Retained automatic discovery of `g++` or `clang++`, optional
  `LIVE_EDITOR_CPP_COMPILER`, C++17 compilation, detailed errors, and timeouts.
- Expanded the permanent isolated suite to 17 tests covering Guest approval and
  rejection, live notifications, one active session, Admin removal, 15-tab
  enforcement, permissions, chat editing/deletion, execution, input, errors,
  cursor-label removal and consecutive-line ownership; all 17 tests pass.
- Re-ran the separate 12-case Python/C++ execution matrix covering loops,
  functions, recursion, classes, imports, multiple inputs, Unicode, expected
  errors, timeouts, and real C++ STL compilation; all 12 cases pass.
- Updated local CSS and JavaScript cache identifiers for Version 4.0. Users
  upgrading from an earlier release should restart the server and press
  `Ctrl+F5`.
- Cleaned Guest records, requests, chats, access grants, snapshots, workspace
  code, and legacy Student records from the public release data.

### Security and privacy

- Use Version 4.0 only on a trusted host and trusted LAN; do not expose the
  development server to the public internet.
- Guest names, code, messages, snapshots, authorship, and permissions are stored
  locally as readable JSON and must be cleaned before publishing a used copy.
- The application does not provide HTTPS, university SSO, encrypted storage, or
  a complete execution sandbox. Every participant with code-execution access
  must be trusted.
- Wallpaper images and appearance preferences remain in the participant's local
  browser and are not synchronized through the server.

### Purpose

Version 4.0 makes joining a small trusted collaboration session easier without
requiring the Admin to pre-register personal Student details. The Admin still
controls entry, identity removal, code access, and workspace limits.

## Version 3.0 — Major Interface and Appearance Update

Version 3.0 combines the approved appearance, workspace-navigation, wallpaper,
and messaging improvements into one major interface release. The registered
Admin/Student workflow and collaboration rules from Version 2.0 remain intact.

### Major interface redesign

- Reworked the application into an edge-to-edge, full-screen workspace so the
  available browser area is used without the previous outer margin.
- Added adjustable workspace, terminal, chat, and Admin Settings panels so each
  participant can choose a practical layout for their screen.
- Redesigned the light and dark interfaces with clearer contrast, translucent
  surfaces, improved spacing, and consistent responsive behaviour.
- Consolidated workspace navigation and language-aware file tabs into a cleaner
  visual system without changing their existing collaboration behaviour.
- Kept Python and C++ syntax colours close to the familiar VS Code palette.

### Personal appearance

- Added a per-PC wallpaper system. The selected image and appearance preferences
  are stored only in that browser and are not shared with other participants.
- Added Fill and Fit wallpaper layouts, wallpaper preview, background dimming,
  wallpaper visibility, panel blur, and light, dark, or automatic theme choices.
- Added optional adaptive interface colours derived from the selected wallpaper.
- Added a focused Appearance screen with back navigation instead of permanently
  displaying the full Settings sidebar.
- Added a blurred ambient background for fitted wallpapers so uncovered space
  follows the wallpaper colours instead of becoming a plain white area.

### Messaging and workspace cleanup

- Added Telegram-style edit and delete actions for chat messages.
- Limited message editing to the original sender and message deletion to the
  original sender or Admin, with changes persisted and synchronized in real time.
- Fixed message deletion so it updates both participants in a direct conversation
  and every connected participant in Group Chat.
- Removed the unused Problems tab and controls that had no working action.
- Simplified the workspace controls while preserving Group Chat, Direct Messages,
  unread notifications, snapshots, collaboration, and code execution.

### Retained fixes and verification

- Retained the per-file Program Input box and the corrected Python `input()` and
  C++ `std::cin` execution path, including the 20,000-character input limit.
- Clarified that separate Python `input()` calls require one value per line,
  while C++ `std::cin` accepts values separated by spaces or new lines.
- Updated local CSS and JavaScript cache identifiers for Version 3.0; users
  upgrading from an older release should restart the server and press `Ctrl+F5`.
- Expanded the permanent suite to 12 tests, including chat edit/delete ownership
  and persistence; all 12 tests pass using isolated temporary data.
- Re-ran the separate 12-case Python/C++ execution matrix covering loops,
  functions, recursion, classes, standard and installed imports, multiple input,
  Unicode, expected errors, timeouts, and C++ STL compilation; all 12 cases pass.
- Re-verified a real C++17 compile/run using g++ and a disposable third-party
  Python package installation/import through the authenticated runner.
- Removed the disposable test environment and checked the release data for
  private chats, uploads, student records, paths, tokens, and network addresses.

### Security and privacy

- Use Version 3.0 only on a trusted host computer and trusted LAN; do not expose
  the development server to the public internet.
- Student records, code, messages, snapshots, authorship, and permissions are
  stored locally as readable JSON and must be removed before publishing a
  working classroom copy.
- The application does not provide HTTPS, university SSO, individual password
  hashing, encrypted storage, or a complete execution sandbox.
- Python and C++ programs execute on the host computer, so every participant
  with execution access must be trusted.
- Wallpaper images and appearance preferences remain in the participant's local
  browser and are not synchronized through the server.

### Purpose

Version 3.0 makes the same real-time LAN collaboration system more adaptable and
comfortable for prolonged use while preserving the controlled accounts, code
ownership, permissions, messaging, and execution behaviour introduced earlier.

## Version 2.0 — Registered Accounts, Multi-File Workspace and Messaging

Historical source: saved pre-appearance milestone from 27 July 2026

Version 2.0 combines three originally planned releases: Admin/Student accounts
and the multi-file workspace, resizable Admin Settings, and redesigned direct
messaging.

### Added

- Added separate Admin and Student login flows with show/hide password buttons,
  required fields and clear error messages.
- Added environment-configurable Admin and shared Student testing passwords.
- Added pre-registered student records containing full name, Student ID, date of
  birth, optional information and active state.
- Added Admin controls for adding, removing and viewing student records.
- Added one-active-session enforcement for each Student account.
- Added logout and temporary authenticated HTTP/WebSocket sessions.
- Added Admin display-name editing and a crown role indicator.
- Added a resizable Admin Settings panel.
- Added a persistent multi-file workspace with shared browser-style tabs.
- Added Python `.py` and C++ `.cpp` file creation.
- Added an Admin-configurable file limit with a maximum of six tabs.
- Added per-file language, code, revision and line-ownership persistence.
- Added per-owner **Your Code Access** grants.
- Added Admin-managed global editing grants, disabled by default.
- Added Python execution and C++17 compile/run support on the host.
- Added a per-file **Program Input (stdin)** box for Python `input()` and C++
  `std::cin`, saved locally in each participant's browser.
- Added a 20,000-character program-input limit.
- Added automatic compiler discovery for `g++` and `clang++`.
- Added `LIVE_EDITOR_CPP_COMPILER` for an explicit compatible compiler path.
- Added a started-conversations direct-message list.
- Added a focused conversation view, back navigation and conversation composer.
- Added restored clickable unread direct-message notifications and read state.
- Added isolated automated tests for authentication, accounts, tabs,
  permissions, messaging, snapshots, execution, standard input, error handling,
  and timeouts.
- Added regression coverage for Python imports, `for`/`while`, functions,
  recursion, classes and comprehensions, plus C++ functions, loops and STL
  headers.
- Added real g++ compile/run verification and a 12-case Python/C++ execution
  matrix.
- Added a disposable installation test that installed `humanize 4.16.0` and
  imported it through `/api/run`; the test package was removed afterward.

### Changed and replaced

- Replaced the unauthenticated Lecturer selector with Admin and pre-registered
  Student roles.
- Replaced the Version 1.x PIN-only allowed-username panel with password-gated
  Admin student-record management.
- Replaced the single shared `main.py` document with a multi-file Python/C++
  workspace.
- Replaced the class-wide Restricted/Open Editing mode with per-owner grants
  and Admin-managed global access.
- Replaced the direct-message view that exposed every possible user with a
  sorted list of conversations that have actually been started.
- Replaced the fixed Admin Settings dialog with a user-resizable panel.
- Continued allowing any participant to create blank lines without changing
  another participant's owned content.
- Continued Group Chat as a separate shared conversation.
- Fixed C++ `std::cin` and Python `input()` receiving immediate end-of-input,
  which previously caused missing input or unpredictable program values.
- Changed local CSS and JavaScript URLs to include a Version 2.0 cache
  identifier, preventing upgraded pages from using an older cached runner.
- Documented that installed Python packages work when they are available in the
  server's active environment, while separate workspace tabs cannot yet import
  one another.

### Removed

- Removed anonymous/custom Guest selection from this stage of the history.
- Removed the old allowed-username textarea workflow.
- Removed the unused Version 1.x `data/users.json` file and its obsolete
  username-management PIN.
- Removed the floating name cloud displayed above another user's typing cursor.
- Removed the old class-wide Restricted/Open permission button.

### University and privacy warning

- Student identity must be pre-registered by the lecturer acting as Admin, or
  by a trusted Admin in a small independent study group.
- This is a controlled-enrolment prototype, not official university identity
  authentication or institutional SSO.
- Names, Student IDs, dates of birth, code, chats, snapshots and permissions are
  stored locally as readable JSON on the host computer.
- The application has no cloud synchronization and does not intentionally
  upload these records, but public deployment or publishing a populated `data`
  folder can expose personal information.
- Version 2.0 must be used only on a trusted host and trusted LAN. It must not be
  exposed to the public internet or used with real records in a public repo.
- Python and C++ execution is not a complete security sandbox; every
  participant must be trusted.

### Compiler note

- C++ execution requires g++ or clang++ on the host computer. Connected
  students do not need a compiler on their devices.
- An arbitrary compiler is not automatically supported. The current command
  uses GCC/Clang-style C++17 flags, so Microsoft `cl.exe` requires a future code
  change.

### Purpose

Version 2.0 moves the project from anonymous classroom selection toward a
controlled small-group collaboration model. It associates work with
pre-registered identities, adds shared Python/C++ files and granular access,
and makes direct conversations and administration easier to manage.

## Version 1.2 — Blank-Line Claiming and Permission Modes

Historical source: `fbcbeeef`

### Added

- Added automatic claiming when a participant writes non-empty content on an
  available blank line.
- Added automatic ownership release when an owned line is cleared.
- Added a Restricted mode that preserves per-line creator protection.
- Added an Open Editing mode that lets every participant edit any line.
- Added a global permission button shown to the participant using the Lecturer
  role for switching between the two modes.
- Added live permission-mode synchronization for all connected users.
- Added persistence in `data/permission_mode.json`, using Restricted mode as
  the clean public default.
- Added automated checks for blank-line access, released ownership, both
  permission modes, Lecturer-role control, and WebSocket synchronization.

### Changed

- Empty lines are treated as open workspace rather than owned code.
- Permission checks now allow all edit ranges while Open Editing mode is active.
- The initial WebSocket state now tells each new participant which permission
  mode is active.

### Fixed

- Fixed a historical ownership bug where clearing a line removed its ownership
  and then immediately assigned stale ownership back to the blank line.
- Fixed the permission button remaining hidden after a participant selects the
  Lecturer role by refreshing its visibility when that user joins.
- Invalid permission-mode values now fall back to Restricted mode.

### Historical limitation

- During Version 1.2 pre-release browser execution and testing, we discovered
  that selecting the Lecturer role does not request or verify the Lecturer
  Admin user-management panel PIN. Review confirmed that the same issue existed
  in Versions 1 and 1.1. The PIN protects only the user-management panel, so the
  Lecturer role and its global editing control are not securely authenticated
  in these versions.
- Version 1.2 still inherits Version 1.1's reduced small-screen chat styling.
  Mobile access works over the same LAN, but this iteration is best used with
  the browser's Desktop site mode in landscape orientation.

### Purpose

Version 1.2 lets participants freely create space around one another's work
while allowing a Lecturer to temporarily open the complete document for shared
editing when an exercise requires it.

## Version 1.1 — Line Ownership and Typing Highlights

Historical source: `0cdb1b2`

### Added

- Added persistent creator information for edited lines.
- Added client-side and server-side protection against editing another user's
  owned lines.
- Added Lecturer and Admin overrides for editing any owned line.
- Added a hover tooltip showing who created a line.
- Added synchronized active-line highlights while another user is typing.
- Added a temporary name badge at the end of the active line.
- Added automated checks for ownership rules, permission denial, override
  access, and line-typing events.

### Changed

- Code-delta messages now include the latest line-ownership information.
- Line ownership is saved in `data/line_authors.json`.
- The public repository continues to use clean demonstration code and empty
  chat and snapshot history.

### Fixed

- Removed an obsolete call to the undefined `bindEvents()` function. All event
  listeners were already registered individually, so this removes a browser
  console error without changing application behaviour.

### Historical limitation

- Version 1.1 inherited Version 1's unauthenticated Lecturer-role selection.
  The Lecturer Admin PIN protected only the username-management panel, not the
  Lecturer identity or editing override.
- The original Version 1.1 iteration removed the Version 1 full-screen mobile
  chat media rule while adding the new styling. This historical behaviour is
  preserved here and can be corrected in a later documented iteration.

### Purpose

Version 1.1 reduces accidental overwriting during collaboration by giving each
line a creator and visibly showing where another participant is typing.

## Version 1 — Initial LAN Editor

### Added

- Added a real-time shared Python editor for users on the same LAN.
- Added synchronized presence, cursors, selections, and typing activity.
- Added exclusive cursor-colour selection.
- Added Python execution with a collapsible output console.
- Added group chat, private direct messages, notifications, and unread state.
- Added named snapshots with restore support.
- Added light and dark themes with adjustable editor font size.
- Added LAN address and QR code sharing.
- Added Lecturer controls for managing allowed usernames.
- Added a responsive, resizable chat panel.

### Historical limitation

- The Lecturer role could be selected without authentication. The Lecturer
  Admin PIN protected only the username-management panel. This issue continued
  through Versions 1.1 and 1.2 and was identified during Version 1.2
  pre-release browser execution and testing.

### Purpose

Version 1 established a working prototype for testing real-time,
multiuser software development over a local network. The prototype provided
the baseline for later Rapid Application Development iterations.

### Credits

- Initial implementation: My lecturer, with the help of an AI coding agent
- Early feature discussions: Me, with feedback from my classmates
