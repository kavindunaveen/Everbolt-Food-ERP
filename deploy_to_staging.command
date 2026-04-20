#!/bin/bash
cd "$(dirname "$0")"

echo "=================================================="
echo "🚀 DEPLOYING TO STAGING ENVIRONMENT"
echo "=================================================="

echo "[1/4] Transferring code to DigitalOcean (Staging)..."
rsync -avz --exclude '.git' --exclude '.venv' --exclude 'venv' --exclude 'db.sqlite3' --exclude '__pycache__' ./ root@178.128.52.97:/var/www/everbolt-erp-staging/

echo "[2/4] Installing dependencies & Migrating Database..."
ssh root@178.128.52.97 "cd /var/www/everbolt-erp-staging && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput"

echo "[3/4] Restarting Staging Server (Gunicorn)..."
ssh root@178.128.52.97 "systemctl restart gunicorn-staging"

echo "=================================================="
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "Visit: https://staging.organicfoodslanka.com"
echo "=================================================="
sleep 5
