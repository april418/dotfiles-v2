"        _
" __   _(_)_ __ ___  _ __ ___
" \ \ / / | '_ ` _ \| '__/ __|
"  \ V /| | | | | | | | | (__
" (_)_/ |_|_| |_| |_|_|  \___|
"


" ========================================
"   関数定義
" ========================================
function! s:has_plugin(plugin)
  return !empty(globpath(&runtimepath, 'plugin/' . a:plugin . '.vim'))
  \   || !empty(globpath(&runtimepath, 'autoload/' . a:plugin . '.vim'))
endfunction


" ========================================
"   goda-pm.vim設定
" ========================================
if &compatible
  set nocompatible
endif

" プラグインは vim ロールが clone し、state も作る。足りないものがあれば
" プラグインを読まずに起動する。
let s:goda_pm_base = expand('~/.cache/goda-pm')
let s:goda_pm_repos = s:goda_pm_base . '/repos/github.com/'
let s:goda_pm_config = expand('~/.vim/goda-pm/main.go')
" state は runtimepath を $VIMRUNTIME ごと書き込むので、runtime ごとに分ける（vim91 など）。
" 既定の v:progname だと、vimdiff や view で起動したときに別の state を探す。vim ロールも同じ名前で作る。
let s:goda_pm_name = fnamemodify($VIMRUNTIME, ':t')

" goda.vim は Vim 9.1 の job と channel で、設定のビルドは go で動く。
function! s:goda_pm_can_make_state() abort
  return v:version >= 901 && has('job') && has('channel')
        \ && executable('go') && filereadable(s:goda_pm_config)
        \ && isdirectory(s:goda_pm_repos . 'Shougo/goda.vim')
endfunction

