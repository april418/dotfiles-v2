#    _               _
#   | |__   __ _ ___| |__  _ __ ___
#   | '_ \ / _` / __| '_ \| '__/ __|
#  _| |_) | (_| \__ \ | | | | | (__
# (_)_.__/ \__,_|___/_| |_|_|  \___|
#


# Source global definitions
if [ -f /etc/bashrc ]; then
  source /etc/bashrc
fi


# =======================================
# screenのstatusbarにディレクトリ名/コマンド名を表示させる
# =======================================
if [ $TERM='screen' ] || [ $TERM='screen-bce' ]; then
  export PS1='[\u@\h \W]\$ '
  export PROMPT_COMMAND='echo -ne "\033k\033\0134\033k$(basename $(pwd))\033\\"'
else
  export PS1='[\u@\h \W]\$ '
fi


# =======================================
# gitの補完設定
# =======================================
if [ -f ~/.git-completion.bash ]; then
  source ~/.git-completion.bash
fi

