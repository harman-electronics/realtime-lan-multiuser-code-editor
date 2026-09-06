#!/bin/sh

set -u

source_file=/source/main.cpp
output_file=/workspace/program
run_timeout=${LIVE_EDITOR_EXECUTION_TIMEOUT:-60}

if [ ! -r "$source_file" ]; then
    echo "C++ source file is unavailable inside the execution container." >&2
    exit 2
fi

timeout --signal=KILL 15s \
    g++ "$source_file" -std=c++17 -O0 -pipe -o "$output_file"
compile_status=$?

if [ "$compile_status" -eq 124 ] || [ "$compile_status" -eq 137 ]; then
    echo "C++ compilation timed out after 15 seconds." >&2
    exit 124
fi

if [ "$compile_status" -ne 0 ]; then
    exit "$compile_status"
fi

printf '%s\n' '__WIFI_CODESHARE_CPP_READY__' >&2
timeout --signal=TERM --kill-after=1s "${run_timeout}s" "$output_file"
run_status=$?

if [ "$run_status" -eq 124 ] || [ "$run_status" -eq 137 ]; then
    exit 124
fi

exit "$run_status"
