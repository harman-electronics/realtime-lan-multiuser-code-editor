import { loadPyodide } from './vendor/pyodide/pyodide.mjs';

export const BROWSER_PYTHON_VERSION = '314.0.5';

const PYODIDE_INDEX_URL = new URL('./vendor/pyodide/', import.meta.url).href;

const PYTHON_RUNNER_SOURCE = String.raw`
import builtins as __live_builtins
import contextlib as __live_contextlib
import json as __live_json
import sys as __live_sys
import traceback as __live_traceback


class __LiveNeedsInput(Exception):
    pass


class __LiveOutputLimit(Exception):
    pass


__live_inputs = __live_json.loads(__live_inputs_json)
__live_events = []
__live_input_index = 0
__live_output_chars = 0


def _live_add_event(stream, text):
    global __live_output_chars
    value = str(text)
    if not value:
        return 0
    if stream != "input":
        remaining = __live_max_output_chars - __live_output_chars
        if remaining <= 0:
            raise __LiveOutputLimit()
        visible = value[:remaining]
        __live_output_chars += len(visible)
    else:
        visible = value
    if __live_events and __live_events[-1]["stream"] == stream:
        __live_events[-1]["text"] += visible
    else:
        __live_events.append({"stream": stream, "text": visible})
    if len(visible) < len(value):
        raise __LiveOutputLimit()
    return len(value)


class __LiveStream:
    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        return _live_add_event(self.stream, text)

    def flush(self):
        return None

    def isatty(self):
        return True


__live_stdout = __LiveStream("stdout")
__live_stderr = __LiveStream("stderr")


def __live_input(prompt=""):
    global __live_input_index
    if prompt:
        __live_stdout.write(prompt)
    if __live_input_index >= len(__live_inputs):
        raise __LiveNeedsInput()
    value = str(__live_inputs[__live_input_index])
    __live_input_index += 1
    _live_add_event("input", f"> {value}\n")
    return value


__live_original_input = __live_builtins.input
_live_blocked_roots = {"js", "pyodide", "_pyodide", "micropip"}
__live_saved_modules = {
    name: module
    for name, module in list(__live_sys.modules.items())
    if name.split(".", 1)[0] in _live_blocked_roots
}


class __LiveBrowserBridgeBlocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in _live_blocked_roots:
            raise ImportError(
                f"Browser bridge module '{fullname}' is unavailable in user code."
            )
        return None


__live_bridge_blocker = __LiveBrowserBridgeBlocker()
__live_waiting = False
__live_status = "completed"
__live_returncode = 0
try:
    __live_builtins.input = __live_input
    for __live_module_name in __live_saved_modules:
        __live_sys.modules.pop(__live_module_name, None)
    __live_sys.meta_path.insert(0, __live_bridge_blocker)
    with __live_contextlib.redirect_stdout(__live_stdout), __live_contextlib.redirect_stderr(__live_stderr):
        __live_namespace = {"__name__": "__main__", "__file__": "<browser-python>"}
        exec(compile(__live_code, "<browser-python>", "exec"), __live_namespace, __live_namespace)
except __LiveNeedsInput:
    __live_waiting = True
    __live_status = "waiting"
except __LiveOutputLimit:
    __live_status = "output_limited"
    __live_returncode = -1
except SystemExit as __live_exit:
    __live_returncode = __live_exit.code if isinstance(__live_exit.code, int) else 0
    if __live_returncode != 0:
        __live_status = "failed"
        __live_stderr.write(f"SystemExit: {__live_exit.code}\n")
except BaseException:
    __live_status = "failed"
    __live_returncode = 1
    __live_traceback.print_exc(file=__live_stderr)
finally:
    __live_builtins.input = __live_original_input
    if __live_bridge_blocker in __live_sys.meta_path:
        __live_sys.meta_path.remove(__live_bridge_blocker)
    __live_sys.modules.update(__live_saved_modules)

__live_result_json = __live_json.dumps({
    "events": __live_events,
    "waiting": __live_waiting,
    "status": __live_status,
    "returncode": __live_returncode,
    "output_chars": __live_output_chars,
})
__live_result_json
`;

export async function createBrowserPythonRuntime() {
  const runningInNode = typeof process === 'object' && Boolean(process.versions?.node);
  return loadPyodide(runningInNode ? {} : { indexURL: PYODIDE_INDEX_URL });
}

export async function replayBrowserPython(runtime, code, inputs, limits = {}) {
  runtime.globals.set('__live_code', String(code || ''));
  runtime.globals.set('__live_inputs_json', JSON.stringify(inputs || []));
  runtime.globals.set(
    '__live_max_output_chars',
    Number(limits.outputChars || 100000),
  );
  const resultJson = await runtime.runPythonAsync(PYTHON_RUNNER_SOURCE);
  return JSON.parse(String(resultJson));
}
