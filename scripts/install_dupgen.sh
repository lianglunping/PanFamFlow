#!/usr/bin/env bash
set -euo pipefail

PREFIX="${1:-$HOME/.local/opt/DupGen_finder}"
REPOSITORY="https://github.com/qiao-xin/DupGen_finder.git"
COMMIT="${DUPGEN_COMMIT:-54b950216efe7700f84395d03565cf75cd745e14}"

if [[ -e "$PREFIX" ]]; then
  echo "Refusing to overwrite existing path: $PREFIX" >&2
  exit 2
fi

git clone --no-checkout "$REPOSITORY" "$PREFIX"
git -C "$PREFIX" checkout --detach "$COMMIT"
test "$(git -C "$PREFIX" rev-parse HEAD)" = "$COMMIT"
make -C "$PREFIX"

cat <<MSG
Installed DupGen_finder under:
  $PREFIX

Add the directory to PATH:
  export PATH="$PREFIX:\$PATH"

Record the source commit:
  git -C "$PREFIX" rev-parse HEAD
MSG
