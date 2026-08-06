import shutil

from test_app import LiveEditorTestCase


def run_execution_matrix():
    harness = LiveEditorTestCase(methodName="runTest")
    harness.setUp()
    results = []

    def run_program(code, language="python", stdin="", timeout=5):
        token = harness.login_admin()
        response = harness.client.post(
            "/api/run",
            headers=harness.auth_header(token),
            json={
                "code": code,
                "language": language,
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
        check(
            "Python for/while/conditions",
            lambda: _assert_output(
                run_program(
                    "total = 0\n"
                    "for number in range(6):\n"
                    "    if number % 2 == 0: total += number\n"
                    "count = 2\n"
                    "while count: total += 1; count -= 1\n"
                    "print(total)\n"
                ),
                "8",
            ),
        )
        check(
            "Python functions and recursion",
            lambda: _assert_output(
                run_program(
                    "def factorial(value):\n"
                    "    return 1 if value <= 1 else value * factorial(value - 1)\n"
                    "print(factorial(6))\n"
                ),
                "720",
            ),
        )
        check(
            "Python classes and comprehensions",
            lambda: _assert_output(
                run_program(
                    "class Box:\n"
                    "    def __init__(self, value): self.value = value\n"
                    "print([Box(number).value ** 2 for number in range(4)])\n"
                ),
                "[0, 1, 4, 9]",
            ),
        )
        check(
            "Python standard-library imports",
            lambda: _assert_output(
                run_program(
                    "import json, math, statistics\n"
                    "from collections import Counter\n"
                    "print(json.dumps({'root': math.isqrt(81), 'mean': statistics.mean([2, 4]), 'a': Counter('banana')['a']}, sort_keys=True))\n"
                ),
                '{"a": 3, "mean": 3, "root": 9}',
            ),
        )
        check(
            "Installed third-party Python import",
            lambda: _assert_output(
                run_program("import qrcode\nprint(qrcode.__package__)\n"),
                "qrcode",
            ),
        )
        check(
            "Python multiple input and Unicode",
            lambda: _assert_output(
                run_program(
                    "name = input().strip()\n"
                    "first, second = map(int, input().split())\n"
                    "print(f'Kia ora, {name}! {first + second}')\n",
                    stdin="Aroha\n10 5\n",
                ),
                "Kia ora, Aroha! 15",
            ),
        )
        check(
            "Expected Python runtime and syntax errors",
            lambda: _assert_python_errors(run_program),
        )
        check(
            "Python timeout",
            lambda: _assert_timeout(
                run_program("while True:\n    pass\n", timeout=1)
            ),
        )

        compiler = shutil.which("g++") or shutil.which("clang++")
        assert compiler, "The C++ matrix requires g++ or clang++."
        check(
            "C++ functions, loops, and STL",
            lambda: _assert_output(
                run_program(
                    "#include <algorithm>\n#include <iostream>\n#include <vector>\n"
                    "int twice(int value) { return value * 2; }\n"
                    "int main() { std::vector<int> values{3,1,2}; std::sort(values.begin(), values.end()); int total=0; for(int value:values) total+=twice(value); int count=2; while(count){++total;--count;} std::cout<<total; }\n",
                    language="cpp",
                ),
                "14",
            ),
        )
        check(
            "C++ standard input",
            lambda: _assert_output(
                run_program(
                    "#include <iostream>\nint main(){int first=0,second=0;std::cin>>first>>second;std::cout<<first+second;}\n",
                    language="cpp",
                    stdin="20 22\n",
                ),
                "42",
            ),
        )
        check(
            "Expected C++ compile error",
            lambda: _assert_cpp_compile_error(
                run_program(
                    "#include <iostream>\nint main(){ this is not valid C++; }\n",
                    language="cpp",
                )
            ),
        )
        check(
            "C++ timeout",
            lambda: _assert_timeout(
                run_program(
                    "int main(){while(true){}}\n",
                    language="cpp",
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


def _assert_python_errors(run_program):
    runtime_error = run_program("raise ValueError('expected failure')\n")
    assert runtime_error["returncode"] != 0
    assert "ValueError: expected failure" in runtime_error["stderr"]
    syntax_error = run_program("def broken(:\n    pass\n")
    assert syntax_error["returncode"] != 0
    assert "SyntaxError" in syntax_error["stderr"]


def _assert_cpp_compile_error(result):
    assert result["stage"] == "compile"
    assert result["returncode"] != 0
    assert result["stderr"].strip()


def _assert_timeout(result):
    assert result["timed_out"] is True
    assert result["returncode"] == -1


if __name__ == "__main__":
    run_execution_matrix()
