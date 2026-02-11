GITLAB_URL = "https://gitlab.com"
GROUP_PATH = "saikumar_Z/dev-backend"
PROTECTED_BRANCH = "PROD"

# 🔴 DRY RUN MODE
DRY_RUN = True   # ← change to False to apply for real
# Users who are allowed to MERGE to PROD
MERGE_ALLOWED_USERS = [
    #"vijay.kumar_zimblesystems.com",
     #   "rahulwrs",
      #  "nithinmaloth"
      "srinivas.lords34"
]

APPROVAL_RULE = {
    "name": "PROD Merge Approval",
    "approvals_required": 1,
    "approver_usernames": [
       # "vijay.kumar_zimblesystems.com",
        #"rahulwrs",
        #"nithinmaloth"
        "srinivas.lords34"
    ]
}
