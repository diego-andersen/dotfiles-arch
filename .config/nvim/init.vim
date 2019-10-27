" Just in case -C happens
if &compatible
  set nocompatible
endif

" Plugin manager
call plug#begin('~/.local/share/plugged')

" Appearance
Plug 'joshdick/onedark.vim'
Plug 'itchyny/lightline.vim'

" IDE
Plug 'scrooloose/nerdtree'
Plug 'sheerun/vim-polyglot'
Plug 'tmhedberg/SimpylFold'
Plug 'kien/ctrlp.vim'

call plug#end()

"Use 24-bit (true-color) mode in Vim/Neovim when outside tmux.
if (has("termguicolors"))
  set termguicolors
endif

" onedark.vim override: Don't set a background color when running in a terminal.
" `gui` is the hex color code used in GUI mode/nvim true-color mode
" `cterm` is the color code used in 256-color mode
" `cterm16` is the color code used in 16-color mode
if (has("autocmd") && !has("gui_running"))
  augroup colorset
    autocmd!
    let s:colors = onedark#GetColors()
    let s:black = s:colors.black
    let s:white = s:colors.white
    autocmd ColorScheme * call onedark#set_highlight("Normal", { "fg": s:white })
    autocmd ColorScheme * call onedark#set_highlight("Visual", { "fg": s:black, "bg": s:white })
  augroup END
endif

" General options
set encoding=utf-8
set noshowmode
set showcmd	" Show last typed command in status bar

" Color scheme
syntax on
colorscheme onedark
let g:onedark_terminal_italics = 1
let g:lightline = {'colorscheme': 'onedark'}

" Pane splitting behaviour
set splitbelow
set splitright

" Pane navigation
nnoremap <C-J> <C-W><C-J>
nnoremap <C-K> <C-W><C-K>
nnoremap <C-L> <C-W><C-L>
nnoremap <C-H> <C-W><C-H>

" Indentation
set tabstop=4		" Pressing TAB inserts X spaces
set softtabstop=4	" Convert tabs to X spaces
set shiftwidth=4    " One indent level = one tab
set expandtab		" Replace tabs with spaces
set autoindent

" Appearance
set number	    " Show line numbers
set nowrap	    " Don't wrap lines
set ruler	    " Show cursor line/col position
set wildmenu	" Visual auto-complete menu on tab
set showmatch	" Highlight matching brackets

" Search
set hlsearch	" Highlight search matches
set incsearch	" Highlight search results as you type
nnoremap <silent> <CR> :noh<CR><CR>

" Python-specific behaviour
au BufNewFile,BufRead *.py
    \ | setlocal tabstop=4
    \ | setlocal softtabstop=4
    \ | setlocal shiftwidth=4
    \ | setlocal expandtab
    \ | setlocal autoindent
    \ | setlocal fileformat=unix
