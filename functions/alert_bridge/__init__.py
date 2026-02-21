"""Azure Monitor → GitHub repository_dispatch bridge.

Receives Azure Monitor Common Alert Schema webhooks and dispatches
repository_dispatch events to trigger the SRE agent workflow.

Authentication uses GitHub App (fishbowl-site-reliability) — PEM key stored in
Key Vault, JWT minted on each invocation, exchanged for an
installation access token.
"""

import logging
import os
import time

import azure.functions as func
import jwt
import requests

logger = logging.getLogger(__name__)


def get_pem_key() -> str:
    """Get GitHub App PEM key from Key Vault or local file."""
    vault_name = os.environ.get("KEY_VAULT_NAME")
    secret_name = os.environ.get("GITHUB_APP_PEM_SECRET_NAME", "fishbowl-sre-pem")

    if vault_name:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(
            vault_url=f"https://{vault_name}.vault.azure.net",
            credential=DefaultAzureCredential(),
        )
        return client.get_secret(secret_name).value

    # Local dev: read from file path
    key_path = os.environ.get("GITHUB_APP_SITE_RELIABILITY_KEY_PATH", "")
    if key_path and os.path.isfile(key_path):
        with open(key_path) as f:
            return f.read()

    raise ValueError(
        "No PEM key: set KEY_VAULT_NAME or GITHUB_APP_SITE_RELIABILITY_KEY_PATH"
    )


def get_installation_token(app_id: str, installation_id: str, pem_key: str) -> str:
    """Mint a JWT from the App PEM, exchange for an installation access token."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": app_id,
    }
    encoded_jwt = jwt.encode(payload, pem_key, algorithm="RS256")

    resp = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["token"]


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
    app_id = os.environ.get("GITHUB_APP_ID")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")

    if not app_id or not installation_id:
        logger.error("GITHUB_APP_ID and GITHUB_APP_INSTALLATION_ID must be set")
        return func.HttpResponse("Missing GitHub App config", status_code=500)

    try:
        pem_key = get_pem_key()
        token = get_installation_token(app_id, installation_id, pem_key)
    except Exception as e:
        logger.error("Failed to get GitHub App token: %s", e)
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
        logger.info(
            "Dispatched azure-alert to %s via fishbowl-site-reliability[bot]", repo
        )
        return func.HttpResponse("Dispatched", status_code=200)

    logger.error("GitHub dispatch failed: %s %s", resp.status_code, resp.text)
    return func.HttpResponse(f"GitHub API error: {resp.status_code}", status_code=502)
