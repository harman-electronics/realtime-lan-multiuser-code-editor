#!/bin/sh

set -u

source_file=/source/main.py
run_timeout=${LIVE_EDITOR_EXECUTION_TIMEOUT:-60}

if [ ! -r "$source_file" ]; then
    echo "Python source file is unavailable inside the execution container." >&2
    exit 2
fi

printf '%s\n' '__WIFI_CODESHARE_PYTHON_READY__' >&2
timeout --signal=TERM --kill-after=1s "${run_timeout}s" \
    python -I -B -u "$source_file"
run_status=$?

if [ "$run_status" -eq 124 ] || [ "$run_status" -eq 137 ]; then
    exit 124
fi

exit "$run_status"
