# Handtop dev layer (BUILD_DEV=1 images only).
# Guarded so plain bash/foot logins pay nothing when tools are absent.
command -v fdfind >/dev/null && alias fd=fdfind
command -v batcat >/dev/null && alias bat=batcat
command -v starship >/dev/null && eval "$(starship init bash --print-full-init)"
command -v direnv >/dev/null && eval "$(direnv hook bash)"
