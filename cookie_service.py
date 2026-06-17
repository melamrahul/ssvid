import cloudscraper
import time
import threading
import hashlib
import json
from flask import Flask, jsonify

app = Flask(__name__)
TARGET = "https://embed.dlsrv.online"

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

cache = {
    "cookies": {},
    "challenge": {},
    "solution": {},
    "updated_at": 0
}

REFRESH_INTERVAL = 300

def solve_pow(salt, ts, difficulty):
    target = "0" * (difficulty * 2)
    nonce = 0
    while True:
        data = f"{salt}{ts}{nonce}".encode()
        h = hashlib.sha256(data).hexdigest()
        if h.startswith(target):
            return nonce
        nonce += 1

def refresh():
    while True:
        try:
            # Step 1: visit page to get CF cookies
            scraper.get(TARGET + "/v1/full?videoId=oVosEbQZIP0", timeout=15)

            # Step 2: get PoW challenge
            r = scraper.post(TARGET + "/api/challenge", timeout=15)
            challenge = r.json()

            salt = challenge["salt"]
            ts = challenge["ts"]
            difficulty = challenge["difficulty"]

            print(f"[OK] Got challenge | difficulty={difficulty}", flush=True)

            # Step 3: solve PoW
            nonce = solve_pow(salt, ts, difficulty)
            print(f"[OK] Solved nonce={nonce}", flush=True)

            cache.update({
                "cookies": dict(scraper.cookies),
                "challenge": challenge,
                "solution": {"nonce": nonce, "salt": salt, "ts": ts},
                "updated_at": time.time()
            })

        except Exception as e:
            print(f"[ERR] {e}", flush=True)

        time.sleep(REFRESH_INTERVAL)

_thread = threading.Thread(target=refresh, daemon=True)
_thread.start()
time.sleep(6)

@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "has_cookies": bool(cache["cookies"]),
        "age_seconds": int(time.time() - cache["updated_at"])
    })

@app.route("/cookies")
def get_cookies():
    return jsonify({
        "cookies": cache["cookies"],
        "challenge": cache["challenge"],
        "solution": cache["solution"],
        "cookie_string": "; ".join(f"{k}={v}" for k, v in cache["cookies"].items()),
        "age_seconds": int(time.time() - cache["updated_at"]),
        "fresh": (time.time() - cache["updated_at"]) < REFRESH_INTERVAL
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
