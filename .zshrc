# Fix $PATH
export PATH=$HOME/miniconda3/bin:$HOME/bin:$PATH

# Path to oh-my-zsh installation.
export ZSH="/home/wristcontrol/.oh-my-zsh"

# Oh-my-zsh theme
ZSH_THEME="geometry/geometry"

# Plugins
plugins=(
  git
)

# Don't use oh-my-zsh on TTY (.psf fonts can't render most things)
if [ "$TERM" != "linux" ]; then
  source $ZSH/oh-my-zsh.sh
fi

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# Preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR='vim'
else
  export EDITOR='nvim'
fi

# Terminal colors
source ~/.config/zsh/colors

# ls command color output
export LS_COLORS=$(cat ~/.config/zsh/ls_colors | ~/scripts/gen_ls_colors.sh)

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# SSH
export SSH_KEY_PATH="~/.ssh/id_rsa"
export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"

# Aliases
source $HOME/.config/zsh/aliases

# XDG variables
export XDG_CONFIG_HOME=$HOME/.config
export XDG_DATA_HOME=$HOME/.local/share
export XDG_CACHE_HOME=$HOME/.cache

# Key directories
export USER_SCRIPTS=$HOME/scripts
