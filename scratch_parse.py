import subprocess
import re
import json

cmd = [
    "aws", "ssm", "get-command-invocation",
    "--command-id", "0e06ab79-6c98-4936-a73e-d59e74011755",
    "--instance-id", "i-04e6c55fc0a27a4eb",
    "--region", "us-west-2"
]
res = subprocess.run(cmd, capture_output=True)
raw = res.stdout.decode("utf-8", errors="ignore")

# Find StandardOutputContent
match = re.search(r'"StandardOutputContent":\s*"(.*?)"\s*,\s*"StandardOutputUrl"', raw, re.DOTALL)
if match:
    content = match.group(1)
    # Unescape python json escape sequences
    content = content.encode('utf-8').decode('unicode_escape')
    # Filter out initial line if it says Generated
    lines = content.splitlines()
    start_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("# Phase 6"):
            start_idx = i
            break
    clean_md = "\n".join(lines[start_idx:])
    with open("docs/benchmark-results.md", "w", encoding="utf-8") as f:
        f.write(clean_md)
    print("Successfully wrote docs/benchmark-results.md! Content length:", len(clean_md))
else:
    print("Match failed. Raw output preview:")
    print(raw[:500])
