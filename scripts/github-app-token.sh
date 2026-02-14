#!/bin/bash
# Generate a GitHub App installation access token.
# Usage: source this file, then call get_github_app_token.
#
# Requires: openssl, curl, jq
#
# get_github_app_token <app_id> <installation_id> <private_key_path>
#   Prints the installation token to stdout (valid 1 hour).

get_github_app_token() {
    local app_id="$1"
    local installation_id="$2"
    local private_key_path="$3"

    if [ -z "$app_id" ] || [ -z "$installation_id" ] || [ -z "$private_key_path" ]; then
        echo "Usage: get_github_app_token <app_id> <installation_id> <private_key_path>" >&2
        return 1
    fi

    if [ ! -f "$private_key_path" ]; then
        echo "ERROR: Private key not found: $private_key_path" >&2
        return 1
    fi

    # --- Step 1: Generate JWT (RS256, valid 10 minutes) ---
    local header='{"alg":"RS256","typ":"JWT"}'
    local now
    now=$(date +%s)
    local iat=$((now - 60))
    local exp=$((now + 600))
    local payload="{\"iat\":${iat},\"exp\":${exp},\"iss\":\"${app_id}\"}"

    # Base64url encode (URL-safe, no padding)
    local header_b64
    header_b64=$(printf '%s' "$header" | openssl base64 -A | tr '+/' '-_' | tr -d '=')
    local payload_b64
    payload_b64=$(printf '%s' "$payload" | openssl base64 -A | tr '+/' '-_' | tr -d '=')

    # Sign with RS256
    local signature
    signature=$(printf '%s' "${header_b64}.${payload_b64}" | \
        openssl dgst -sha256 -sign "$private_key_path" | \
        openssl base64 -A | tr '+/' '-_' | tr -d '=')

    local jwt="${header_b64}.${payload_b64}.${signature}"

    # --- Step 2: Exchange JWT for installation token ---
    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer ${jwt}" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/app/installations/${installation_id}/access_tokens")

    local token
    token=$(printf '%s' "$response" | jq -r '.token // empty')

    if [ -z "$token" ]; then
        echo "ERROR: Failed to get installation token. Response:" >&2
        printf '%s' "$response" | jq . >&2 2>/dev/null || printf '%s\n' "$response" >&2
        return 1
    fi

    printf '%s' "$token"
}
