#!/bin/bash
# Object Classification Demo - double-click to start (macOS). docs/design.md section 4.
cd "$(dirname "$0")" || exit 1
HERE="$PWD"

fail() {
  echo
  [ -n "$1" ] && echo "$1"
  read -r -p "Press Enter to close this window." _
  exit 1
}

# Opened from a zip or a temp/translocated copy: refuse.
case "$HERE/" in
  */var/folders/* | *.zip/* | */AppTranslocation/*)
    fail "Extract the zip first, then open the extracted folder." ;;
esac

# Pinned uv: version + SHA-256 per platform live in bin/uv.version.
eval "$(tr -d '\r' < bin/uv.version)"
case "$(uname -m)" in
  arm64) UV_ARCH=aarch64; UV_SHA=$DEMO_UV_SHA256_MACOS_AARCH64 ;;
  x86_64) UV_ARCH=x86_64; UV_SHA=$DEMO_UV_SHA256_MACOS_X86_64 ;;
  *) fail "This Mac is not supported." ;;
esac
UV="$HERE/bin/uv"
export UV_INSTALL_DIR="$HERE/bin"
export UV_NO_MODIFY_PATH=1
export UV_PYTHON_PREFERENCE=only-managed
export UV_PYTHON_INSTALL_DIR="$HERE/.uv/python"
export UV_CACHE_DIR="$HERE/.uv/cache"

if ! "$UV" --version 2>/dev/null | grep -q "^uv $DEMO_UV_VERSION "; then
  echo "Downloading uv $DEMO_UV_VERSION ..."
  TGZ="$HERE/bin/uv-download.tar.gz"
  curl -fL --retry 3 -o "$TGZ" \
    "https://github.com/astral-sh/uv/releases/download/$DEMO_UV_VERSION/uv-$UV_ARCH-apple-darwin.tar.gz" \
    || fail "First-time setup needs internet once."
  if [ "$(shasum -a 256 "$TGZ" | cut -d ' ' -f 1)" != "$UV_SHA" ]; then
    rm -f "$TGZ"
    fail "The uv download is damaged. Double-click Start Demo again."
  fi
  tar -xzf "$TGZ" -C "$HERE/bin" --strip-components 1 "uv-$UV_ARCH-apple-darwin/uv" || fail
  rm -f "$TGZ"
fi

# No extra: macOS uses the default torch (MPS on Apple Silicon, the pinned 2.2.2 on Intel).
"$UV" run --frozen python -m demo.setup --variant mac \
  || fail "Setup did not finish. Read the message above, then double-click Start Demo again."
"$UV" run --frozen python -m demo || fail
