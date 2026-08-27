import time
import math
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# Track active synthetic load threads
active_threads = 0
thread_lock = threading.Lock()

def cpu_loader(duration: int, intensity: float):
    """
    Consumes CPU by calculating factorials/math operations in a tight loop.
    duration: Seconds to run.
    intensity: How much sleep to add (1.0 = full throttle, lower = less CPU).
    """
    global active_threads
    with thread_lock:
        active_threads += 1

    end_time = time.time() + duration
    try:
        while time.time() < end_time:
            # CPU intensive math
            for _ in range(1000):
                math.factorial(100)
            
            # Throttle if intensity is less than 1.0
            if intensity < 1.0:
                time.sleep((1.0 - intensity) * 0.01)
    finally:
        with thread_lock:
            active_threads -= 1

@app.route("/")
def health_check():
    return jsonify({
        "status": "healthy",
        "active_load_threads": active_threads
    })

@app.route("/load", methods=["POST"])
def generate_load():
    """
    Endpoint to trigger synthetic CPU load.
    Example: POST /load?duration=60&intensity=1.0&threads=4
    """
    duration = int(request.args.get("duration", 30))
    intensity = float(request.args.get("intensity", 1.0))
    threads = int(request.args.get("threads", 1))

    # Cap to prevent completely locking up the node
    duration = min(duration, 300)
    threads = min(threads, 16)
    intensity = min(max(intensity, 0.1), 1.0)

    for _ in range(threads):
        t = threading.Thread(target=cpu_loader, args=(duration, intensity))
        t.daemon = True
        t.start()

    return jsonify({
        "status": "load_started",
        "duration_seconds": duration,
        "intensity": intensity,
        "threads": threads
    }), 202

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
