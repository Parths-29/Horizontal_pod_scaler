import subprocess
import json
import time
import base64

INSTANCE_ID = "i-04e6c55fc0a27a4eb"
REGION = "us-west-2"

code_bytes = open("load-tests/analyze_results.py", "rb").read()
b64_code = base64.b64encode(code_bytes).decode('ascii')

remote_cmd = f"""
echo '{b64_code}' | base64 -d > /home/ssm-user/Horizontal_pod_scaler/load-tests/analyze_results.py
cd /home/ssm-user/Horizontal_pod_scaler/load-tests && python3 analyze_results.py
cat /home/ssm-user/Horizontal_pod_scaler/docs/benchmark-results.md
"""

params = json.dumps({"commands": [remote_cmd]})

res = subprocess.run([
    "aws", "ssm", "send-command",
    "--instance-ids", INSTANCE_ID,
    "--document-name", "AWS-RunShellScript",
    "--parameters", params,
    "--region", REGION
], capture_output=True, text=True)

if res.returncode != 0:
    print("Error launching SSM:", res.stderr)
    exit(1)

cid = json.loads(res.stdout)["Command"]["CommandId"]
print(f"Sent SSM command: {cid}")

for _ in range(30):
    time.sleep(2)
    inv = subprocess.run([
        "aws", "ssm", "get-command-invocation",
        "--command-id", cid,
        "--instance-id", INSTANCE_ID,
        "--region", REGION
    ], capture_output=True, text=True)
    data = json.loads(inv.stdout)
    status = data.get("Status")
    if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
        out = data.get("StandardOutputContent", "")
        err = data.get("StandardErrorContent", "")
        print(f"Status: {status}")
        if out:
            print("\n--- Output ---")
            print(out)
            lines = out.splitlines()
            # If the first line is the print statement, remove it to save valid markdown
            start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("# Phase 6"):
                    start_idx = i
                    break
            out_md = "\n".join(lines[start_idx:])
            with open("docs/benchmark-results.md", "w", encoding="utf-8") as f:
                f.write(out_md)
            print("Successfully saved docs/benchmark-results.md!")
        if err:
            print("\n--- Error ---")
            print(err)
        break
