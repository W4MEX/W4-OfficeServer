#!/usr/bin/env bash
set -euo pipefail

# Keep Linux container paths intact when Docker is invoked from Git Bash.
export MSYS2_ARG_CONV_EXCL='*'

container=${1:?Usage: bash apply.sh CONTAINER}
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
assets=/var/www/euro-office/documentserver-example/welcome

docker exec --user 0 "$container" test -f /etc/nginx/includes/ds-example.conf
docker exec --user 0 "$container" test -d "$assets"

for asset in w4-office-white.svg w4-icon.svg; do
  docker cp "./$asset" "$container:$assets/$asset"
  docker exec --user 0 "$container" chmod 644 "$assets/$asset"
done

docker exec --user 0 -i "$container" sh -ec '
  config=/etc/nginx/includes/ds-example.conf
  staged=$(mktemp)
  previous=$(mktemp)
  trap '"'"'rm -f "$staged" "$previous"'"'"' EXIT
  cat > "$staged"
  cp "$config" "$previous"
  cat "$staged" > "$config"
  if ! nginx -t || ! nginx -s reload; then
    cat "$previous" > "$config"
    exit 1
  fi
' < ds-example.conf
