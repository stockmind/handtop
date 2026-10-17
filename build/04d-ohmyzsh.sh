#!/bin/bash
# Oh My Zsh + the two custom plugins the shipped ~/.zshrc uses, installed into
# /etc/skel so every fresh home gets them (10-image.sh copies skel -> /home/rg).
# Pinned to the revisions the handheld has been running (docs/desktop.md).
# zsh itself and starship come from the package lists.
set -euo pipefail
source "$(dirname "$0")/config.sh"

OMZ_REPO="https://github.com/ohmyzsh/ohmyzsh.git"
OMZ_COMMIT="964ddf789b022b6958b27d02d7fa54f552de21e9"                  # 2026-10-13
PLUGINS=(
  "https://github.com/zsh-users/zsh-autosuggestions.git|85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5|zsh-autosuggestions"
  "https://github.com/zsh-users/zsh-syntax-highlighting.git|e6683f20e5c38d3e5447f45845d04ddda75d0f23|zsh-syntax-highlighting"
)

SKEL="$ROOTFS/etc/skel"
OMZ="$SKEL/.oh-my-zsh"

echo "Installing Oh My Zsh into /etc/skel (pinned) ..."
safe_rm -r "$OMZ"
git clone --quiet "$OMZ_REPO" "$OMZ"
git -C "$OMZ" -c advice.detachedHead=false checkout --quiet "$OMZ_COMMIT"

for spec in "${PLUGINS[@]}"; do
  repo="${spec%%|*}"; rest="${spec#*|}"; commit="${rest%%|*}"; name="${rest#*|}"
  git clone --quiet "$repo" "$OMZ/custom/plugins/$name"
  git -C "$OMZ/custom/plugins/$name" -c advice.detachedHead=false checkout --quiet "$commit"
  echo "  + custom/plugins/$name @ ${commit:0:8}"
done

# Drop git metadata: the device never needs the history, saves ~5 MiB.
safe_rm -r "$OMZ/.git"
for spec in "${PLUGINS[@]}"; do
  name="${spec##*|}"
  safe_rm -r "$OMZ/custom/plugins/$name/.git"
done

chown -R root:root "$SKEL"
echo "Oh My Zsh installed: $(du -sh "$OMZ" | cut -f1)"
