# Copyright 2026 Poing Studios
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
from typing import Any, Dict
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response

from poing_reviewer.core.config import Config
from poing_reviewer.core.logging import get_logger
from poing_reviewer.server.auth import get_installation_token, verify_webhook_signature
from poing_reviewer.services.review_service import ReviewService
from poing_reviewer.services.triage_service import TriageService

logger = get_logger("server.app")

app = FastAPI(
    title="Poing Reviewer Webhook Server",
    description="Autonomous AI code review and issue triage bot for GitHub",
    version="1.0.0",
)


def _handle_pull_request(payload: Dict[str, Any], token: str) -> None:
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened", "review_requested"):
        logger.info(f"Ignoring PR action '{action}'")
        return

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    repo_full_name = repo.get("full_name", "")
    pr_number = pr.get("number")
    base_ref = pr.get("base", {}).get("ref", "master")
    pr_title = pr.get("title", "")
    head_sha = pr.get("head", {}).get("sha", "")

    logger.info(f"Processing PR #{pr_number} in {repo_full_name} ({action})...")

    cfg = Config(
        mode="review",
        repo=repo_full_name,
        pr_number=pr_number,
        base_ref=base_ref,
        pr_title=pr_title,
        head_sha=head_sha,
        github_token=token,
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
    )

    try:
        service = ReviewService(config=cfg)
        service.run()
    except Exception as e:
        logger.error(f"Error reviewing PR #{pr_number} in {repo_full_name}: {e}", exc_info=True)


def _handle_issue(payload: Dict[str, Any], token: str) -> None:
    action = payload.get("action")
    if action != "opened":
        logger.info(f"Ignoring issue action '{action}'")
        return

    issue = payload.get("issue", {})
    repo = payload.get("repository", {})
    repo_full_name = repo.get("full_name", "")
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "")

    logger.info(f"Processing Issue #{issue_number} in {repo_full_name}...")

    cfg = Config(
        mode="triage",
        repo=repo_full_name,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body,
        issue_action=action,
        github_token=token,
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
    )

    try:
        service = TriageService(config=cfg)
        service.run()
    except Exception as e:
        logger.error(f"Error triaging issue #{issue_number} in {repo_full_name}: {e}", exc_info=True)


@app.get("/")
@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "poing-reviewer"}


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
) -> Response:
    body = await request.body()

    webhook_secret = os.environ.get("WEBHOOK_SECRET", "")
    if webhook_secret and not verify_webhook_signature(body, x_hub_signature_256, webhook_secret):
        logger.warning("Invalid webhook signature received")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    installation = payload.get("installation", {})
    installation_id = installation.get("id")
    if not installation_id:
        logger.warning("No installation ID found in webhook payload")
        return Response(content="No installation found", status_code=200)

    app_id = os.environ.get("APP_ID", "")
    private_key = os.environ.get("APP_PRIVATE_KEY", "").replace("\\n", "\n")

    # If private key is passed as path
    private_key_path = os.environ.get("APP_PRIVATE_KEY_PATH", "")
    if not private_key and private_key_path and os.path.exists(private_key_path):
        with open(private_key_path, "r", encoding="utf-8") as f:
            private_key = f.read()

    if not app_id or not private_key:
        logger.error("APP_ID or APP_PRIVATE_KEY not configured on server")
        raise HTTPException(status_code=500, detail="Server GitHub App credentials not configured")

    token = get_installation_token(app_id, private_key, installation_id)
    if not token:
        logger.error(f"Failed to generate installation token for installation #{installation_id}")
        raise HTTPException(status_code=500, detail="Failed to generate installation token")

    if x_github_event == "pull_request":
        background_tasks.add_task(_handle_pull_request, payload, token)
        return Response(content="Pull request review queued", status_code=202)

    elif x_github_event == "issues":
        background_tasks.add_task(_handle_issue, payload, token)
        return Response(content="Issue triage queued", status_code=202)

    elif x_github_event == "ping":
        return Response(content="PONG", status_code=200)

    return Response(content=f"Ignored event '{x_github_event}'", status_code=200)
