#    _               _                           __ _ _
#   | |__   __ _ ___| |__       _ __  _ __ ___  / _(_) | ___
#   | '_ \ / _` / __| '_ \     | '_ \| '__/ _ \| |_| | |/ _ \
#  _| |_) | (_| \__ \ | | |    | |_) | | | (_) |  _| | |  __/
# (_)_.__/ \__,_|___/_| |_|____| .__/|_|  \___/|_| |_|_|\___|
#                        |_____|_|
#

# User specific environment and startup programs
PATH="$PATH:$HOME/.local/bin"
export PATH

# rbenv
if [ -d ~/.rbenv ]; then
  export PATH="$HOME/.rbenv/bin:$PATH"
  eval "$($HOME/.rbenv/bin/rbenv init -)"
fi

# nvm
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

# Package registry (Flatt Security Guard)
# Token: override UV_DEFAULT_INDEX in ~/.bash_profile.local
#   export UV_DEFAULT_INDEX="https://token:tg_anon_xxx@pypi.flatt.tech/simple/"
export NPM_CONFIG_REGISTRY="https://npm.flatt.tech"
export UV_DEFAULT_INDEX="https://pypi.flatt.tech/simple/"

# Load .bash_profile.local if it exists
if [ -f ~/.bash_profile.local ]; then
  source ~/.bash_profile.local
fi

# Get the aliases and functions
if [ -f ~/.bashrc ]; then
  source ~/.bashrc
fi
