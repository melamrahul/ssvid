import cloudscraper
import time
import threading
import hashlib
import os
from flask import Flask, jsonify

import sys
print(f"[STARTUP] Python {sys.version}", flush=True)

try:
    import cloudscraper
    print("[STARTUP] cloudscraper OK", flush=True)
except Exception as e:
    print(f"[STARTUP] cloudscraper FAILED: {e}", flush=True)

app = Flask(__name__)
TARGET = "https://embed.dlsrv.online"

cache = {
    "cookies": {},
    "challenge": {},
    "solution": {},
    "updated_at": 0,
    "last_error": ""
}

REFRESH_INTERVAL = 300

def make_scraper():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
        delay=10
    )

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
        scraper = make_scraper()  # fresh scraper each cycle
        try:
            print("[*] Visiting page...", flush=True)
            r1 = scraper.get(TARGET + "/v1/full?videoId=oVosEbQZIP0", timeout=20)
            print(f"[*] Page status: {r1.status_code}", flush=True)

            time.sleep(3)  # wait like a human

            print("[*] Posting to /api/challenge...", flush=True)
            r2 = scraper.post(TARGET + "/api/challenge", timeout=20)
            print(f"[*] Challenge status: {r2.status_code}", flush=True)
            print(f"[*] Challenge body: {r2.text[:200]}", flush=True)

            challenge = r2.json()

            salt = challenge["salt"]
            ts = challenge["ts"]
            difficulty = challenge["difficulty"]

            print(f"[OK] Got challenge | difficulty={difficulty}", flush=True)

            nonce = solve_pow(salt, ts, difficulty)
            print(f"[OK] Solved | nonce={nonce}", flush=True)

            cache.update({
                "cookies": dict(scraper.cookies),
                "challenge": challenge,
                "solution": {"nonce": nonce, "salt": salt, "ts": ts},
                "updated_at": time.time(),
                "last_error": ""
            })

        except Exception as e:
            err = str(e)
            print(f"[ERR] {err}", flush=True)
            cache["last_error"] = err

        time.sleep(REFRESH_INTERVAL)

_thread = threading.Thread(target=refresh, daemon=True)
_thread.start()
time.sleep(10)  # give it more time to complete first refresh

@app.route("/health")
def health():
    return jsonify({
        "ok": bool(cache["cookies"]),
        "has_cookies": bool(cache["cookies"]),
        "age_seconds": int(time.time() - cache["updated_at"]),
        "last_error": cache["last_error"]
    })

@app.route("/cookies")
def get_cookies():
    return jsonify({
        "cookies": cache["cookies"],
        "challenge": cache["challenge"],
        "solution": cache["solution"],
        "cookie_string": "; ".join(f"{k}={v}" for k, v in cache["cookies"].items()),
        "age_seconds": int(time.time() - cache["updated_at"]),
        "fresh": (time.time() - cache["updated_at"]) < REFRESH_INTERVAL,
        "last_error": cache["last_error"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