if v:version >= 901 && isdirectory(s:goda_pm_repos . 'Shougo/goda-pm.vim')
  execute 'set runtimepath^=' . fnameescape(s:goda_pm_repos . 'Shougo/goda-pm.vim')

  if goda_pm#min#load_state(s:goda_pm_base, s:goda_pm_name)
    " state が無いか古い。作れるときだけ作り、次の起動から効く。
    " sudo の下では goda-pm が動かないので作らない。
    if s:goda_pm_can_make_state() && !g:goda_pm._is_sudo
      execute 'set runtimepath^=' . fnameescape(s:goda_pm_repos . 'Shougo/goda.vim')
      augroup GodaPmMakeState
        autocmd!
        autocmd VimEnter * ++once
              \ call goda_pm#make_state(s:goda_pm_base, s:goda_pm_name)
        " 入っていないプラグインは state に入らない。
        autocmd User GodaPm:makeStatePost
              \ echomsg 'goda-pm: state を作りました。入っていないプラグインは'
              \ . " :call goda_pm#async_ext_action('installer', 'install') で入れて、vim を開き直してください"
      augroup END
    endif
  elseif s:goda_pm_can_make_state()
    augroup GodaPmCheckFiles
      autocmd!
      autocmd BufWritePost plugins.toml,*.go,go.mod,go.sum
            \ if !empty(goda_pm#check_files(s:goda_pm_base, s:goda_pm_name))
            \ | call goda_pm#make_state(s:goda_pm_base, s:goda_pm_name)
            \ | endif
    augroup END
  endif
endif

filetype plugin indent on


" ========================================
"   補完設定
" ========================================
" 補完候補が表示されている場合は確定。そうでない場合は改行
inoremap <expr><CR>  pumvisible() ? "\<C-y>" : "\<CR>"
" <TAB>: completion.
inoremap <expr><TAB>  pumvisible() ? "\<C-n>" : "\<TAB>"

" Enable omni completion.
autocmd FileType css           setlocal omnifunc=csscomplete#CompleteCSS
autocmd FileType html,markdown setlocal omnifunc=htmlcomplete#CompleteTags
autocmd FileType javascript    setlocal omnifunc=javascriptcomplete#CompleteJS
autocmd FileType python        setlocal omnifunc=pythoncomplete#Complete
autocmd FileType xml           setlocal omnifunc=xmlcomplete#CompleteTags


" ========================================
"   unite.vim設定
" ========================================
" 入力モードで開始する
let g:unite_enable_start_insert=1

" 元々のコマンドをなかったことに
nnoremap s <Nop>
"" 分割画面の移動
" 下
nnoremap sj <C-w>j
" 上
nnoremap sk <C-w>k
" 右
nnoremap sl <C-w>l
" 左
nnoremap sh <C-w>h
"" 画面の表示位置を移動
" 下
nnoremap sJ <C-w>J
" 上
nnoremap sK <C-w>K
" 右
nnoremap sL <C-w>L
" 左
nnoremap sH <C-w>H
" 分割画面の入れ替え
nnoremap sr <C-w>r
" 次のウインドウへ
nnoremap sw <C-w>w
" 画面の縦分割
nnoremap ss :<C-u>sp<CR>
" 画面の横分割
nnoremap sv :<C-u>vs<CR>
" 画面を閉じる
nnoremap sq :<C-u>q<CR>
" 画面を閉じてバッファからも消す
nnoremap sQ :<C-u>bd<CR>
" 画面の大きさを揃える
nnoremap s= <C-w>=
nnoremap sO <C-w>=
" 縦に最大化
nnoremap su <C-w>_
" 横に最大化
nnoremap si <C-w>|

" 次のタブへ
nnoremap sn gt
" 前のタブへ
nnoremap sp gT
" タブを開く
nnoremap st :<C-u>tabnew<CR>
" タブ一覧
nnoremap sT :<C-u>Unite tab<CR>

" 次のバッファへ
nnoremap sN :<C-u>bn<CR>
" 前のバッファへ
nnoremap sP :<C-u>bp<CR>
" 現在のタブで開いたものだけのバッファ一覧
nnoremap sB :<C-u>Unite buffer_tab -buffer-name=file<CR>
" バッファ一覧
nnoremap sb :<C-u>Unite buffer -buffer-name=file<CR>

" ファイル検索
nnoremap sf :<C-u>Unite -buffer-name=file file<CR>

" 連打できるように
if s:has_plugin('submode')
  call submode#enter_with('bufmove', 'n', '', 's>', '<C-w>>')
  call submode#enter_with('bufmove', 'n', '', 's<', '<C-w><')
  call submode#enter_with('bufmove', 'n', '', 's+', '<C-w>+')
  call submode#enter_with('bufmove', 'n', '', 's-', '<C-w>-')
  call submode#enter_with('bufmove', 'n', '', 'sw', '<C-w>w')
  call submode#map('bufmove', 'n', '', '>', '<C-w>>')
  call submode#map('bufmove', 'n', '', '<', '<C-w><')
  call submode#map('bufmove', 'n', '', '+', '<C-w>+')
  call submode#map('bufmove', 'n', '', '-', '<C-w>-')
  call submode#map('bufmove', 'n', '', 'w', '<C-w>w')
endif

" ESCキーを2回押すと終了する
autocmd FileType unite nnoremap <silent> <buffer> <ESC><ESC> :q<CR>
autocmd FileType unite inoremap <silent> <buffer> <ESC><ESC> <ESC>:q<CR>


" ========================================
"   unite-giti設定
" ========================================
if s:has_plugin('giti')
  let g:giti_log_default_line_count = 100
  "nnoremap <expr><silent> gD ':<C-u>GitiDiff ' . expand('%:p') . '<CR>'
  "nnoremap <expr><silent> gd ':<C-u>GitiDiffCached ' . expand('%:p') .  '<CR>'
  "nnoremap <silent> gf :<C-u>GitiFetch<CR>
  "nnoremap <silent> gF :<C-u>GitiFetch
  "nnoremap <expr><silent> gp ':<C-u>GitiPushWithSettingUpstream origin ' . giti#branch#current_name() . '<CR>'
  "nnoremap <silent> gP :<C-u>GitiPull<CR>
  "nnoremap <expr><silent> gl ':<C-u>GitiLogLine ' . expand('%:p') . '<CR>'
  "nnoremap <expr><silent> gL ':<C-u>GitiLog ' . expand('%:p') . '<CR>'

  "nnoremap <silent> gs :<C-u>Unite giti<CR>
  nnoremap <silent> gst :<C-u>Unite giti/status<CR>
  nnoremap <silent> gb :<C-u>Unite giti/branch<CR>
  nnoremap <silent> gB :<C-u>Unite giti/branch_all<CR>
  nnoremap <silent> gc :<C-u>Unite giti/config<CR>
  nnoremap <silent> gl :<C-u>Unite giti/log<CR>
  nnoremap <expr><silent> gL ':<C-u>Unite giti/log:' . expand('%:p') . '<CR>'
  nnoremap <silent> gG :<C-u>Unite giti/grep<CR>
endif


" ========================================
"   fugitive設定
" ========================================
if s:has_plugin('fugitive')
  nnoremap <silent> gd :<C-u>Gdiff<CR>
endif


" ========================================
"   gitv設定
" ========================================
if s:has_plugin('gitv')
  autocmd FileType git :setlocal foldlevel=99
  nnoremap <silent> gV :<C-u>Gitv<CR>
  nnoremap <silent> gv :<C-u>Gitv!<CR>
endif


" ========================================
"   emmet-vim設定
" ========================================
if s:has_plugin('emmet')
  " どのモードでコマンドを使えるようにするか
  "   n - normal
  "   i - insert
  "   v - visual
  "   a - all
  "   組み合わせ可
  let g:user_emmet_mode='a'
  " コマンド開始キー
  let g:user_emmet_leader_key='<C-e>'
  " 元々のコマンドをなかったことに
  nnoremap e <Nop>
  vnoremap e <Nop>
  " キーバインド
  " カーソル位置までのすべてを展開
  nnoremap <silent> ee :call emmet#expandAbbr(3,"")<CR>
  " 選択範囲を囲むタグを作成
  vnoremap <silent> er :call emmet#expandAbbr(2,"")<CR>
  " 一つのタグのみを展開
  nnoremap <silent> ew :call emmet#expandAbbr(1,"")<CR>
  " タグの削除
  nnoremap <silent> ed :call emmet#removeTag()<CR>
  " コメントアウト/解除
  nnoremap <silent> ec :call emmet#toggleComment()<CR>
  " 選択範囲を一行にする
  vnoremap <silent> em :call emmet#mergeLines()<CR>
  " 中身のない次/前のタグ内で挿入モードに
  nnoremap <silent> en :call emmet#moveNextPrev(0)<CR>
  nnoremap <silent> eN :call emmet#moveNextPrev(1)<CR>
endif


" ========================================
"   vim-jsx設定
" ========================================
"  拡張子をjsxに限定するか
"    0 - しない
"    1 - する
let g:jsx_ext_required = 0


" ========================================
"   キーバインド
" ========================================
" 行頭へ移動
noremap h ^
" 行末へ移動
noremap l $
" ハイライトを消す
nnoremap <silent> <ESC><ESC> :noh<CR>


" ========================================
"   ハイライト設定
" ========================================
augroup SyntaxHighlights
  autocmd!
  " coffee
  autocmd BufRead,BufNewFile,BufReadPre *.coffee set filetype=coffee
  " riot tag
  autocmd BufRead,BufNewFile,BufReadPre *.tag set filetype=tag
  " cson
  autocmd BufRead,BufNewFile,BufReadPre *.cson set filetype=coffee
augroup END


" ========================================
"   カラースキーム設定
" ========================================
set background=dark
" solarized が入る前は既定の配色で起動する。
try
  colorscheme solarized
catch /^Vim\%((\a\+)\)\=:E185:/
endtry
"let g:solarized_termcolors=256
"let g:rehash256 = 1
set t_Co=256
syntax on


" ========================================
"   表示設定
" ========================================
" 非表示文字を表示
set list
" 非表示文字の表示内容を設定
"   tab   - タブ文字を表示
"   trail - 行末のスペースを表示
"   nbsp  - ノーブレークスペースを表示
"   eol   - 改行を表示
set listchars=tab:»-
" 行番号を表示
set number
" 現在行をハイライト表示
set cursorline
" 行末空白文字もしくは全角空白をハイライト表示
if has('syntax')
  augroup HighlightTrailingSpaces
    autocmd!
    autocmd VimEnter,WinEnter,Colorscheme * highlight Spaces term=underline guibg=Red ctermbg=Red
    autocmd VimEnter,WinEnter * match Spaces /\(\s\+$\|　\)/
  augroup END
endif


" ========================================
"   検索設定
" ========================================
set ignorecase
set smartcase
set wrapscan
set hlsearch


" ========================================
"   タブ幅設定
" ========================================
set tabstop=2
set expandtab
set smarttab
set shiftwidth=2
set shiftround
set wrap


" ========================================
"   インデント設定
" ========================================
set autoindent
set showmatch


" ========================================
"   undo設定
" ========================================
set undofile
set undodir=$HOME/.vim/undo


" ========================================
"   Statuslineの設定
" ========================================
set laststatus=2
if s:has_plugin('fugitive')
  set statusline=%<%f\ %h%m%r%{fugitive#statusline()}%=%-14.(%l,%c%V%)\ \[ENC=%{&fileencoding}]%P
endif


" ========================================
"   その他設定
" ========================================
" 普通にバックスペースできるように
set backspace=indent,eol,start

" 行末空白文字の削除
augroup RemoveTwoByteSpaces
  autocmd!
  autocmd BufWritePre * :%s/\(\s\|　\)\+$//ge
augroup END

" ファイル読み込み時にscreenタブの内容を書き換える
augroup RenameScreenTabTitle
  autocmd!
  autocmd BufEnter * if @% == '' | :silent exec "!echo -ne '\ekvi anonymous buffer\e\\'" | else | :silent exec "!echo -ne '\ekvi <afile>\e\\'" | endif
augroup END


