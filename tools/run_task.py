import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Allow both `python tools/run_task.py` and `python -m tools.run_task`
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.tf_outputs import terraform_outputs

REGION = os.environ.get("AWS_REGION", "eu-west-1")
REPO_ROOT = Path(__file__).resolve().parents[1]
TF_DIR = REPO_ROOT / "infra" / "terraform"

SCENARIO_TO_SCRIPT = {
    "load": "/tests/scenarios/load.js",
}

# Must match terraform awslogs-stream-prefix
STREAM_PREFIX = "run"

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)


def parse_duration_seconds(s: str) -> int:
    m = _DURATION_RE.match(s or "")
    if not m:
        raise SystemExit(f"Invalid duration '{s}'. Use formats like 30s, 2m, 1h, 1d.")
    n = int(m.group(1))
    unit = m.group(2).lower()
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return n * mult


def describe_task(ecs, cluster_arn: str, task_arn: str) -> dict:
    resp = ecs.describe_tasks(cluster=cluster_arn, tasks=[task_arn])
    tasks = resp.get("tasks", [])
    if not tasks:
        raise SystemExit(f"Task not found in describe_tasks: {task_arn}")
    return tasks[0]


def compute_log_stream_name(task_arn: str, stream_prefix: str, container_name: str) -> str:
    task_id = task_arn.split("/")[-1]
    return f"{stream_prefix}/{container_name}/{task_id}"


def tail_stream_incremental(logs, log_group: str, stream_name: str, start_ms: int) -> tuple[int, int]:
    """
    Returns (new_start_ms, printed_count)
    """
    printed = 0
    next_token = None
    last_token = None

    # Paginate a few pages per poll to avoid missing bursts.
    for _ in range(10):
        kwargs = {
            "logGroupName": log_group,
            "logStreamNames": [stream_name],
            "startTime": start_ms,
            "interleaved": True,
        }
        if next_token:
            kwargs["nextToken"] = next_token

        resp = logs.filter_log_events(**kwargs)

        for e in resp.get("events", []):
            ts = datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc).strftime("%H:%M:%S")
            msg = (e.get("message") or "").rstrip("\n")
            if msg:
                print(f"{ts} | {msg}")
                printed += 1
            start_ms = max(start_ms, e["timestamp"] + 1)

        next_token = resp.get("nextToken")
        if not next_token or next_token == last_token:
            break
        last_token = next_token

    return start_ms, printed


