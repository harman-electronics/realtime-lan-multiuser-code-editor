# Changelog

All notable changes to the Real-Time LAN Multiuser Code Editor will be recorded
in this file.

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
