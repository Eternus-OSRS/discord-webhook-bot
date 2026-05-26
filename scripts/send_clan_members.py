import os
import json
import datetime as dt
from io import BytesIO

import requests


WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
WOM_VERIFICATION_CODE = os.getenv("WOM_VERIFICATION_CODE")  # not required for GET, kept for future use
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")


def fetch_group_members():
    """
    Calls WOM Get Group Details endpoint:
    GET https://api.wiseoldman.net/v2/groups/:id
    Returns memberships with nested player objects. [3](https://www.youtube.com/watch?v=xh2iabVtw-c)[4](https://envtools.dev/guides/github-actions-secrets)
    """
    url = f"https://api.wiseoldman.net/v2/groups/{WOM_GROUP_ID}"
    print("=== WOM DEBUG ===")
    print(f"Requesting: {url}")
