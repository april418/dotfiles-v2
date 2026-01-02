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
"   NeoBundle設定
" ========================================
" Note: Skip initialization for vim-tiny or vim-small.
if 0 | endif

if &compatible
  set nocompatible               " Be iMproved
endif

" Required:
set runtimepath+=~/.vim/bundle/neobundle.vim/

" Required:
call neobundle#begin(expand('~/.vim/bundle/'))
  " Let NeoBundle manage NeoBundle
  " Required:
  NeoBundleFetch 'Shougo/neobundle.vim'

  " My Bundles here:
  " Refer to |:NeoBundle-examples|.
  " Note: You don't set neobundle setting in .gvimrc!
  NeoBundle 'Shougo/neocomplete'
  NeoBundle 'Shougo/unite.vim'
  NeoBundle 'Shougo/neomru.vim'
  NeoBundle 'Shougo/neosnippet'
  NeoBundle 'Shougo/neosnippet-snippets'
  NeoBundle 'altercation/vim-colors-solarized'
  NeoBundle 'powerline/powerline', {'rtp': 'powerline/bindings/vim/'}
  NeoBundle 'tpope/vim-fugitive'
  NeoBundle 'kmnk/vim-unite-giti'
  NeoBundle 'gregsexton/gitv'
  NeoBundle 'kana/vim-submode'
  NeoBundle 'kchmck/vim-coffee-script'
  NeoBundle 'ryym/vim-riot'
  NeoBundle 'digitaltoad/vim-pug'
  NeoBundle 'wavded/vim-stylus'
  NeoBundle 'pangloss/vim-javascript'
  NeoBundle 'jelera/vim-javascript-syntax'
  NeoBundle 'mxw/vim-jsx'
  NeoBundle 'mattn/emmet-vim'
  NeoBundle 'editorconfig/editorconfig-vim'
  NeoBundle 'lumiliet/vim-twig'
  NeoBundle 'Glench/Vim-Jinja2-Syntax'
  NeoBundle 'posva/vim-vue'
call neobundle#end()

" Required:
filetype plugin indent on

" If there are uninstalled bundles found on startup,
" this will conveniently prompt you to install them.
NeoBundleCheck


" ========================================
"   NeoComplete設定
" ========================================
" Note: This option must be set in .vimrc(_vimrc).  NOT IN .gvimrc(_gvimrc)!
" Disable AutoComplPop.
let g:acp_enableAtStartup = 0
" Use neocomplete.
let g:neocomplete#enable_at_startup = 1
" Use smartcase.
let g:neocomplete#enable_smart_case = 1
" Set minimum syntax keyword length.
let g:neocomplete#sources#syntax#min_keyword_length = 3
let g:neocomplete#lock_buffer_name_pattern = '\*ku\*'

" Define dictionary.
let g:neocomplete#sources#dictionary#dictionaries = {
  \ 'default' : '',
  \ 'vimshell' : $HOME.'/.vimshell_hist',
  \ 'scheme' : $HOME.'/.gosh_completions'
  \ }

" Define keyword.
if !exists('g:neocomplete#keyword_patterns')
  let g:neocomplete#keyword_patterns = {}
endif
let g:neocomplete#keyword_patterns['default'] = '\h\w*'

" Plugin key-mappings.
inoremap <expr><C-g> neocomplete#undo_completion()
inoremap <expr><C-l> neocomplete#complete_common_string()

" Recommended key-mappings.
" <CR>: close popup and save indent.
inoremap <silent> <CR> <C-r>=<SID>my_cr_function()<CR>
function! s:my_cr_function()
  return (pumvisible() ? "\<C-y>" : "" ) . "\<CR>"
  " For no inserting <CR> key.
  "return pumvisible() ? "\<C-y>" : "\<CR>"
endfunction
" <TAB>: completion.
inoremap <expr><TAB>  pumvisible() ? "\<C-n>" : "\<TAB>"
" <C-h>, <BS>: close popup and delete backword char.
inoremap <expr><C-h> neocomplete#smart_close_popup()."\<C-h>"
inoremap <expr><BS> neocomplete#smart_close_popup()."\<C-h>"
" Close popup by <Space>.
"inoremap <expr><Space> pumvisible() ? "\<C-y>" : "\<Space>"

" 補完候補が表示されている場合は確定。そうでない場合は改行
inoremap <expr><CR>  pumvisible() ? neocomplete#close_popup() : "<CR>"

" AutoComplPop like behavior.
"let g:neocomplete#enable_auto_select = 1

" Shell like behavior(not recommended).
"set completeopt+=longest
"let g:neocomplete#enable_auto_select = 1
"let g:neocomplete#disable_auto_complete = 1
"inoremap <expr><TAB>  pumvisible() ? "\<Down>" : "\<C-x>\<C-u>"

" Enable omni completion.
autocmd FileType css           setlocal omnifunc=csscomplete#CompleteCSS
autocmd FileType html,markdown setlocal omnifunc=htmlcomplete#CompleteTags
autocmd FileType javascript    setlocal omnifunc=javascriptcomplete#CompleteJS
autocmd FileType python        setlocal omnifunc=pythoncomplete#Complete
autocmd FileType xml           setlocal omnifunc=xmlcomplete#CompleteTags

" Enable heavy omni completion.
if !exists('g:neocomplete#sources#omni#input_patterns')
  let g:neocomplete#sources#omni#input_patterns = {}
endif
"let g:neocomplete#sources#omni#input_patterns.php = '[^. \t]->\h\w*\|\h\w*::'
"let g:neocomplete#sources#omni#input_patterns.c = '[^.[:digit:] *\t]\%(\.\|->\)'
"let g:neocomplete#sources#omni#input_patterns.cpp = '[^.[:digit:] *\t]\%(\.\|->\)\|\h\w*::'

" For perlomni.vim setting.
" https://github.com/c9s/perlomni.vim
"let g:neocomplete#sources#omni#input_patterns.perl = '\h\w*->\h\w*\|\h\w*::'


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
colorscheme solarized
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
if !s:has_plugin('powerline') && s:has_plugin('fugitive')
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


