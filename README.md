# Real-Time LAN Multiuser Code Editor

A real-time LAN code editor for Python and C++ with collaborative editing,
line ownership, Admin-approved Guest access, chat, appearance controls, and
safer split execution. The Admin can choose whether Python runs inside each
participant's browser or in restricted Docker containers on the Admin host;
browser mode is the default. Admins and approved Guests run C++ in restricted
Docker containers on the Admin host.
Changes, presence, messages, permissions, settings, and file updates are
synchronized in real time.

## Version 5.2 — Guest Docker C++ Execution

Version 5.2 allows approved Guests to select **Compile & Run C++**, enter live
`std::cin` values, stop their own program, and receive compiler/runtime details.
Every C++ program still runs inside a fresh restricted Docker container on the
Admin host. Each account can run one Docker Python or C++ program at a time;
the server tracks at most 20 interactive executions and allows at most four
Docker containers to run concurrently across the classroom.

Input and Stop remain tied to the account and WebSocket connection that started
the program, so one Guest cannot control another Guest's execution. The legacy
Admin compatibility route remains Admin-only; the shared live terminal is the
supported Guest C++ path.

Version 5.1 introduced restricted Docker C++, optional Docker Python, the
Admin-controlled Python mode menu, and optional automatic Guest entry. Browser
Python remains the default. Only the Admin host needs Docker Desktop and WSL 2.

Read the [changelog](CHANGELOG.md) for the complete feature history, detailed
changes, security notes, and previous releases.

> [!WARNING]
> **Use this project only on a trusted host computer and trusted local network.**
> It is intended for a class, lab, or small group working together with or
> without a lecturer. Do not expose the development server to the public
> internet or publish a populated `data` folder. Guest names, code, chats,
> snapshots, ownership, and permissions are stored locally as readable JSON.
> Docker significantly reduces the risk from Python and C++ code, but it is not
> a perfect security boundary. The Admin should keep Docker Desktop updated.
> Approved Guests can start C++ containers on the Admin host. Keep normal Guest
> approval enabled unless everyone with the LAN address can be trusted, and
> review unexpected code or behaviour before allowing further runs.

> [!IMPORTANT]
> This is a collaborative prototype, not production authentication. It does
> not provide HTTPS, university SSO, or encrypted storage. Browser Python stays
> on the participant device; Docker Python and C++ run on the Admin host inside
> restricted containers. Keep the Admin account and LAN trusted and never expose
> the development server to the public internet.

### Admin-controlled Python execution mode (Version 5.1)

![Version 5.1 Admin Python execution mode menu](docs/images/version-5.1-python-mode-menu.png)

### Interactive Docker Python with NumPy

![Version 5.1 Docker Python input and NumPy output](docs/images/version-5.1-docker-python-input.png)

### Automatic Guest entry control

![Version 5.1 Guest entry setting off by default](docs/images/version-5.1-guest-entry-setting.png)

### Guest Docker C++ with live input (Version 5.2)

![Version 5.2 Guest Docker C++ execution with live input](docs/images/version-5.2-guest-cpp-docker-input.png)

The Version 5.1 terminal screenshot shows real `10` and `5` inputs plus Python
and NumPy results from a restricted container. Submitted input is blue,
successful status messages are yellow, and red remains reserved for errors and
limits. The Version 5.2 C++ screenshot shows the same live-input workflow from
an approved Guest account, including the Docker status and successful result.

## Main features

- Live FIFO Admin approval or rejection of Guest join requests from a bell
  popover or Admin Settings
- Optional trusted-LAN Guest auto-join, controlled by the Admin and off by
  default
- Real-time multi-file Python and C++ collaboration over a LAN
- Persistent line ownership, blank-line claiming, and code-access permissions
- Up to 15 Admin-configurable Python and C++ file tabs
- Admin-controlled Browser/Docker Python mode, synchronized for all users
- Browser-side Python 3.14 or restricted Docker Python 3.14 with interactive
  input, output limits, Stop control, and approved libraries in Docker mode
- Admin and approved Guest C++17 execution in disposable restricted Docker
  containers, with live input and per-account ownership
- Group Chat and Direct Messages with unread alerts, editing, and deletion
- One active session per approved Guest and Admin removal controls
- Adjustable full-screen workspace, terminal, chat, and Admin Settings panels
- Light, dark, and automatic themes with local wallpapers, Fill/Fit, adaptive
  colours, panel blur, dimming, visibility, and ambient backgrounds
- LAN address and QR-code sharing for trusted devices

## Quick start

### 1. Create an environment

Windows Command Prompt:

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```cmd
python -m pip install -r requirements.txt
```

