#!/bin/zsh
#            _
#    _______| |__  _ __ ___
#   |_  / __| '_ \| '__/ __|
#  _ / /\__ \ | | | | | (__
# (_)___|___/_| |_|_|  \___|
#


# ========================================
#   dotfiles の更新の確認
# ========================================
# 入力を受けるので instant prompt より前に置く。instant prompt の間は stdin が端末につながらない。
# 起動を遅らせないよう、dotfiles コマンドが聞くことを書き残したときだけ起動する。
typeset -g _dotfiles_update_asked=
# 端末から zsh -ic で 1 つのコマンドを流すときは、プロンプトを出さないので聞かない。
if [[ -t 0 && -t 1 && -z ${ZSH_EXECUTION_STRING:-} && -s ${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/update-pending \
    && ${DOTFILES_UPDATE_ASK:-} != never && -z ${DOTFILES_UPDATING:-} ]] && (( $+commands[dotfiles] )); then
  dotfiles update --startup --style powerline && _dotfiles_update_asked=1
fi


# ========================================
#   powerlevel10k instant promptの設定
# ========================================
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


# ========================================
#   キャッシュディレクトリの初期化
# ========================================
if [ ! -d ~/.cache ]; then
  mkdir ~/.cache
fi
if [ ! -d ~/.cache/zsh ]; then
  mkdir ~/.cache/zsh
fi


# ========================================
#   zshプラグイン読み込み（zinit）
# ========================================
ZINIT_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/zinit/zinit.git"
source "$ZINIT_HOME/zinit.zsh"

# powerlevel10kをインストール
# zinit ice depth=1
zinit light romkatv/powerlevel10k


# ========================================
#   モジュール読み込み
# ========================================
# イベントに関数をバインドできるようにする
autoload -Uz add-zsh-hook
# プロンプト
autoload -Uz promptinit; promptinit
# バージョン管理情報を取得できるようにする
autoload -Uz vcs_info
# zshのバージョンごとに挙動を変えられるようにする
autoload -Uz is-at-least
# 端末情報を取得できるようにする
autoload -Uz terminfo
# 色を詳細に設定できるようにする
autoload -Uz colors; colors
# 補完機能を使用できるようにする
autoload -Uz compinit; compinit -u
# cdr を有効にする
autoload -Uz chpwd_recent_dirs cdr
# 履歴検索
autoload -Uz history-search-end


# ========================================
#   キー設定
# ========================================
# viライクなキーバインド
bindkey -v

# homeキーを使えるようにする
bindkey "OH" beginning-of-line
# endキーを使えるようにする
bindkey "OF" end-of-line
# deleteキーを使えるようにする
bindkey "[3~" delete-char


# ========================================
#   補完表示設定
# ========================================
# ディレクトリ名のみでcd
setopt auto_cd
# リストを詰めて表示
setopt list_packed
# ディレクトリ名の補完で末尾の / を自動的に付加し、次の補完に備える
setopt auto_param_slash
# ファイル名の展開でディレクトリにマッチした場合 末尾に / を付加
setopt mark_dirs
# 補完候補一覧でファイルの種別を識別マーク表示 (ls -F の記号)
setopt list_types
# 補完キー連打で順に補完候補を自動で補完
setopt auto_menu
# カッコの対応などを自動的に補完
setopt auto_param_keys
# コマンドラインでも # 以降をコメントと見なす
setopt interactive_comments
# コマンドラインの引数で --prefix=/usr などの = 以降でも補完できる
setopt magic_equal_subst
# 語の途中でもカーソル位置で補完
setopt complete_in_word
# カーソル位置は保持したままファイル名一覧を順次その場で表示
setopt always_last_prompt
# 日本語ファイル名等8ビットを通す
setopt print_eight_bit
# 拡張グロブで補完(~とか^とか。例えばless *.txt~memo.txt ならmemo.txt 以外の *.txt にマッチ)
setopt extended_glob
# 明確なドットの指定なしで.から始まるファイルをマッチ
setopt globdots
# 展開する前に補完候補を出させる(Ctrl-iで補完するようにする)
#bindkey "^I" menu-complete
# 補完候補を ←↓↑→ でも選択出来るようにする
zstyle ':completion:*:default' menu select=2
# 補完表示を詳細に
zstyle ':completion:*' verbose yes
# 補完候補の対象を拡張
zstyle ':completion:*' completer _expand _complete _match _prefix _approximate _list _history
# キャッシュを補完候補にする
zstyle ':completion:*' use-cache on
zstyle ':completion:*' cache-path ~/.cache/zsh/completion
# 概要説明を補完候補に表示
zstyle ':completion:*:options' description yes
# グループ名に空文字列を指定すると，マッチ対象のタグ名がグループ名に使われる
# したがって，すべての マッチ種別を別々に表示させたいなら以下のようにする
zstyle ':completion:*' group-name ''
# ファイル補完候補に色を付ける
# macOS の Homebrew は coreutils を g 接頭辞付きで入れるので gdircolors も探す。
if [ -f ~/.dircolors ]; then
  if (( $+commands[dircolors] )); then
    eval $(dircolors ~/.dircolors)
  elif (( $+commands[gdircolors] )); then
    eval $(gdircolors ~/.dircolors)
  fi
fi
if [ ! -z "$LS_COLORS" ]; then
  zstyle ':completion:*' list-colors ${(s.:.)LS_COLORS}
fi

# ========================================
#   入力訂正設定
# ========================================
# コマンドのスペルチェックを有効に
setopt correct


# ========================================
#   pushd設定
# ========================================
# cdの履歴表示、cd - で一つ前のディレクトリへ
setopt autopushd
# 同ディレクトリを履歴に追加しない
setopt pushd_ignore_dups


# ========================================
#   cdr設定
# ========================================
add-zsh-hook chpwd chpwd_recent_dirs
# cdr の設定
zstyle ':completion:*' recent-dirs-insert both
zstyle ':chpwd:*' recent-dirs-max 500
zstyle ':chpwd:*' recent-dirs-default true
zstyle ':chpwd:*' recent-dirs-file "$HOME/.cache/zsh/chpwd-recent-dirs"
zstyle ':chpwd:*' recent-dirs-pushd true


# ========================================
#   履歴設定
# ========================================
# historyファイル
HISTFILE=~/.zsh_history
# ファイルサイズ
HISTFILESIZE=1000000
HISTSIZE=1000000
# saveする量
SAVEHIST=1000000
# 重複を記録しない
setopt hist_ignore_dups
# スペース排除
setopt hist_reduce_blanks
# 履歴ファイルを共有
setopt share_history
# zshの開始終了を記録
setopt EXTENDED_HISTORY
# 重複するコマンドが記憶されるとき、古い方を削除する
setopt hist_ignore_all_dups
# 重複するコマンドが保存されるとき、古い方を削除する。
setopt hist_save_no_dups
# コマンド履歴呼び出し
zle -N history-beginning-search-backward-end history-search-end
zle -N history-beginning-search-forward-end history-search-end
bindkey "^P" history-beginning-search-backward-end
bindkey "^N" history-beginning-search-forward-end


# ========================================
#   プロンプト設定
# ========================================
# powerlevel10kの設定ファイルがあれば読み込む
if [ -f ~/.p10k.zsh ]; then
  source ~/.p10k.zsh
fi

# characters
local separator=""
local end=""
local right_arrow=""
local question=""
local info=""
local warn=""

# colors
local p10k_bg_color="%{[48;5;$(printf "%03d" "$POWERLEVEL9K_BACKGROUND")m%}"
local p10k_fg_color="%{[38;5;$(printf "%03d" "$POWERLEVEL9K_BACKGROUND")m%}"
local fg_red="%{[38;5;001m%}"
local fg_green="%{[38;5;002m%}"
local fg_yellow="%{[38;5;003m%}"
local fg_cyan="%{[38;5;014m%}"
local fg_gray="%{[38;5;245m%}"
local fg_default="%{[38;5;007m%}"
local reset="%{[0m%}"

# 入力訂正プロンプト
SPROMPT="$p10k_bg_color $question correct $fg_gray$separator$fg_red %R $fg_default$right_arrow$fg_green %r$fg_default ? $fg_gray$separator$fg_default [n/y/a/e] $reset$p10k_fg_color$end$reset "

# 補完メッセージのフォーマット設定
zstyle ':completion:*:messages' format "$p10k_bg_color$fg_cyan $info $fg_gray$separator$fg_default %d $reset$p10k_fg_color$end $reset"
zstyle ':completion:*:warnings' format "$p10k_bg_color $fg_yellow$warn$fg_default No matches for $fg_gray$separator$fg_default $fg_red %d $reset$p10k_fg_color$end $reset"
zstyle ':completion:*:descriptions' format "$p10k_bg_color $info Completing $fg_gray$separator$fg_cyan %d $reset$p10k_fg_color$end $reset"
zstyle ':completion:*:corrections' format "$p10k_bg_color $fg_red$warn$fg_default Errors in %d $fg_gray$separator$fg_red %e $reset$p10k_fg_color$end $reset"


# ========================================
#   エイリアス
# ========================================
alias -g ...='../..'
alias -g ....='../../..'
alias -g ls='ls --color=auto'
alias printcolors='for c in {000..255}; do echo -n "\e[38;5;${c}m $c" ; [ $(($c%16)) -eq 15 ] && echo;done;echo; for c in {000..255}; do echo -n "\e[48;5;${c}m $c" ; [ $(($c%16)) -eq 15 ] && echo;done;echo;'

# Cygwin用
if [ ! -z "$CYGWIN" ] || uname | grep -q 'CYGWIN'; then
  alias ipconfig='(){ ipconfig $@ | iconv -f cp932 -t UTF-8 }'
  alias ping='(){ ping $@ | iconv -f cp932 -t UTF-8 }'
fi

# tar.gzの圧縮・解凍
alias targz='(){ tar -zcvf $@ }'
alias untargz='(){ tar -zxvf $@ }'


# ========================================
#   ターミナルがscreenのとき最終行に常に
#   ディレクトリ名/コマンド名を表示させる
# ========================================
# GNU Screenが動作しているかどうか
function is_screen_running() {
  [ ! -z "$STY" ]
}

# screenの現在表示しているタブに実行されたコマンドを引数付きでセットする
function _set_executed_command_to_current_screen_tab() {
  print -bNP "\ek${1%% 2%% *}\e\\"
}

# screenの現在表示しているタブに現在のディレクトリをセットする
function _set_current_directory_to_current_screen_tab() {
  print -bNP "\ek$(basename $PWD)\e\\"
}

# ターミナルがscreenならイベントに関数をバインド
if is_screen_running; then
  add-zsh-hook preexec _set_executed_command_to_current_screen_tab
  add-zsh-hook precmd _set_current_directory_to_current_screen_tab
fi


# ========================================
#   dotfiles の更新通知
# ========================================
# .zshrc の本体で呼ぶとプロンプトを出さない zsh -ic でも動いて出力が混ざるため、最初の precmd で呼ぶ。
# この時点の出力は p10k が instant prompt の後にまとめて出し直すので消えない。
function _dotfiles_update_notice() {
  add-zsh-hook -d precmd _dotfiles_update_notice
  # 起動時に更新を聞いたシェルでは、同じ内容をそこで出している。
  if [[ -z $_dotfiles_update_asked ]] && (( $+commands[dotfiles] )); then
    # この時点の stdout は p10k の一時ファイルで端末ではないため、見た目は呼ぶ側で指定する。
    dotfiles notify --style powerline
  fi
  unset _dotfiles_update_asked
}
add-zsh-hook precmd _dotfiles_update_notice


# ========================================
#   その他
# ========================================
# Ctrl-sでターミナルがロックされないようにする
stty stop undef <$TTY >$TTY

# local設定ファイルがあれば読み込む
if [ -f ~/.zshrc.local ]; then
  source ~/.zshrc.local
fi
