# Deploy Voice AI with Cloudflare Tunnel

## Prerequisites

- Cloudflare account
- Domain managed by Cloudflare DNS
- `cloudflared` installed (`brew install cloudflared` on macOS)

## Setup (one-time)

### 1. Login to Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser to authorize your account.

### 2. Create a named tunnel

```bash
cloudflared tunnel create voice-ai
```

Note the **tunnel ID** printed (e.g. `abfee1be-3094-4095-8bab-f0c04f743f06`).

### 3. Create config file

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/<username>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: language.xibo.online
    service: http://localhost:8080
  - service: http_status:404
```

### 4. Route DNS

```bash
cloudflared tunnel route dns voice-ai language.xibo.online
```

## Running

### Start the app server

```bash
cd voice-ai && ../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Start the tunnel (in a separate terminal)

```bash
cloudflared tunnel run voice-ai
```

App is now live at **https://language.xibo.online**

## Stopping

```bash
# Stop tunnel: Ctrl+C in the tunnel terminal

# Stop server: Ctrl+C in the server terminal
# Or kill by port:
lsof -ti:8080 | xargs kill
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `tunnel not found` | Run `cloudflared tunnel list` to verify tunnel exists |
| DNS not resolving | Check Cloudflare dashboard for CNAME record on `language.xibo.online` |
| 502 Bad Gateway | Make sure uvicorn is running on port 8080 before starting the tunnel |
| Credentials error | Re-run `cloudflared tunnel login` to refresh credentials |
