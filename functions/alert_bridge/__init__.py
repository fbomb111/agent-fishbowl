"""Azure Monitor → GitHub repository_dispatch bridge.

Receives Azure Monitor Common Alert Schema webhooks and dispatches
repository_dispatch events to trigger the SRE agent workflow.
"""

import logging
import os

import azure.functions as func
import requests

logger = logging.getLogger(__name__)


def get_github_token() -> str:
    """Get GitHub PAT from Key Vault (Azure) or env var (local dev)."""
    vault_name = os.environ.get("KEY_VAULT_NAME")
    secret_name = os.environ.get("GITHUB_TOKEN_SECRET_NAME")

    if vault_name and secret_name:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(
            vault_url=f"https://{vault_name}.vault.azure.net",
            credential=DefaultAzureCredential(),
        )
        return client.get_secret(secret_name).value

    # Local dev: read directly from env
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError(
            "No GitHub token: set KEY_VAULT_NAME+SECRET_NAME or GITHUB_TOKEN"
        )
    return token


def parse_alert(body: dict) -> dict:
    """Extract useful fields from Azure Monitor Common Alert Schema."""
    essentials = body.get("data", {}).get("essentials", {})
    return {
        "alertRule": essentials.get("alertRule", "unknown"),
        "severity": essentials.get("severity", "unknown"),
        "monitorCondition": essentials.get("monitorCondition", "unknown"),
        "description": essentials.get("description", ""),
        "firedDateTime": essentials.get("firedDateTime", ""),
        "alertTargetIDs": essentials.get("alertTargetIDs", []),
    }


def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Alert bridge triggered")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)

    alert_payload = parse_alert(body)
    logger.info(
        "Alert: %s (severity: %s)",
        alert_payload["alertRule"],
        alert_payload["severity"],
    )

    repo = os.environ.get("GITHUB_REPO", "YourMoveLabs/agent-fishbowl")

    try:
        token = get_github_token()
    except Exception as e:
        logger.error("Failed to get GitHub token: %s", e)
        return func.HttpResponse(f"Token error: {e}", status_code=500)

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/dispatches",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={
            "event_type": "azure-alert",
            "client_payload": alert_payload,
        },
        timeout=10,
    )

    if resp.status_code == 204:
        logger.info("Dispatched azure-alert to %s", repo)
        return func.HttpResponse("Dispatched", status_code=200)

    logger.error("GitHub dispatch failed: %s %s", resp.status_code, resp.text)
    return func.HttpResponse(f"GitHub API error: {resp.status_code}", status_code=502)
