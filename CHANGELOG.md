# Changelog

All notable changes to the Real-Time LAN Multiuser Code Editor will be recorded
in this file.

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
