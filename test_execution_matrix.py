import shutil
import subprocess
from pathlib import Path

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

    def check(name, callback):
        callback()
        results.append(name)
        print(f"PASS {len(results):02d}/12: {name}")

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
            print(f"PASS {len(results):02d}/12: {name}")

        compiler = shutil.which("g++") or shutil.which("clang++")
        assert compiler, "The C++ matrix requires g++ or clang++."
        check(
            "Admin C++ functions loops and STL",
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
            "Admin C++ standard input",
            lambda: _assert_output(
                run_cpp(
                    "#include <iostream>\nint main(){int first=0,second=0;std::cin>>first>>second;std::cout<<first+second;}\n",
                    stdin="20 22\n",
                ),
                "42",
            ),
        )
        check(
            "Expected Admin C++ compile error",
            lambda: _assert_cpp_compile_error(
                run_cpp(
                    "#include <iostream>\nint main(){ this is not valid C++; }\n"
                )
            ),
        )
        check(
            "Admin C++ timeout",
            lambda: _assert_timeout(
                run_cpp(
                    "int main(){while(true){}}\n",
                    timeout=1,
                )
            ),
        )
        assert len(results) == 12
        print("Execution matrix: 12/12 passed")
    finally:
        harness.tearDown()


def _assert_output(result, expected):
    assert result["returncode"] == 0, result.get("stderr")
    assert result["stdout"].strip() == expected, result


def _assert_cpp_compile_error(result):
    assert result["stage"] == "compile"
    assert result["returncode"] != 0
    assert result["stderr"].strip()


def _assert_timeout(result):
    assert result["timed_out"] is True
    assert result["returncode"] == -1


if __name__ == "__main__":
    run_execution_matrix()