def register_task_definition_with_image(ecs, base_task_definition_arn: str, container_name: str, image: str) -> str:
    resp = ecs.describe_task_definition(taskDefinition=base_task_definition_arn)
    td = resp["taskDefinition"]

    container_defs = td.get("containerDefinitions") or []
    found = False
    for c in container_defs:
        if c.get("name") == container_name:
            c["image"] = image
            found = True
            break
    if not found:
        raise SystemExit(f"Container '{container_name}' not found in task definition: {base_task_definition_arn}")

    payload = {
        "family": td["family"],
        "taskRoleArn": td.get("taskRoleArn"),
        "executionRoleArn": td.get("executionRoleArn"),
        "networkMode": td.get("networkMode"),
        "containerDefinitions": container_defs,
        "volumes": td.get("volumes") or [],
        "placementConstraints": td.get("placementConstraints") or [],
        "requiresCompatibilities": td.get("requiresCompatibilities") or [],
        "cpu": td.get("cpu"),
        "memory": td.get("memory"),
        "runtimePlatform": td.get("runtimePlatform"),
        "ephemeralStorage": td.get("ephemeralStorage"),
    }
    # Remove keys with None values (boto3 rejects explicit None)
    payload = {k: v for k, v in payload.items() if v is not None}

    reg = ecs.register_task_definition(**payload)
    return reg["taskDefinition"]["taskDefinitionArn"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=SCENARIO_TO_SCRIPT.keys(), default="load")
    ap.add_argument("--vus", type=int, default=2)
    ap.add_argument("--duration", default="30s")
    ap.add_argument(
        "--sleep-ms",
        type=int,
        default=0,
        help="Sleep (per VU) after each request iteration, in milliseconds (0 disables).",
    )
    ap.add_argument(
        "--request-file",
        dest="request_file_path",
        default=str(REPO_ROOT / "loadtest" / "utils" / "request.json"),
        help="Path to JSON request config (expects fields: url, method, body; optional: headers).",
    )

    ap.add_argument(
        "--warmup-vus",
        type=int,
        default=None,
        help="Warmup VUs for scenario 'load'. Provide with --warmup-duration.",
    )
    ap.add_argument(
        "--warmup-duration",
        default=None,
        help="Warmup duration for scenario 'load' (e.g. 10s, 2m). Provide with --warmup-vus.",
    )

    ap.add_argument("--no-wait", action="store_true", help="Start the ECS task and exit immediately.")
    ap.add_argument("--tail", action="store_true", help="Stream CloudWatch logs while waiting.")
    ap.add_argument("--poll-seconds", type=int, default=5, help="Polling interval while waiting.")
    ap.add_argument(
        "--image-tag",
        default=None,
        help="Optional ECR image tag to run. When provided, a new task definition revision is registered for this run.",
    )
    ap.add_argument(
        "--fetch-and-append",
        action="store_true",
        help="After a successful run (only when waiting), run tools/fetch_and_append.py <RUN_ID>.",
    )
    args = ap.parse_args()

    if args.no_wait and args.fetch_and_append:
        raise SystemExit("--fetch-and-append cannot be used with --no-wait")

    if args.sleep_ms < 0:
        raise SystemExit("--sleep-ms must be >= 0")

    run_id = str(uuid.uuid4())

    request_path = Path(args.request_file_path)
    if not request_path.is_absolute():
        request_path = (REPO_ROOT / request_path).resolve()
    if not request_path.exists():
        raise SystemExit(f"Missing request file: {request_path}")

    try:
        request = json.loads(request_path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {request_path}: {e}")

    url = request.get("url")
    if not url:
        raise SystemExit(f"Missing 'url' in request file: {request_path}")

    headers = request.get("headers")
    if headers is not None:
        if not isinstance(headers, dict):
            raise SystemExit(
                f"Invalid 'headers' in request file: {request_path} (expected an object/map of string->string)"
            )
        for k, v in headers.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SystemExit(
                    f"Invalid 'headers' in request file: {request_path} (expected an object/map of string->string)"
                )

    method = str(request.get("method") or "GET").upper()
    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        raise SystemExit(f"Invalid method '{method}' in request file. Use GET/POST/PUT/DELETE/PATCH")

    body = request.get("body")
    # Allow JSON body as object/array; stringify before passing to ECS env.
    body_str = None
    if body is not None:
        body_str = body if isinstance(body, str) else json.dumps(body)

    # Container can read the request file if it's under loadtest/ (copied to /tests/)
    request_file_in_container = None
    try:
        rel = request_path.resolve().relative_to((REPO_ROOT / "loadtest").resolve())
        request_file_in_container = f"/tests/{rel.as_posix()}"
    except Exception:
        request_file_in_container = None

    if args.scenario != "load" and (args.warmup_vus is not None or args.warmup_duration is not None):
        raise SystemExit("--warmup-vus/--warmup-duration are supported only for --scenario load")

    if args.scenario == "load" and ((args.warmup_vus is None) ^ (args.warmup_duration is None)):
        raise SystemExit("For --scenario load, provide both --warmup-vus and --warmup-duration, or neither.")

    # If request file includes a body for GET/DELETE, k6 script will ignore it.
    if body_str and method in ("GET", "DELETE"):
        print(f"⚠️  Request file includes body with {method}; body will be ignored by the k6 script")

    outs = terraform_outputs(TF_DIR)

    results_bucket = outs["results_bucket_name"]
    results_prefix = outs["results_prefix"]
    results_key = f"{results_prefix}/{run_id}/summary.json"

    ecs = boto3.client("ecs", region_name=REGION)

    env = [
        {"name": "RUN_ID", "value": run_id},
        {"name": "TARGET_URL", "value": url},
        {"name": "MEASURE_VUS", "value": str(args.vus)},
        {"name": "MEASURE_DURATION", "value": args.duration},
        {"name": "SLEEP_MS", "value": str(args.sleep_ms)},
        {"name": "RESULTS_BUCKET", "value": results_bucket},
        {"name": "RESULTS_KEY", "value": results_key},
        # upload_summary.py needs an explicit region to avoid boto3 defaulting to
        # us-east-1 and getting a PermanentRedirect for buckets in other regions.
        {"name": "AWS_DEFAULT_REGION", "value": REGION},
    ]

    if os.environ.get("TARGET_API_KEY"):
        env.append({"name": "TARGET_API_KEY", "value": os.environ["TARGET_API_KEY"]})
    if os.environ.get("TARGET_BEARER_TOKEN"):
        env.append({"name": "TARGET_BEARER_TOKEN", "value": os.environ["TARGET_BEARER_TOKEN"]})

    # Provide request details to k6
    env.append({"name": "REQUEST_METHOD", "value": method})
    if body_str is not None and body_str != "":
        env.append({"name": "REQUEST_BODY", "value": body_str})

    # Provide the file path + JSON as fallback (in case file isn't available in container)
    if request_file_in_container:
        env.append({"name": "REQUEST_FILE_PATH", "value": request_file_in_container})
    env.append({"name": "REQUEST_JSON", "value": json.dumps(request)})

    warmup_seconds = 0
    if args.scenario == "load" and args.warmup_vus is not None:
        env.append({"name": "WARMUP_VUS", "value": str(args.warmup_vus)})
        env.append({"name": "WARMUP_DURATION", "value": args.warmup_duration})
        warmup_seconds = parse_duration_seconds(args.warmup_duration)

    measure_seconds = parse_duration_seconds(args.duration)
    expected_total_seconds = warmup_seconds + measure_seconds

    task_definition_arn = outs["task_definition_arn"]
    if args.image_tag:
        image = f"{outs['ecr_repo_url']}:{args.image_tag}"
        task_definition_arn = register_task_definition_with_image(
            ecs, outs["task_definition_arn"], outs["container_name"], image
        )
        print(f"📦 Using image: {image}")
        print(f"🧾 Task definition revision: {task_definition_arn}")

    resp = ecs.run_task(
        cluster=outs["ecs_cluster_arn"],
        taskDefinition=task_definition_arn,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": outs["public_subnet_ids"],
                "securityGroups": [outs["task_security_group_id"]],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": outs["container_name"],
                    "command": ["run", SCENARIO_TO_SCRIPT[args.scenario]],
                    "environment": env,
                }
            ]
        },
    )

    if resp.get("failures"):
        raise SystemExit(f"RunTask failures: {resp['failures']}")

    task_arn = resp["tasks"][0]["taskArn"]
    container_name = outs["container_name"]
    log_group = outs.get("log_group_name")

    log_stream_name = None
    if log_group:
        log_stream_name = compute_log_stream_name(task_arn, STREAM_PREFIX, container_name)

    print(f"✅ Started task: {task_arn}")
    print(f"🧪 RUN_ID: {run_id}")
    print(f"📦 Results (on success): s3://{results_bucket}/{results_key}")
    if log_stream_name:
        print(f"📜 Log stream: {log_stream_name}")

    if args.no_wait:
        return

    start = time.time()
    last_status = None

    logs_client = None
    tail_start_ms = int(time.time() * 1000)
    printed_any = False

    if args.tail and log_group and log_stream_name:
        logs_client = boto3.client("logs", region_name=REGION)

    while True:
        task = describe_task(ecs, outs["ecs_cluster_arn"], task_arn)
        status = task.get("lastStatus", "UNKNOWN")
        desired = task.get("desiredStatus", "UNKNOWN")

        elapsed = int(time.time() - start)
        est_pct = min(99, int((elapsed / max(1, expected_total_seconds)) * 100))

        if (status, desired) != last_status:
            print(f"⏳ Status: {status} (desired={desired}) | elapsed={elapsed}s | est~{est_pct}%")
            last_status = (status, desired)

        if logs_client and status in ("RUNNING", "DEPROVISIONING", "STOPPED"):
            try:
                tail_start_ms, printed = tail_stream_incremental(
                    logs_client, log_group, log_stream_name, tail_start_ms
                )
                if printed > 0:
                    printed_any = True
                elif not printed_any and status == "RUNNING":
                    # print once so user understands tail is active
                    print("📡 Tailing logs... (no events yet)")
                    printed_any = True
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                # stream might not exist immediately; keep retrying
                if code in ("ResourceNotFoundException", "InvalidParameterException"):
                    pass
                else:
                    raise

        if status == "STOPPED":
            containers = task.get("containers") or []
            exit_code = None
            reason = None
            if containers:
                exit_code = containers[0].get("exitCode")
                reason = containers[0].get("reason")

            print(f"✅ STOPPED | elapsed={elapsed}s | est~100% | exitCode={exit_code} reason={reason}")

            if exit_code not in (0, None):
                raise SystemExit(f"ECS task failed (exitCode={exit_code}). Check CloudWatch logs for details.")

            if args.fetch_and_append:
                script = REPO_ROOT / "tools" / "fetch_and_append.py"
                if not script.exists():
                    raise SystemExit(f"Missing script: {script}")

                cmd = [sys.executable, str(script), run_id]
                print(f"➡️  Running: {' '.join(cmd)}")
                subprocess.run(cmd, check=True)
            return

        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    main()