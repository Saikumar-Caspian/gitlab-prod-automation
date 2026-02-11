import os
import sys
import requests
from urllib.parse import quote_plus

# =========================================================
# CONFIGURATION
# =========================================================

GITLAB_URL = "https://gitlab.com"
GROUP_PATH = "zimble_switching/dev-backend"
PROTECTED_BRANCH = "PROD"

DRY_RUN = False   # True = dry run, False = apply

# Users allowed to MERGE to PROD
MERGE_ALLOWED_USERS = [
    "vijay.kumar_zimblesystems.com",
    "rahulwrs",
    "nithinmaloth"
]

# Merge Request Approval Rule (ONLY for PROD)
APPROVAL_RULE = {
    "name": "PROD Merge Approval",
    "approvals_required": 1,
    "approver_usernames": [
        "vijay.kumar_zimblesystems.com",
        "rahulwrs",
        "nithinmaloth"
    ]
}

DEVELOPER = 30
MAINTAINER = 40

# =========================================================
# AUTH
# =========================================================

TOKEN = os.getenv("GITLAB_TOKEN", "").strip()
if not TOKEN:
    sys.exit("ERROR: GITLAB_TOKEN environment variable not set")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# =========================================================
# API HELPERS
# =========================================================

def api_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def api_post(url, payload):
    if DRY_RUN:
        print(f"    [DRY-RUN] POST {url}")
        return {}
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()

def api_delete(url):
    if DRY_RUN:
        print(f"    [DRY-RUN] DELETE {url}")
        return
    r = requests.delete(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return
    if r.status_code not in (200, 204):
        raise RuntimeError(f"{r.status_code}: {r.text}")

# =========================================================
# START
# =========================================================

if DRY_RUN:
    print("\n⚠️  DRY RUN MODE — NO CHANGES WILL BE MADE\n")

# ---------------------------------------------------------
# STEP 1: Resolve subgroup
# ---------------------------------------------------------
group = api_get(
    f"{GITLAB_URL}/api/v4/groups/{quote_plus(GROUP_PATH)}"
)
group_id = group["id"]

print(f"Target group: {GROUP_PATH} (id={group_id})")

# ---------------------------------------------------------
# STEP 2: Fetch repositories
# ---------------------------------------------------------
projects = []
page = 1

while True:
    batch = api_get(
        f"{GITLAB_URL}/api/v4/groups/{group_id}/projects",
        params={"per_page": 100, "page": page, "include_subgroups": True}
    )
    if not batch:
        break
    projects.extend(batch)
    page += 1

print(f"Found {len(projects)} repositories")

# ---------------------------------------------------------
# STEP 3: Resolve user IDs
# ---------------------------------------------------------
def resolve_user_ids(usernames):
    ids = []
    for username in usernames:
        users = api_get(
            f"{GITLAB_URL}/api/v4/users",
            params={"username": username}
        )
        if not users:
            sys.exit(f"ERROR: GitLab user not found: {username}")
        ids.append(users[0]["id"])
    return ids

merge_user_ids = resolve_user_ids(MERGE_ALLOWED_USERS)
approval_user_ids = resolve_user_ids(APPROVAL_RULE["approver_usernames"])

# ---------------------------------------------------------
# STEP 4: Process repositories (ONLY PROD)
# ---------------------------------------------------------
for project in projects:
    pid = project["id"]
    name = project["path_with_namespace"]

    print(f"\nProcessing: {name}")

    # ---- Check if PROD branch exists ----
    try:
        api_get(
            f"{GITLAB_URL}/api/v4/projects/{pid}/repository/branches/{PROTECTED_BRANCH}"
        )
    except requests.exceptions.HTTPError:
        print("  ⏭ PROD branch does not exist — skipping repo")
        continue

    # ---- Delete old protection (if any) ----
    protected_branch_url = (
        f"{GITLAB_URL}/api/v4/projects/{pid}/protected_branches/{PROTECTED_BRANCH}"
    )
    api_delete(protected_branch_url)

    # ---- Create protected branch ----
    protected_branch = api_post(
        f"{GITLAB_URL}/api/v4/projects/{pid}/protected_branches",
        {
            "name": PROTECTED_BRANCH,
            "push_access_level": DEVELOPER,
            "allow_force_push": False,
            "code_owner_approval_required": False,
            "merge_access_levels": [
                {"user_id": uid} for uid in merge_user_ids
            ]
        }
    )

    protected_branch_id = protected_branch.get("id")

    print("  ✔ PROD branch protected")

    # ---- Approval rule ONLY for PROD ----
    rules = api_get(
        f"{GITLAB_URL}/api/v4/projects/{pid}/approval_rules"
    )

    for rule in rules:
        if rule["name"] == APPROVAL_RULE["name"]:
            api_delete(
                f"{GITLAB_URL}/api/v4/projects/{pid}/approval_rules/{rule['id']}"
            )

    api_post(
        f"{GITLAB_URL}/api/v4/projects/{pid}/approval_rules",
        {
            "name": APPROVAL_RULE["name"],
            "approvals_required": APPROVAL_RULE["approvals_required"],
            "user_ids": approval_user_ids,
            "protected_branch_ids": [protected_branch_id]
        }
    )

    print("  ✔ PROD approval rule applied")

print("\nDONE.")
if DRY_RUN:
    print("Dry run completed — no changes made.")
else:
    print("Changes successfully applied.")
