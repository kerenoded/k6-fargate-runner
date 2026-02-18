#!/bin/sh
set -e

echo "RUN_ID=${RUN_ID:-unknown} TARGET_URL=${TARGET_URL:-unknown}"
echo "RESULTS=s3://${RESULTS_BUCKET:-unset}/${RESULTS_KEY:-unset}"

upload_summary() {
  # Upload summary.json if produced by handleSummary
  if [ -n "${RESULTS_BUCKET:-}" ] && [ -n "${RESULTS_KEY:-}" ] && [ -f /tmp/summary.json ]; then
    echo "Uploading /tmp/summary.json to s3://${RESULTS_BUCKET}/${RESULTS_KEY}"
    # Never let upload failures change the container exit code.
    set +e
    python3 /uploader/upload_summary.py
    upload_exit=$?
    set -e
    if [ "${upload_exit}" -ne 0 ]; then
      echo "Upload failed (exitCode=${upload_exit}); continuing" >&2
      return 0
    fi
    echo "Upload complete"
  else
    echo "Skipping upload (missing RESULTS_BUCKET/RESULTS_KEY or /tmp/summary.json not found)"
  fi
}

# Run k6 (ECS passes: run /tests/scenarios/<scenario>.js)
# Upload is attempted only when k6 exits successfully.
k6_exit=0

k6 "$@" &
k6_pid=$!

term_handler() {
  echo "Received termination signal; forwarding to k6 (pid=${k6_pid})"
  kill -TERM "${k6_pid}" 2>/dev/null || true
}

trap term_handler TERM INT

wait "${k6_pid}" || k6_exit=$?

if [ "${k6_exit}" -eq 0 ]; then
  upload_summary
else
  echo "Skipping upload because k6 exited non-zero (exitCode=${k6_exit})"
fi

exit "${k6_exit}"