### 3. Prepare Docker execution

Install Docker Desktop with its WSL 2 Linux engine on the Admin computer, open
Docker Desktop, and wait for the engine to start. A Docker account is not
required. Then run this once from the project folder:

```cmd
setup-docker.cmd
```

This builds the pinned local `wifi-codeshare-cpp-runner:1.0` and
`wifi-codeshare-python-runner:1.0` images. The editor and Browser Python still
work when Docker is unavailable. Docker Python cannot be selected and C++ Run
shows a clear setup or engine error until Docker is ready.
The Windows launcher also detects current per-user Docker Desktop installations
under `%LOCALAPPDATA%\Programs\DockerDesktop`, even when `docker.exe` is not yet
listed in that CMD window's `PATH`.

On macOS or Linux, build the same image with:

```bash
docker build --pull --tag wifi-codeshare-cpp-runner:1.0 docker/cpp-runner
docker build --pull --tag wifi-codeshare-python-runner:1.0 docker/python-runner
```

### 4. Start the server

```cmd
python app.py
```

Open `http://localhost:8000` on the host. Trusted devices on the same LAN can
open the Wi-Fi address shown in CMD or scan the displayed QR code.

The Python WebAssembly runtime is served locally by this project. The current
interface still loads CodeMirror, Lucide icons, Google Fonts, and QRCode from
public CDNs, so an internet connection is currently needed for the complete
interface on its first load. Fully offline LAN support is not finished yet.

## Demonstration login

1. Select **Admin**, enter password `12345`, and log in.
2. On another browser or device, select **Guest**, enter a fictional full name
   such as `Bob`, choose a cursor colour, and send the request.
3. The Admin receives `Bob wants to join`. Open the bell popover or go to
   **Admin Settings → Join Requests**, then select **Accept** or **Reject**.
   When several Guests are waiting, resolve the oldest request first; the next
   request receives the controls automatically.
4. An accepted Guest enters automatically. Their approved identity is retained
   for future requests, and the Admin can remove it from Settings.

For a trusted private session, the Admin can turn on **Admin Settings → Guest
entry**. The normal queue is used by default. When auto-join is on, waiting
requests are approved and new Guests enter immediately after choosing an
available name and colour. Turn it off again before sharing the address beyond
the intended group.

Only one active connection is allowed for each approved Guest identity.

### Change the Admin password

Set a private password in the same CMD window before starting the server:

```cmd
set "LIVE_EDITOR_ADMIN_PASSWORD=choose-a-new-admin-password"
python app.py
```

This is safer than editing the default value in `app.py` and avoids committing
a personal password to GitHub.

## Choosing and running Python

Python starts in **Runs in this browser** mode. On a Python tab, the Admin can
select the green execution pill and choose **Browser Python** or **Docker
Python**. Guests can see the selected mode but cannot change it. The choice is
saved on the host and synchronized to all connected users.

In Browser mode, each participant runs their own code on their own device. The
first run loads the approximately 13.5 MB local WebAssembly runtime from the
LAN host; later runs reuse the worker while the page remains open. In Docker
mode, every user receives a separate restricted container on the Admin host.
When either mode requests a value, type it in the terminal row and press
`Enter` or select **Send**.

For separate Python `input()` calls, send one value at each prompt:

```text
10
5
```

Entering `10 5` on one line gives the first Python `input()` call the complete
text. The browser worker replays the isolated program with the collected input
values whenever another value is submitted. This supports ordinary learning
programs, loops, functions, and classes, but nondeterministic code may produce
a different earlier value during a replay. Docker Python uses a normal live
stdin stream and does not replay the program. Select **Stop** to end the active
worker or container.

Both modes limit a run to 60 seconds, 100,000 output characters, 4,096
characters per input line, and 20,000 input characters per run. Docker Python
also uses 512 MB RAM, one CPU, 64 processes, a 128 MB temporary workspace, no
network, and read-only root and source mounts.

## Running C++

Admins and approved Guests can select **Compile & Run C++**, submit live
terminal input, and stop the program they started. C++ always runs in a fresh
restricted container on the Admin host; it never runs directly on a Guest
device or as a native host process.

C++ `std::cin` accepts either `10 5` on one line or values on separate lines.
Each run uses a new container with a 60-second execution limit, 100,000 output
characters, 512 MB RAM, one CPU, 64 processes, and a 128 MB temporary
workspace. Each account may have one interactive Docker Python or C++ program
at a time. The server tracks at most 20 interactive executions and allows no
more than four Docker Python/C++ containers to run concurrently. A queued run
uses the same 60-second deadline while waiting for a slot.

