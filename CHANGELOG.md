# Changelog

All notable changes to the Real-Time LAN Multiuser Code Editor will be recorded
in this file.

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

### Purpose

Version 1 established a working prototype for testing real-time,
multiuser software development over a local network. The prototype provided
the baseline for later Rapid Application Development iterations.

### Credits

- Initial implementation: My lecturer, with the help of an AI coding agent
- Early feature discussions: Me, with feedback from my classmates
