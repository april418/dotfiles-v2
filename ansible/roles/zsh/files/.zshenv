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

# $HOME/binにパスを通す
export PATH=$HOME/bin:$PATH


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
export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This loads nvm


# localのzshenvを読み込む
if [ -f ~/.zshenv.local ]; then
  source ~/.zshenv.local
fi
