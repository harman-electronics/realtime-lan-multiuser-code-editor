import {
  BROWSER_PYTHON_VERSION,
  createBrowserPythonRuntime,
  replayBrowserPython,
} from './python-runtime.mjs?v=5.1-python-modes-1';

let runtimePromise = null;
let activeRun = null;
let executing = false;

function getRuntime() {
  if (!runtimePromise) runtimePromise = createBrowserPythonRuntime();
  return runtimePromise;
}

function post(type, payload = {}) {
  self.postMessage({ type, ...payload });
}

async function executeActiveRun() {
  if (!activeRun || executing) return;
  executing = true;
  const started = performance.now();
  try {
    const runtime = await getRuntime();
    if (!activeRun) return;
    post('runtime_ready', {
      runId: activeRun.runId,
      version: BROWSER_PYTHON_VERSION,
    });
    const result = await replayBrowserPython(
      runtime,
      activeRun.code,
      activeRun.inputs,
      activeRun.limits,
    );
    if (!activeRun) return;
    activeRun.waiting = Boolean(result.waiting);
    post('result', {
      runId: activeRun.runId,
      ...result,
      elapsed: (performance.now() - started) / 1000,
    });
    if (!result.waiting) activeRun = null;
  } catch (error) {
    post('fatal', {
      runId: activeRun?.runId || null,
      message: error instanceof Error ? error.message : String(error),
    });
    activeRun = null;
    runtimePromise = null;
  } finally {
    executing = false;
  }
}

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'run') {
    if (activeRun) {
      post('fatal', {
        runId: data.runId || null,
        message: 'A Python program is already running in this browser.',
      });
      return;
    }
    activeRun = {
      runId: String(data.runId || ''),
      code: String(data.code || ''),
      inputs: [],
      inputChars: 0,
      limits: data.limits || {},
      waiting: false,
    };
    post('runtime_loading', {
      runId: activeRun.runId,
      version: BROWSER_PYTHON_VERSION,
    });
    void executeActiveRun();
    return;
  }

  if (data.type === 'input') {
    if (!activeRun || !activeRun.waiting) {
      post('input_error', {
        runId: data.runId || null,
        message: 'The Python program is not waiting for input.',
      });
      return;
    }
    const value = String(data.text ?? '');
    const lineLimit = Number(activeRun.limits.inputLineChars || 4096);
    const totalLimit = Number(activeRun.limits.inputTotalChars || 20000);
    if (value.includes('\n') || value.includes('\r')) {
      post('input_error', {
        runId: activeRun.runId,
        message: 'Send one input line at a time.',
      });
      return;
    }
    if (value.length > lineLimit) {
      post('input_error', {
        runId: activeRun.runId,
        message: `One input line cannot exceed ${lineLimit.toLocaleString()} characters.`,
      });
      return;
    }
    const nextTotal = activeRun.inputChars + value.length + 1;
    if (nextTotal > totalLimit) {
      post('input_error', {
        runId: activeRun.runId,
        message: `Program input cannot exceed ${totalLimit.toLocaleString()} characters per run.`,
      });
      return;
    }
    activeRun.inputs.push(value);
    activeRun.inputChars = nextTotal;
    activeRun.waiting = false;
    void executeActiveRun();
  }
});
