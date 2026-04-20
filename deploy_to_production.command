#!/bin/bash
cd "$(dirname "$0")"

echo "=================================================="
echo "🚨 DEPLOYING TO LIVE PRODUCTION SERVER"
echo "=================================================="

read -p "Are you absolutely sure you want to push to Production? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Deployment cancelled."
    exit 1
fi

echo "[1/4] Transferring code to DigitalOcean (Production)..."
rsync -avz --exclude '.git' --exclude '.venv' --exclude 'venv' --exclude 'db.sqlite3' --exclude '__pycache__' ./ root@178.128.52.97:/var/www/everbolt-erp/

echo "[2/4] Installing dependencies & Migrating Database..."
ssh root@178.128.52.97 "cd /var/www/everbolt-erp && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput"

echo "[3/4] Restarting Production Server (Gunicorn)..."
ssh root@178.128.52.97 "systemctl restart gunicorn"

echo "=================================================="
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "Visit: https://erp.organicfoodslanka.com"
echo "=================================================="
sleep 5
