import subprocess, json, time, sys

INSTANCE_ID = "i-04e6c55fc0a27a4eb"
REGION = "us-west-2"

def exec_ssm(cmd_str):
    params = json.dumps({"commands": [cmd_str]})
    res = subprocess.run([
        "aws", "ssm", "send-command",
        "--instance-ids", INSTANCE_ID,
        "--document-name", "AWS-RunShellScript",
        "--parameters", params,
        "--region", REGION
    ], capture_output=True, text=True)
    
    cid = json.loads(res.stdout)["Command"]["CommandId"]
    
    for _ in range(20):
        time.sleep(1.5)
        inv = subprocess.run([
            "aws", "ssm", "get-command-invocation",
            "--command-id", cid,
            "--instance-id", INSTANCE_ID,
            "--region", REGION
        ], capture_output=True, text=True)
        data = json.loads(inv.stdout)
        if data.get("Status") in ["Success", "Failed", "Cancelled"]:
            return data.get("StandardOutputContent", "") + data.get("StandardErrorContent", "")
    return ""

print("Checking results dir:")
print(exec_ssm("ls -l /home/ssm-user/Horizontal_pod_scaler/load-tests/results/"))