## C++ compiler and libraries

C++ compilation happens inside the pinned `gcc:14.2.0-bookworm` Docker image,
not through a compiler installed on Windows. Connected Guests therefore need
neither Docker nor their own compiler. Verify the Admin setup from CMD:

```cmd
docker version
docker image inspect wifi-codeshare-cpp-runner:1.0
```

To rebuild the execution image after changing its Dockerfile or runner:

```cmd
setup-docker.cmd
```

Standard GCC headers such as `<iostream>`, `<vector>`, `<algorithm>`, and
`<string>` are available inside the image. Microsoft `cl.exe` is not used.

> [!IMPORTANT]
> Third-party C++ libraries that need extra include paths, library paths,
> linker flags, or multi-file builds are not automatically supported. The
> current image compiles one source file with fixed GCC C++17 options. Extra
> libraries should be added to a reviewed custom Docker image, never installed
> directly in response to code submitted by a user.

## Python libraries

Python standard-library imports work inside the browser runtime, including
modules such as `math`, `json`, `statistics`, and `collections`. Packages
installed in the host virtual environment are intentionally **not** visible to
browser Python. Third-party Pyodide package files are not bundled yet, and
separate Python workspace tabs cannot currently import one another.

Docker Python includes the standard library plus the reviewed, pinned packages
`numpy==2.5.2`, `pandas==3.0.5`, `matplotlib==3.11.1`, and `sympy==1.14.0`.
Matplotlib can calculate and save output in the temporary workspace, but the
container does not open desktop windows. Arbitrary `pip install` is not
available during a run because the container network is disabled. Add more
packages only by reviewing and rebuilding `docker/python-runner/Dockerfile`.

## Testing

Version 5.2 passes **29/29 permanent automated tests** and **26/26 execution-
matrix checks**. Eight matrix checks exercise the real pinned Pyodide engine,
nine exercise Docker Python, and nine exercise Docker C++. The matrix covers
input, functions, loops, approved Python libraries, compiler/runtime errors,
timeouts, non-root execution, read-only boundaries, disabled network, output
limits, cleanup, and image identity. Interactive integration tests also verify
real Guest C++ input, container restrictions, one run per account, and
connection-owned input and Stop controls.

```cmd
python test_app.py
python test_execution_matrix.py
node test_browser_python.mjs
```

The server tests use isolated temporary data and do not modify committed
records. The Node check loads the same local WebAssembly runtime used by the
browser and does not start the application server.

## Stopping, upgrading, and mobile access

Stop the server by returning to CMD and pressing `Ctrl+C`. Persistent changes
are normally saved when they happen; live connections, cursors, typing state,
and login sessions end when the server stops.

After upgrading, restart the server and hard-refresh the browser with `Ctrl+F5`
(Windows/Linux) or `Cmd+Shift+R` (macOS).

Phones on the same trusted Wi-Fi can use the LAN address or QR code. Do not use
`localhost` on a phone. Mobile support remains experimental; landscape
orientation and **Desktop site** mode usually provide a better layout.

## Project structure

```text
.
├── app.py
├── docker_execution.py       # Fixed restricted Docker execution policy
├── requirements.txt
├── setup-docker.cmd          # One-time Windows Docker images setup
├── test_app.py
├── test_browser_python.mjs
├── test_execution_matrix.py
├── data/                    # Local JSON workspace and collaboration state
├── docker/
│   ├── cpp-runner/          # Pinned GCC image and non-root runner
│   └── python-runner/       # Pinned Python image and approved libraries
├── docs/
│   └── images/             # Release screenshots
└── static/
    ├── python-runtime.mjs   # Browser Python execution and input replay
    ├── python-worker.mjs    # Disposable Web Worker controller
    └── vendor/pyodide/      # Pinned local Pyodide 314.0.5 runtime
```

## Technology

Python, FastAPI, Uvicorn, WebSockets, HTML, CSS, JavaScript, CodeMirror 5,
Pyodide 314.0.5, WebAssembly, Web Workers, Lucide icons, QRCode, Pillow,
Docker-isolated Python 3.14 with pinned scientific packages, and a
Docker-isolated GCC 14.2 C++17 runner.

## Credits

The project began as a Rapid Application Development demonstration. Its
features developed through classroom discussion, feedback, implementation,
and repeated testing.

## Licence

No open-source licence has been selected. Reuse or redistribution requires
permission from the respective contributors. The vendored Pyodide runtime is
separately licensed under the Mozilla Public License 2.0; its licence is kept
in `static/vendor/pyodide/LICENSE`.
