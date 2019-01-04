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

# Environment variables
source $HOME/.config/zsh/env_variables

# Aliases
source $HOME/.config/zsh/aliases
