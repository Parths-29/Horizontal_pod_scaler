import subprocess
import json
import time
import base64

INSTANCE_ID = "i-04e6c55fc0a27a4eb"
REGION = "us-west-2"

params = json.dumps({"commands": ["base64 -w 0 /home/ssm-user/Horizontal_pod_scaler/docs/benchmark-results.md"]})

res = subprocess.run([
    "aws", "ssm", "send-command",
    "--instance-ids", INSTANCE_ID,
    "--document-name", "AWS-RunShellScript",
    "--parameters", params,
    "--region", REGION
], capture_output=True, text=True)

cid = json.loads(res.stdout)["Command"]["CommandId"]

time.sleep(3)

inv = subprocess.run([
    "aws", "ssm", "get-command-invocation",
    "--command-id", cid,
    "--instance-id", INSTANCE_ID,
    "--region", REGION
], capture_output=True, text=True)

data = json.loads(inv.stdout)
b64_str = data.get("StandardOutputContent", "").strip()
content = base64.b64decode(b64_str).decode("utf-8")

print("Fetched benchmark-results.md content:")
print("=" * 60)
print(content)
print("=" * 60)

with open("docs/benchmark-results.md", "w", encoding="utf-8") as f:
    f.write(content)
print("Saved locally to docs/benchmark-results.md!")
