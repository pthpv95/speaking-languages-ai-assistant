#!/bin/bash
cd "$(dirname "$0")"
lsof -ti:8080 | xargs kill -9 2>/dev/null
lsof -ti:8443 | xargs kill -9 2>/dev/null
../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --reload &
../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8443 --ssl-keyfile=key.pem --ssl-certfile=cert.pem --reload &
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
echo ""
echo "  Local:  http://localhost:8080"
echo "  Mobile: https://$IP:8443"
echo ""
wait
