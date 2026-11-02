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
if [ "$TERM" = "xterm" ]; then
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
  # nvm.sh をそのまま読むと、版を選ぶ nvm use が版の解決に起動のたび 300〜400 ms かける。
  # 読み込みは --no-use で済ませ、版が名前で決まるときは nvm と同じ関数で PATH などを組む。
  source "$NVM_DIR/nvm.sh" --no-use
  if (( $+functions[nvm_auto] && $+functions[nvm_change_path] && $+functions[nvm_has] )); then
    () {
      local node=${commands[node]-} version dir
      # nvm の nvm_auto と同じく、PATH の node が nvm の版ならそれを引き継ぎ、無ければ default を使う。
      if [[ $node == $NVM_DIR/* ]]; then
        [[ $node == $NVM_DIR/versions/node/*/bin/node ]] || return 1
        version=${${node#$NVM_DIR/versions/node/}%%/*}
      elif [[ -r $NVM_DIR/alias/default ]]; then
        version=v${$(<$NVM_DIR/alias/default)#v}
      fi
      dir=$NVM_DIR/versions/node/$version
      # 別名（lts/* など）や入っていない版は、nvm 自身の解決に任せる。
      [[ $version == v<->.<->.<-> && -x $dir/bin/node ]] || return 1
      # nvm 0.40.8 の nvm use が版を切り替えるところと同じ。nvm を上げたら nvm.sh と見比べる。
      PATH=$(nvm_change_path "$PATH" /bin "$dir")
      if nvm_has manpath; then
        MANPATH=$(nvm_change_path "${MANPATH-}" /share/man "$dir")
        case $MANPATH in
          :* | *::* | *:) ;;
          *) MANPATH=$MANPATH: ;;
        esac
        export MANPATH
      fi
      export PATH NVM_BIN=$dir/bin NVM_INC=$dir/include/node
    } || nvm_auto use
  else
    # 使う内部関数が nvm から消えたら、遅くても nvm.sh をそのまま読む。
    source "$NVM_DIR/nvm.sh"
  fi
fi
# nvm の補完は .zshrc で compinit の後に読む。


# ========================================
#   パッケージレジストリ設定 (Flatt Security Guard)
# ========================================
# 環境変数で設定することでプロジェクトの設定ファイルによる上書きを防ぐ
# トークンを設定する場合は ~/.zshenv.local で UV_DEFAULT_INDEX を上書きする
#   export UV_DEFAULT_INDEX="https://token:tg_anon_xxx@pypi.flatt.tech/simple/"
export NPM_CONFIG_REGISTRY="https://npm.flatt.tech"
# pnpm 11 以降は環境変数の registry を pnpm_config_registry からしか読まない
export PNPM_CONFIG_REGISTRY="https://npm.flatt.tech"
export UV_DEFAULT_INDEX="https://pypi.flatt.tech/simple/"


# ========================================
#   local設定ファイルがあれば読み込む
# ========================================
if [ -f ~/.zshenv.local ]; then
  source ~/.zshenv.local
fi
