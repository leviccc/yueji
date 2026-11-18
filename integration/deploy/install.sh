#!/bin/bash
set -euo pipefail
release=${1:?Specify /opt/yueji/releases/RELEASE}
case "$release" in /opt/yueji/releases/*) ;; *) echo 'Unexpected release path'; exit 1 ;; esac
test -f "$release/integration/app.py"
test -f /etc/yueji.env
install -d -m 700 -o yueji -g yueji /var/lib/yueji
install -d -m 700 /var/backups/yueji
find "$release" -type d -exec chmod 755 {} +
find "$release" -type f -exec chmod 644 {} +
previous=$(readlink -f /opt/yueji/current || true)
ln -sfn "$release" /opt/yueji/current
install -m 644 "$release/integration/deploy/yueji.service" /etc/systemd/system/yueji.service
install -m 644 "$release/integration/deploy/yueji-backup.service" /etc/systemd/system/yueji-backup.service
install -m 644 "$release/integration/deploy/yueji-backup.timer" /etc/systemd/system/yueji-backup.timer
cat > /usr/local/bin/yueji-configure <<'EOF'
#!/bin/sh
cd /opt/yueji/current
exec /opt/yueji/venv/bin/python -m integration.configure
EOF
chmod 755 /usr/local/bin/yueji-configure
systemctl daemon-reload
systemctl enable yueji yueji-backup.timer
systemctl restart yueji
if ! /opt/yueji/venv/bin/python - <<'PY'
import time,urllib.request
for attempt in range(25):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3) as response:
            if response.status==200:
                print('Unified backend is healthy.')
                raise SystemExit(0)
    except OSError:
        time.sleep(1)
raise SystemExit(1)
PY
then
    if test -n "$previous" && test "$previous" != "$release" && test -d "$previous"; then
        ln -sfn "$previous" /opt/yueji/current
        systemctl restart yueji
        echo 'Restored previous release.'
    fi
    exit 1
fi
if test -f /etc/letsencrypt/live/example.com/fullchain.pem; then
    install -m 644 "$release/integration/deploy/nginx-https.conf" /etc/nginx/sites-available/yueji
else
    install -m 644 "$release/integration/deploy/nginx-http.conf" /etc/nginx/sites-available/yueji
fi
ln -sfn /etc/nginx/sites-available/yueji /etc/nginx/sites-enabled/yueji
test ! -L /etc/nginx/sites-enabled/default || unlink /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx
systemctl start yueji-backup.timer
systemctl start yueji-backup.service
echo 'Release installed with persistent state and online backups.'
