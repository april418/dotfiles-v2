#            _
#    _______| |__   ___ _ ____   __
#   |_  / __| '_ \ / _ \ '_ \ \ / /
#  _ / /\__ \ | | |  __/ | | \ V /
# (_)___|___/_| |_|\___|_| |_|\_/
#


# ========================================
#   環境設定
# ========================================
# ロケール設定
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# エディタをvimにする
export EDITOR=vim

# xtermを256色表示可能にする
if [ "$TERM"="xterm" ]; then
  export TERM="xterm-256color"
fi

# ~/.local/binをPATHに追加
export PATH="$PATH:$HOME/.local/bin"


# ========================================
#   rbenv設定
# ========================================
if [ -d ~/.rbenv ]; then
  export PATH="$HOME/.rbenv/bin:$PATH"
  eval "$($HOME/.rbenv/bin/rbenv init -)"
fi


# ========================================
#   screen設定
# ========================================
if [ ! -z "$STY" ]; then
  export SHELL_NAME="$(basename $SHELL)"
fi


# ========================================
#   nvm設定
# ========================================
if [ -z "$XDG_CONFIG_HOME" ]; then
  export NVM_DIR="$HOME/.nvm"
else
  export NVM_DIR="$XDG_CONFIG_HOME/nvm"
fi
if [ -s "$NVM_DIR/nvm.sh" ]; then
  source "$NVM_DIR/nvm.sh"
fi
if [ -s "$NVM_DIR/bash_completion" ]; then
  source "$NVM_DIR/bash_completion"
fi


# ========================================
#   local設定ファイルがあれば読み込む
# ========================================
if [ -f ~/.zshenv.local ]; then
  source ~/.zshenv.local
fi
