#!/usr/bin/env bash
# Run the local MES stack. Data is persistent: MariaDB keeps the site database and
# Redis is only a cache/queue, so restarts preserve everything seeded or entered.
set -euo pipefail

BENCH_PATH="${BENCH_PATH:-$HOME/frappe-bench}"
export PATH="$PATH:$HOME/.local/bin"
if [ -s "$HOME/.nvm/nvm.sh" ]; then
	# shellcheck disable=SC1091
	. "$HOME/.nvm/nvm.sh" && nvm use 24 >/dev/null
fi

sudo service mariadb start >/dev/null 2>&1 || true
cd "$BENCH_PATH"
exec bench start
