# Fix $PATH
export PATH=$HOME/bin:$PATH

# Don't use oh-my-zsh on TTY (.psf fonts can't render most things)
if [ "$TERM" != "linux" ]; then
    # Path to oh-my-zsh installation.
    export ZSH="/home/wristcontrol/.oh-my-zsh"

    # Oh-my-zsh theme
    ZSH_THEME="spaceship"
    source $HOME/.config/zsh/spaceship_prompt

    # Plugins
    plugins=(
        gitfast
        virtualenv
    )

    source $ZSH/oh-my-zsh.sh
fi

# History
HISTFILE=$HOME/.zsh_history
HISTSIZE=5000
SAVEHIST=5000
setopt SHARE_HISTORY
setopt APPEND_HISTORY
setopt INC_APPEND_HISTORY
setopt HIST_IGNORE_DUPS

# Preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR=vim
else
  export EDITOR=nvim
fi

export BAT_THEME=ansi

# TTY colors (outside of X11)
source ~/.config/zsh/tty_colors

# ls command color output
export LS_COLORS=$(cat ~/.config/zsh/ls_colors | $HOME/bin/gen_ls_colors)

# Aliases
source $HOME/.config/zsh/aliases

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/wristcontrol/miniconda3/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/wristcontrol/miniconda3/etc/profile.d/conda.sh" ]; then
        . "/home/wristcontrol/miniconda3/etc/profile.d/conda.sh"
    else
        export PATH="/home/wristcontrol/miniconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<
