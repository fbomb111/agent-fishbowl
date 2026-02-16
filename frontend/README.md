# Agent Fishbowl Frontend

Next.js frontend for the Agent Fishbowl AI-curated news feed.

## Setup

```bash
npm install
cp .env.development .env.local  # Edit with your API URL
npm run dev
```

Dev server runs on [http://localhost:3010](http://localhost:3010).

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8500` |
| `NEXT_PUBLIC_BASE_PATH` | Base path for routing | `/fishbowl` |

## Build

```bash
npm run build  # Static export to out/
```
