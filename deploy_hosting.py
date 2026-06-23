#!/usr/bin/env python3
"""
Deploy a static dist/ folder to Firebase Hosting via the REST API.
Auth: a Google OAuth access token (owner) + quota project header. Avoids
firebase-tools interactive login and SA keys (blocked by org policy).

Usage: deploy_hosting.py <site> <dist_dir> <access_token> <quota_project>
"""
import concurrent.futures
import gzip
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://firebasehosting.googleapis.com/v1beta1"


def call(method, url, token, project, data=None, ctype="application/json",
         raw=False, timeout=60, retries=4):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Goog-User-Project": project,
        "Content-Type": ctype,
    }
    body = data if raw else (data.encode() if data is not None else None)
    # Per-request timeout + retry: a stuck socket on any one of the ~800 uploads
    # used to hang the whole deploy forever; bounded retries make it resilient to
    # transient SSL/network blips (the EOF errors seen mid-upload).
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise last


def main():
    site, dist, token, project = sys.argv[1:5]
    import json

    # 1. create version.
    #  - redirect: English moved from /en/ to the root, so 301 the old /en/* URLs.
    #  - SPA fallback: any path without a matching static file serves /index.html
    #    (so unknown /lag/... or deep links still boot the app).
    version_config = json.dumps({
        "config": {
            "redirects": [
                {"regex": "^/en(?:/(?P<rest>.*))?$", "statusCode": 301,
                 "location": "/:rest"}
            ],
            "rewrites": [{"glob": "**", "path": "/index.html"}],
        }
    })
    version = json.loads(call("POST", f"{API}/sites/{site}/versions",
                              token, project, version_config))["name"]
    print("version:", version)

    # 2. gzip every file, hash gzipped bytes, build manifest
    manifest, blobs = {}, {}
    for root, _, files in os.walk(dist):
        for fn in files:
            full = os.path.join(root, fn)
            rel = "/" + os.path.relpath(full, dist).replace(os.sep, "/")
            with open(full, "rb") as f:
                gz = gzip.compress(f.read(), 9)
            h = hashlib.sha256(gz).hexdigest()
            manifest[rel] = h
            blobs[h] = gz
    print("files:", len(manifest))

    # 3. populateFiles — Firebase returns only the blob hashes it doesn't already
    # have (content-addressed dedupe across versions). A JS/CSS change re-hashes
    # the bundle, so every prerendered page that embeds it counts as "new".
    pop = json.loads(call("POST", f"{API}/{version}:populateFiles",
                          token, project, json.dumps({"files": manifest})))
    upload_url = pop["uploadUrl"]
    required = pop.get("uploadRequiredHashes", [])
    print("upload required:", len(required))

    # 4. upload the required blobs IN PARALLEL (sequential was minutes for ~800
    # files — long enough to outlast the access token / hit a network blip).
    def _put(h):
        call("PUT", f"{upload_url}/{h}", token, project,
             data=blobs[h], ctype="application/octet-stream", raw=True)
        return h

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(_put, h) for h in required]
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            fut.result()  # re-raise any upload error (after its own retries)
            done += 1
            if done % 100 == 0 or done == len(required):
                print(f"uploaded {done}/{len(required)}")

    # 5. finalize
    call("PATCH", f"{API}/{version}?update_mask=status",
         token, project, json.dumps({"status": "FINALIZED"}))
    print("finalized")

    # 6. release
    rel = json.loads(call("POST",
                          f"{API}/sites/{site}/releases?version_name={version}",
                          token, project, "{}"))
    print("released:", rel.get("name"))


if __name__ == "__main__":
    main()
