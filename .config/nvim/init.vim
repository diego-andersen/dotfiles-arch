" Just in case -C happens
if &compatible
  set nocompatible
endif

" Plugin manager
call plug#begin('~/.local/share/plugged')

" Appearance
Plug 'chriskempson/base16-vim'
Plug 'itchyny/lightline.vim'

" IDE
Plug 'scrooloose/nerdtree'
Plug 'sheerun/vim-polyglot'
Plug 'tmhedberg/SimpylFold'
Plug 'ctrlpvim/ctrlp.vim'

call plug#end()

"Use 24-bit (true-color) mode in Vim/Neovim when outside tmux.
if (has("termguicolors"))
  set termguicolors
endif

" Color scheme

" Python imports should be the same colour as keywords, not functions
function! s:base16_customize() abort
  call Base16hi("pythonImport", g:base16_gui0E, "", g:base16_cterm0E, "")
  call Base16hi("Normal", "", "NONE", "", "NONE")
  call Base16hi("LineNr", "", "NONE", "", "NONE")
endfunction

augroup on_change_colorschema
  autocmd!
  autocmd ColorScheme base16* call s:base16_customize()
augroup END

syntax enable
colorscheme base16-tomorrow
set background=light

" Lightline options
let g:lightline = {
    \ 'colorscheme': 'one',
    \ 'active': {
    \   'left': [['mode', 'paste'], ['readonly', 'absolutepath', 'modified']]
    \ }
\ }

" General options
set encoding=utf-8
set noshowmode      " Don't show Vim mode in input bar (Airline already does)
set showcmd         " Show last typed command in status bar
set autoread        " Auto-reload open file when external changes are made

" Appearance
set number	        " Show line numbers
set relativenumber  " Show line numbers relative to current line
set nowrap	        " Don't wrap lines
set wildmenu	    " Visual auto-complete menu on tab
set showmatch	    " Highlight matching brackets

" Indentation
set tabstop=4		" One TAB = X spaces
set softtabstop=4	" Convert TAB to X spaces during editing operations
set shiftwidth=4    " One indent level = X spaces
set expandtab		" Replace tab characters with spaces in insert mode
set autoindent      " Auto-indent on newline

" Pane splitting behaviour
set splitbelow splitright

" Disable automatic commenting on newline
autocmd FileType * setlocal formatoptions-=c formatoptions-=r formatoptions-=o

" Auto-reload config on write
autocmd bufwritepost init.vim source ~/.config/nvim/init.vim

" Search
set hlsearch	" Highlight search matches
set incsearch	" Highlight search results as you type

" Delete trailing whitespace on save
autocmd BufWritePre * %s/\s\+$//e

" KEYBINDS

" Single-keypress pane navigation
nnoremap <C-h> <C-w><C-h>
nnoremap <C-j> <C-w><C-j>
nnoremap <C-k> <C-w><C-k>
nnoremap <C-l> <C-w><C-l>

" Enter clears search result highlighting
nnoremap <silent> <CR> :noh<CR><CR>

" LANGUAGE-SPECIFIC BEHAVIOUR

" JSON
au BufNewFile,BufRead *.json
    \ | setlocal tabstop=2
    \ | setlocal softtabstop=2
    \ | setlocal shiftwidth=2
