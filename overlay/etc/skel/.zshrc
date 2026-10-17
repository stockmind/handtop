# ============================================================================
# ~/.zshrc — shipped by the image (/etc/skel; 10-image.sh copies skel into a
# fresh /home/rg). Ported from aurora webtop-private (webtop/config/.zshrc);
# container paths (/config/...) rewritten to $HOME, and toolchain managers that
# are not installed here are guarded so the shell always starts clean.
# Oh My Zsh + the two custom plugins come from build/04d-ohmyzsh.sh (pinned).
# ============================================================================

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load. (Inert while starship drives the prompt.)
ZSH_THEME="robbyrussell"

# Which plugins would you like to load?
plugins=(git docker zsh-autosuggestions zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh

# User configuration

# Preferred editor for local and remote sessions
export EDITOR='micro'
export VISUAL='micro'

# SDKMAN (guarded - only sourced when installed)
if [ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]; then
  export SDKMAN_DIR="$HOME/.sdkman"
  source "$HOME/.sdkman/bin/sdkman-init.sh"
fi

# Volta (guarded)
if [ -d "$HOME/.volta" ]; then
  export VOLTA_HOME="$HOME/.volta"
  export PATH="$VOLTA_HOME/bin:$PATH"
fi

eval "$(starship init zsh)"

# opencode
[ -d "$HOME/.opencode/bin" ] && export PATH="$HOME/.opencode/bin:$PATH"

# codex
[ -d "$HOME/.local/bin" ] && export PATH="$HOME/.local/bin:$PATH"

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
if [ -d "$HOME/.bun" ]; then
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
fi

# pnpm
if [ -d "$HOME/.local/share/pnpm" ]; then
  export PNPM_HOME="$HOME/.local/share/pnpm"
  case ":$PATH:" in
    *":$PNPM_HOME:"*) ;;
    *) export PATH="$PNPM_HOME:$PATH" ;;
  esac
fi
