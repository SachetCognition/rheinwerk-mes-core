#!/usr/bin/env bash
# Reproducible local stack for the consolidated MES:
#   Frappe + ERPNext substrate (SachetCognition/Chem_erpnext) + this app (rheinwerk_mes)
#   on MariaDB + Redis, with the programme fixtures seeded.
#
# Idempotent: re-running skips whatever already exists.
#
#   ./scripts/setup_stack.sh            # create/refresh the site and seed fixtures
#   ./scripts/start_stack.sh            # run it (http://dev.localhost:8000)
set -euo pipefail

BENCH_PATH="${BENCH_PATH:-$HOME/frappe-bench}"
SITE="${FRAPPE_SITE:-dev.localhost}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-frappe}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
ERPNEXT_SRC="${ERPNEXT_SRC:-$HOME/repos/Chem-erpnext}"
ERPNEXT_BRANCH="${ERPNEXT_BRANCH:-develop}"
APP_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PATH="$PATH:$HOME/.local/bin"
if [ -s "$HOME/.nvm/nvm.sh" ]; then
	# frappe develop requires node >= 24 for the asset build
	# shellcheck disable=SC1091
	. "$HOME/.nvm/nvm.sh" && nvm use 24 >/dev/null
fi

log() { printf '\n=== %s\n' "$1"; }

log "MariaDB + Redis"
sudo service mariadb start >/dev/null 2>&1 || true

cd "$BENCH_PATH"

# Frappe talks to the bench's own redis instances (ports from
# sites/common_site_config.json, typically 11000/13000), not to the distro
# redis-server on 6379 — bench install-app fails hard without them. They are
# stopped again on exit, because `bench start` supervises its own copies and
# aborts when the ports are already bound.
STARTED_REDIS_PORTS=()
stop_started_redis() {
	for started in "${STARTED_REDIS_PORTS[@]:-}"; do
		[ -n "$started" ] && redis-cli -p "$started" shutdown nosave >/dev/null 2>&1 || true
	done
}
trap stop_started_redis EXIT

for conf in config/redis_queue.conf config/redis_cache.conf; do
	[ -f "$conf" ] || continue
	port="$(awk '$1 == "port" { print $2 }' "$conf")"
	if ! redis-cli -p "$port" ping >/dev/null 2>&1; then
		redis-server "$conf" --daemonize yes
		STARTED_REDIS_PORTS+=("$port")
	fi
done

log "ERPNext substrate"
if [ ! -d "apps/erpnext" ]; then
	if [ -d "$ERPNEXT_SRC" ]; then
		bench get-app erpnext "$ERPNEXT_SRC" --branch "$ERPNEXT_BRANCH" --skip-assets
	else
		bench get-app erpnext https://github.com/SachetCognition/Chem_erpnext --branch "$ERPNEXT_BRANCH" --skip-assets
	fi
fi

log "rheinwerk_mes app (linked to the working tree at $APP_SRC)"
if [ ! -e "apps/rheinwerk_mes" ]; then
	ln -s "$APP_SRC" apps/rheinwerk_mes
	./env/bin/python -m pip install --quiet -e apps/rheinwerk_mes
fi
if ! grep -qx "rheinwerk_mes" sites/apps.txt; then
	# `bench get-app` leaves apps.txt without a trailing newline, so a naive
	# append would concatenate onto the previous app name.
	[ -s sites/apps.txt ] && [ -n "$(tail -c1 sites/apps.txt)" ] && printf '\n' >> sites/apps.txt
	printf 'rheinwerk_mes\n' >> sites/apps.txt
fi

log "node dependencies + asset build prerequisites"
( cd apps/frappe && yarn install --check-files >/dev/null )
ln -sfn ../../node_modules apps/frappe/frappe/public/node_modules
( cd apps/erpnext && yarn install --check-files >/dev/null )

log "site $SITE"
if [ ! -d "sites/$SITE" ]; then
	bench new-site "$SITE" \
		--db-root-password "$DB_ROOT_PASSWORD" \
		--admin-password "$ADMIN_PASSWORD" \
		--mariadb-user-host-login-scope='%'
fi
# Install what is missing (installing twice exits non-zero) and always migrate, so
# re-runs pick up new DocTypes, custom fields and patches from the working tree.
installed="$(bench --site "$SITE" list-apps 2>/dev/null | awk 'NF { print $1 }')"
for app in erpnext rheinwerk_mes; do
	printf '%s\n' "$installed" | grep -qx "$app" || bench --site "$SITE" install-app "$app"
done
bench --site "$SITE" migrate

log "assets"
bench build

log "programme fixtures"
bench --site "$SITE" execute rheinwerk_mes.fixtures.seed.seed_all

log "done — start the stack with ./scripts/start_stack.sh (Administrator / $ADMIN_PASSWORD)"
