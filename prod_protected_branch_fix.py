import os
import sys
import requests
from urllib.parse import quote_plus

# =========================================================
# MODE SWITCH (CHANGE ONLY THIS)
# =========================================================
DRY_RUN = True   # True = DRY RUN | False = REAL RUN

# =========================================================
# CONFIG
# =========================================================
GITLAB_URL = "https://gitlab.com"
GROUP_PATH = "zimble_switching/dev-backend"
BRANCH = "PROD"

MERGE_USERS = [
    "vijay.kumar_zimblesystems.com",
    "rahulwrs",
    "nithinmaloth"
]

DEVELOPER = 30
MAINTAINER = 40

TOKEN = os.getenv("GITLAB_TOKEN", "").strip()
if not TOKEN:
    sys.exit("ERROR: GITLAB_TOKEN not set")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# =========================================================
# HELPERS
# =========================================================
def api_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def api_delete(url):
    if DRY_RUN:
        print(f"[DRY-RUN] DELETE {url}")
        return
    r = requests.delete(url, headers=HEADERS, timeout=30)
    if r.status_code not in (200, 204, 404):
        raise RuntimeError(r.text)

def api_post(url, payload):
    if DRY_RUN:
        print(f"[DRY-RUN] POST {url}")
        print("Payload:", payload)
        return
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(r.text)

# =========================================================
# START
# =========================================================
print("\n==============================================")
print("MODE:", "DRY RUN (NO CHANGES)" if DRY_RUN else "REAL RUN (APPLYING)")
print("PROD → Allowed to merge = USERS ONLY")
print("PROD → Allowed to push and merge = Dev + Maintainers")
print("==============================================\n")

# Resolve group
group = api_get(f"{GITLAB_URL}/api/v4/groups/{quote_plus(GROUP_PATH)}")
group_id = group["id"]

# Fetch projects
projects = []
page = 1
while True:
    batch = api_get(
        f"{GITLAB_URL}/api/v4/groups/{group_id}/projects",
        params={"per_page": 100, "page": page}
    )
    if not batch:
        break
    projects.extend(batch)
    page += 1

print(f"Found {len(projects)} repositories")

# Resolve merge user IDs
merge_user_ids = []
for username in MERGE_USERS:
    users = api_get(
        f"{GITLAB_URL}/api/v4/users",
        params={"username": username}
    )
    if not users:
        sys.exit(f"ERROR: User not found: {username}")
    merge_user_ids.append(users[0]["id"])

# Process repositories
for project in projects:
    pid = project["id"]
    name = project["path_with_namespace"]

    print(f"\n➡ {name}")

    # Check PROD branch exists
    try:
        api_get(
            f"{GITLAB_URL}/api/v4/projects/{pid}/repository/branches/{BRANCH}"
        )
    except:
        print("   ⏭ PROD branch not found, skipping")
        continue

    # Remove existing PROD protection
    api_delete(
        f"{GITLAB_URL}/api/v4/projects/{pid}/protected_branches/{BRANCH}"
    )

    # Recreate PROD protection (THIS IS THE KEY FIX)
    api_post(
        f"{GITLAB_URL}/api/v4/projects/{pid}/protected_branches",
        {
            "name": BRANCH,

            # UI → Allowed to push and merge
            "push_access_level": DEVELOPER,

            # UI → Allowed to merge (users list)
            "merge_access_levels": [
                {"user_id": uid, "access_level": MAINTAINER}
                for uid in merge_user_ids
            ]

            # ❌ DO NOT set merge_access_level
            # ❌ DO NOT touch anything else
        }
    )

    print("   ✅ Allowed to merge = users only")
    print("   ✅ Allowed to push and merge = Dev + Maintainers")

print("\nDONE")
