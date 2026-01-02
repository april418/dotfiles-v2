#!/bin/bash

#                  _      _       _
#  _ __ ___   ___ | |_ __| |  ___| |__
# | '_ ` _ \ / _ \| __/ _` | / __| '_ \
# | | | | | | (_) | || (_| |_\__ \ | | |
# |_| |_| |_|\___/ \__\__,_(_)___/_| |_|
#
#

br() {
  local columns=$(tput cols)
  local i=0
  for ((i=0; i < columns; i++)); do
    printf "-"
  done
  printf "\n"
}

text_center() {
  local columns=$(tput cols)
  local line=
  if [ -p /dev/stdin ]; then
    while IFS= read -r line  || [ -n "$line" ]; do
      printf "%*s\n" $(( (${#line} + columns) / 2)) "$line"
    done < /dev/stdin
  else
    line="$@"
    printf "%*s\n" $(( (${#line} + columns) / 2)) "$line"
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
    done < /dev/stdin
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
  for ((i=0; i < length; i++)); do
    indent="$indent "
  done
  if [ -p /dev/stdin ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      echo "${indent}${line}"
    done < /dev/stdin
  else
    shift
    line="$@"
    echo "${indent}${#line}"
  fi
}

display_center() {
  local columns=$(tput cols)
  local length=$(echo "$@" | max_length)
  echo "$@" | with_indent "$(((columns - length) / 2))"
}

get_ipaddress() {
  #ifconfig eth0 | sed -n -e 's/^ *inet addr:\([0-9.]\+\).*$/\1/p'
  #hostname -I | cut -f1 -d' '
  ip -f inet -o addr show eth0 | sed -n -e 's/^.\+eth0 \+inet \([0-9.]\+\).*$/\1/p'
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

