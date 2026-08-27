import assert from 'node:assert/strict';
import {
  BROWSER_PYTHON_VERSION,
  createBrowserPythonRuntime,
  replayBrowserPython,
} from './static/python-runtime.mjs';

const runtime = await createBrowserPythonRuntime();
const passed = [];

async function check(name, test) {
  await test();
  passed.push(name);
  process.stdout.write(`PASS ${String(passed.length).padStart(2, '0')}/8: ${name}\n`);
}

function transcript(result, stream = null) {
  return result.events
    .filter((event) => !stream || event.stream === stream)
    .map((event) => event.text)
    .join('');
}

await check('Browser Python version is pinned', async () => {
  assert.equal(BROWSER_PYTHON_VERSION, '314.0.5');
  assert.match(String(runtime.runPython('import sys; sys.version')), /^3\.14\./);
});

await check('Python output remains inside the browser runtime', async () => {
  const result = await replayBrowserPython(runtime, "print('browser only')", []);
  assert.equal(result.status, 'completed');
  assert.equal(transcript(result, 'stdout').trim(), 'browser only');
});

await check('Python waits for interactive input', async () => {
  const result = await replayBrowserPython(
    runtime,
    "name = input('Name: ')\nprint(f'Hello, {name}!')",
    [],
  );
  assert.equal(result.status, 'waiting');
  assert.equal(transcript(result, 'stdout'), 'Name: ');
});

await check('Python resumes with multiple terminal inputs', async () => {
  const code = [
    "first = int(input('First: '))",
    "second = int(input('Second: '))",
    "print(f'Total: {first + second}')",
  ].join('\n');
  const firstWait = await replayBrowserPython(runtime, code, ['10']);
  assert.equal(firstWait.status, 'waiting');
  const completed = await replayBrowserPython(runtime, code, ['10', '5']);
  assert.equal(completed.status, 'completed');
  assert.match(transcript(completed), /Total: 15/);
});

await check('Loops functions recursion and classes work', async () => {
  const result = await replayBrowserPython(runtime, [
    'def factorial(value):',
    '    return 1 if value <= 1 else value * factorial(value - 1)',
    'class Box:',
    '    def __init__(self, value): self.value = value',
    'total = 0',
    'for number in range(4): total += number',
    'remaining = 2',
    'while remaining: remaining -= 1',
    "print(factorial(5), Box(total).value, remaining)",
  ].join('\n'), []);
  assert.equal(result.status, 'completed');
  assert.equal(transcript(result, 'stdout').trim(), '120 6 0');
});

await check('Python standard-library imports work', async () => {
  const result = await replayBrowserPython(
    runtime,
    "import math\nfrom collections import Counter\nprint(math.isqrt(81), Counter('banana')['a'])",
    [],
  );
  assert.equal(result.status, 'completed');
  assert.equal(transcript(result, 'stdout').trim(), '9 3');
});

await check('Python errors retain source line details', async () => {
  const result = await replayBrowserPython(
    runtime,
    "value = 1\nprint(missing_name)",
    [],
  );
  assert.equal(result.status, 'failed');
  assert.match(transcript(result, 'stderr'), /line 2/);
  assert.match(transcript(result, 'stderr'), /NameError/);
});

await check('Python output and host-process access are restricted', async () => {
  const limited = await replayBrowserPython(
    runtime,
    "print('x' * 200)",
    [],
    { outputChars: 40 },
  );
  assert.equal(limited.status, 'output_limited');
  assert.equal(limited.output_chars, 40);

  const processAttempt = await replayBrowserPython(
    runtime,
    "import subprocess\nsubprocess.run(['cmd', '/c', 'echo', 'unsafe'], check=True)",
    [],
  );
  assert.equal(processAttempt.status, 'failed');
  assert.doesNotMatch(transcript(processAttempt, 'stdout'), /unsafe/i);

  const browserBridgeAttempt = await replayBrowserPython(
    runtime,
    "import js\njs.self.postMessage({'type': 'forged'})",
    [],
  );
  assert.equal(browserBridgeAttempt.status, 'failed');
  assert.match(transcript(browserBridgeAttempt, 'stderr'), /unavailable in user code/);
});

process.stdout.write(`Pyodide ${runtime.version}: ${passed.length}/8 checks passed.\n`);
