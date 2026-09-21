import subprocess
import json
import time
import os
from pathlib import Path

INSTANCE_ID = "i-04e6c55fc0a27a4eb"
REGION = "us-west-2"
TARGET_DIR = Path("load-tests/results")
TARGET_DIR.mkdir(parents=True, exist_ok=True)

def run_ssm_command(commands):
    params = json.dumps({"commands": commands})
    cmd = [
        "aws", "ssm", "send-command",
        "--instance-ids", INSTANCE_ID,
        "--document-name", "AWS-RunShellScript",
        "--parameters", params,
        "--region", REGION
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    command_id = json.loads(res.stdout)["Command"]["CommandId"]
    
    # Wait for completion
    for _ in range(30):
        time.sleep(2)
        inv = subprocess.run([
            "aws", "ssm", "get-command-invocation",
            "--command-id", command_id,
            "--instance-id", INSTANCE_ID,
            "--region", REGION
        ], capture_output=True, text=True)
        data = json.loads(inv.stdout)
        status = data.get("Status")
        if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
            return data
    return None

def download_file(remote_path, local_path):
    print(f"Downloading {remote_path} ...")
    # Base64 encode on remote, stream or chunk if needed
    data = run_ssm_command([f"base64 -w 0 {remote_path}"])
    if not data or data.get("Status") != "Success":
        print(f"Failed to fetch {remote_path}: {data}")
        return False
    
    b64_content = data.get("StandardOutputContent", "").strip()
    import base64
    content = base64.b64decode(b64_content)
    with open(local_path, "wb") as f:
        f.write(content)
    print(f"Saved {local_path} ({len(content)} bytes)")
    return True

if __name__ == "__main__":
    files = [
        "hpa_gradual_ramp.json",
        "keda_gradual_ramp.json",
        "hpa_sudden_spike.json",
        "keda_sudden_spike.json",
        "hpa_daily_cycle.json",
        "keda_daily_cycle.json"
    ]
    
    remote_dir = "/home/ssm-user/Horizontal_pod_scaler/load-tests/results"
    for fname in files:
        remote_path = f"{remote_dir}/{fname}"
        local_path = TARGET_DIR / fname
        download_file(remote_path, local_path)
