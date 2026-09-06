import shutil
import subprocess
from pathlib import Path

from docker_execution import (
    CPP_CONTAINER_LABEL,
    PYTHON_CONTAINER_LABEL,
    ensure_cpp_docker_ready,
    ensure_python_docker_ready,
)
import app as app_module
from test_app import LiveEditorTestCase


ROOT_DIR = Path(__file__).resolve().parent


def run_execution_matrix():
    harness = LiveEditorTestCase(methodName="runTest")
    harness.setUp()
    results = []

    def run_cpp(code, stdin="", timeout=5):
        token = harness.login_admin()
        response = harness.client.post(
            "/api/run",
            headers=harness.auth_header(token),
            json={
                "code": code,
                "language": "cpp",
                "stdin": stdin,
                "timeout": timeout,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def run_python_docker(code, inputs=None, execution_seconds=None):
        token = harness.login_admin()
        harness.manager.access_control["python_execution_mode"] = "docker"
        original_limit = app_module.MAX_INTERACTIVE_EXECUTION_SECONDS
        if execution_seconds is not None:
            app_module.MAX_INTERACTIVE_EXECUTION_SECONDS = execution_seconds
        try:
            with harness.client.websocket_connect(
                f"/ws/python_matrix_{len(results)}"
            ) as websocket:
                harness.join_admin_websocket(websocket, token)
                websocket.send_json(
                    {
                        "type": "terminal_run",
                        "file_id": "file_main",
                        "code": code,
                    }
                )
                events = []
                sent_input = False
                for _ in range(500):
                    message = websocket.receive_json()
                    events.append(message)
                    if message.get("type") == "terminal_ready" and not sent_input:
                        for value in inputs or []:
                            websocket.send_json({"type": "terminal_input", "text": value})
                        sent_input = True
                    if message.get("type") == "terminal_finished":
                        return {
                            **message,
                            "stdout": "".join(
                                item.get("text", "")
                                for item in events
                                if item.get("type") == "terminal_output"
                                and item.get("stream") == "stdout"
                            ),
                            "stderr": "".join(
                                item.get("text", "")
                                for item in events
                                if item.get("type") == "terminal_output"
                                and item.get("stream") == "stderr"
                            ),
                            "output_limited": any(
                                item.get("type") == "terminal_limit" for item in events
                            ),
                        }
                raise AssertionError("Docker Python did not finish")
        finally:
            app_module.MAX_INTERACTIVE_EXECUTION_SECONDS = original_limit

    def check(name, callback):
        callback()
        results.append(name)
        print(f"PASS {len(results):02d}/26: {name}")

    try:
        node = shutil.which("node")
        assert node, "The browser-Python matrix requires Node.js."
        browser_python = subprocess.run(
            [node, str(ROOT_DIR / "test_browser_python.mjs")],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert browser_python.returncode == 0, (
            browser_python.stdout + browser_python.stderr
        )
        browser_checks = [
            line.split(": ", 1)[1]
            for line in browser_python.stdout.splitlines()
            if line.startswith("PASS ") and ": " in line
        ]
        assert len(browser_checks) == 8, browser_python.stdout
        for name in browser_checks:
            results.append(name)
            print(f"PASS {len(results):02d}/26: {name}")

        docker = ensure_python_docker_ready()
        check(
            "Docker Python functions and loops",
            lambda: _assert_interactive_output(
                run_python_docker(
                    "def twice(value):\n"
                    "    return value * 2\n"
                    "total = 0\n"
                    "for value in [1, 2, 3]:\n"
                    "    total += twice(value)\n"
                    "count = 2\n"
                    "while count:\n"
                    "    total += 1\n"
                    "    count -= 1\n"
                    "print(total)\n"
                ),
                "14",
            ),
        )
        check(
            "Docker Python standard input",
            lambda: _assert_interactive_output(
                run_python_docker(
                    "first = int(input('First: '))\n"
                    "second = int(input('Second: '))\n"
                    "print(first + second)\n",
                    inputs=["20", "22"],
                ),
                "42",
            ),
        )
        check(
            "Docker Python approved libraries",
            lambda: _assert_contains_all(
                run_python_docker(
                    "import numpy as np, pandas as pd, matplotlib, sympy as sp\n"
                    "print(np.array([2, 3]).sum())\n"
                    "print(pd.Series([4, 5]).sum())\n"
                    "print(matplotlib.__version__)\n"
                    "print(sp.factor(42))\n"
                ),
                ["5", "9", "3.11.1", "42"],
            ),
        )
        check(
            "Expected Docker Python runtime error",
            lambda: _assert_python_error(
                run_python_docker("raise ValueError('expected failure')\n")
            ),
        )
        check(
            "Docker Python timeout",
            lambda: _assert_interactive_timeout(
                run_python_docker("while True:\n    pass\n", execution_seconds=1)
            ),
        )
        check(
            "Docker Python uses a non-root user and read-only boundaries",
            lambda: _assert_interactive_output(
                run_python_docker(
                    "import os\n"
                    "def writable(path):\n"
                    "    try:\n"
                    "        with open(path, 'a', encoding='utf-8') as handle: handle.write('x')\n"
                    "        return 1\n"
                    "    except OSError:\n"
                    "        return 0\n"
                    "print(f'uid={os.getuid()};root={writable(\"/escape.txt\")};source={writable(\"/source/main.py\")}')\n"
                ),
                "uid=10001;root=0;source=0",
            ),
        )
        check(
            "Docker Python network access is disabled",
            lambda: _assert_interactive_output(
                run_python_docker(
                    "import socket\n"
                    "sock = socket.socket()\n"
                    "sock.settimeout(1)\n"
                    "try:\n"
                    "    sock.connect(('1.1.1.1', 53))\n"
                    "    print('connected')\n"
                    "except OSError:\n"
                    "    print('blocked')\n"
                    "finally:\n"
                    "    sock.close()\n"
                ),
                "blocked",
            ),
        )
        check(
            "Docker Python output is limited",
            lambda: _assert_interactive_output_limit(
                run_python_docker("print('x' * 120000)\n")
            ),
        )
        check(
            "Docker Python container cleanup and image user",
            lambda: _assert_python_container_cleanup(docker),
        )

        docker = ensure_cpp_docker_ready()
        check(
            "Docker C++ functions loops and STL",
            lambda: _assert_output(
                run_cpp(
                    "#include <algorithm>\n#include <iostream>\n#include <vector>\n"
                    "int twice(int value) { return value * 2; }\n"
                    "int main() { std::vector<int> values{3,1,2}; std::sort(values.begin(), values.end()); int total=0; for(int value:values) total+=twice(value); int count=2; while(count){++total;--count;} std::cout<<total; }\n"
                ),
                "14",
            ),
        )
        check(
            "Docker C++ standard input",
            lambda: _assert_output(
                run_cpp(
                    "#include <iostream>\nint main(){int first=0,second=0;std::cin>>first>>second;std::cout<<first+second;}\n",
                    stdin="20 22\n",
                ),
                "42",
            ),
        )
        check(
            "Expected Docker C++ compile error",
            lambda: _assert_cpp_compile_error(
                run_cpp(
                    "#include <iostream>\nint main(){ this is not valid C++; }\n"
                )
            ),
        )
        check(
            "Docker C++ timeout",
            lambda: _assert_timeout(
                run_cpp(
                    "int main(){while(true){}}\n",
                    timeout=1,
                )
            ),
        )
        check(
            "Docker C++ uses a non-root user and read-only boundaries",
            lambda: _assert_output(
                run_cpp(
                    "#include <fstream>\n#include <iostream>\n#include <unistd.h>\n"
                    "int main(){std::ofstream root(\"/escape.txt\");std::ofstream source(\"/source/main.cpp\",std::ios::app);"
                    "std::cout<<\"uid=\"<<getuid()<<\";root=\"<<root.good()<<\";source=\"<<source.good();}\n"
                ),
                "uid=10001;root=0;source=0",
            ),
        )
        check(
            "Docker C++ network access is disabled",
            lambda: _assert_output(
                run_cpp(
                    "#include <arpa/inet.h>\n#include <iostream>\n#include <sys/socket.h>\n#include <unistd.h>\n"
                    "int main(){int fd=socket(AF_INET,SOCK_STREAM,0);sockaddr_in address{};address.sin_family=AF_INET;"
                    "address.sin_port=htons(53);inet_pton(AF_INET,\"1.1.1.1\",&address.sin_addr);"
                    "int result=connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address));"
                    "std::cout<<(result==0?\"connected\":\"blocked\");if(fd>=0)close(fd);}\n"
                ),
                "blocked",
            ),
        )
        check(
            "Docker C++ output is limited",
            lambda: _assert_output_limit(
                run_cpp(
                    "#include <iostream>\nint main(){for(int i=0;i<120000;++i)std::cout<<'x';}\n"
                )
            ),
        )
        check(
            "Docker C++ container is removed after execution",
            lambda: _assert_no_cpp_containers(docker),
        )
        check(
            "Docker C++ image is configured as non-root",
            lambda: _assert_image_user(docker),
        )
        assert len(results) == 26
        print("Execution matrix: 26/26 passed")
    finally:
        harness.tearDown()


def _assert_output(result, expected):
    assert result["returncode"] == 0, result.get("stderr")
    assert result["stdout"].strip() == expected, result


def _assert_interactive_output(result, expected):
    assert result["status"] == "completed", result
    assert result["stdout"].strip().endswith(expected), result


def _assert_contains_all(result, values):
    assert result["status"] == "completed", result
    for value in values:
        assert value in result["stdout"], result


def _assert_python_error(result):
    assert result["status"] == "failed", result
    assert "ValueError: expected failure" in result["stderr"], result


def _assert_interactive_timeout(result):
    assert result["status"] == "timed_out", result


def _assert_interactive_output_limit(result):
    assert result["status"] == "output_limited", result
    assert result["output_limited"] is True, result
    assert len(result["stdout"]) <= 100_000, len(result["stdout"])


def _assert_cpp_compile_error(result):
    assert result["stage"] == "compile"
    assert result["returncode"] != 0
    assert result["stderr"].strip()


def _assert_timeout(result):
    assert result["timed_out"] is True
    assert result["returncode"] == -1


def _assert_output_limit(result):
    assert result["output_limited"] is True, result
    assert result["returncode"] == -1, result
    assert len(result["stdout"]) <= 100_000, len(result["stdout"])
    assert "Output stopped after 100,000 characters." in result["stderr"]


def _assert_no_cpp_containers(docker):
    process = subprocess.run(
        [
            docker,
            "ps",
            "--all",
            "--filter",
            f"label={CPP_CONTAINER_LABEL}",
            "--format",
            "{{.ID}}",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert not process.stdout.strip(), process.stdout


def _assert_image_user(docker):
    process = subprocess.run(
        [
            docker,
            "image",
            "inspect",
            "wifi-codeshare-cpp-runner:1.0",
            "--format",
            "{{.Config.User}}",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "10001:10001", process.stdout


def _assert_python_container_cleanup(docker):
    process = subprocess.run(
        [
            docker,
            "ps",
            "--all",
            "--filter",
            f"label={PYTHON_CONTAINER_LABEL}",
            "--format",
            "{{.ID}}",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert not process.stdout.strip(), process.stdout
    image = subprocess.run(
        [
            docker,
            "image",
            "inspect",
            "wifi-codeshare-python-runner:1.0",
            "--format",
            "{{.Config.User}}",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert image.returncode == 0, image.stderr
    assert image.stdout.strip() == "10001:10001", image.stdout


if __name__ == "__main__":
    run_execution_matrix()
