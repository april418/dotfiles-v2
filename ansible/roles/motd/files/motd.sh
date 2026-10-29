#!/bin/bash

#                  _      _       _
#  _ __ ___   ___ | |_ __| |  ___| |__
# | '_ ` _ \ / _ \| __/ _` | / __| '_ \
# | | | | | | (_) | || (_| |_\__ \ | | |
# |_| |_| |_|\___/ \__\__,_(_)___/_| |_|
#
#

terminal_columns() {
  # pam_motd runs this with an empty environment (no TERM), where tput fails.
  tput cols 2>/dev/null || echo 80
}

br() {
  local columns=$(terminal_columns)
  local i=0
  for ((i = 0; i < columns; i++)); do
    printf "-"
  done
  printf "\n"
}

text_center() {
  local columns=$(terminal_columns)
  local line=
  if [ -p /dev/stdin ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      printf "%*s\n" $(((${#line} + columns) / 2)) "$line"
    done </dev/stdin
  else
    line="$@"
    printf "%*s\n" $(((${#line} + columns) / 2)) "$line"
  fi
}

max_length() {
  local length=
  local max_length=0
  local line=
  if [ -p /dev/stdin ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      length=${#line}
      if [ $length -gt $max_length ]; then
        max_length=$length
      fi
    done </dev/stdin
    echo $max_length
  else
    line="$@"
    echo ${#line}
  fi
}

with_indent() {
  local length="$1"
  local line=
  local indent=
  local i=
  for ((i = 0; i < length; i++)); do
    indent="$indent "
  done
  if [ -p /dev/stdin ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      echo "${indent}${line}"
    done </dev/stdin
  else
    shift
    line="$@"
    echo "${indent}${#line}"
  fi
}

display_center() {
  local columns=$(terminal_columns)
  local length=$(echo "$@" | max_length)
  echo "$@" | with_indent "$(((columns - length) / 2))"
}

get_ipaddress() {
  #ifconfig eth0 | sed -n -e 's/^ *inet addr:\([0-9.]\+\).*$/\1/p'
  #hostname -I | cut -f1 -d' '
  # The interface name varies by host (eth0, ens4),
  # so take the source address of the route to an external host.
  ip -4 -o route get 1.1.1.1 2>/dev/null | sed -n -e 's/^.* src \([0-9.]*\).*$/\1/p'
}

blue="[034m"
cyan="[036m"
default="[0m"
ipaddress="$(get_ipaddress | figlet)"
hostname="$(hostname | figlet)"

echo
br
echo "${cyan}$(display_center "$ipaddress")${default}"
echo "${blue}$(display_center "$hostname")${default}"
echo
text_center 'Wellcome to development server!!'
text_center 'Enjoy your development!!'
echo
br
echo
