#!/bin/bash

# Claude Code statusline script
# Receives JSON via $CLAUDE_STATUSLINE_DATA

DATA="$CLAUDE_STATUSLINE_DATA"

if [ -z "$DATA" ]; then
  exit 0
fi

# Parse JSON fields
model=$(echo "$DATA" | jq -r '.model // ""')
context_used=$(echo "$DATA" | jq -r '.contextWindow.used // 0')
context_total=$(echo "$DATA" | jq -r '.contextWindow.total // 1')
cost=$(echo "$DATA" | jq -r '.cost.usd // 0')
duration=$(echo "$DATA" | jq -r '.duration.formatted // ""')
git_branch=$(echo "$DATA" | jq -r '.git.branch // ""')
git_staged=$(echo "$DATA" | jq -r '.git.staged // 0')
git_modified=$(echo "$DATA" | jq -r '.git.modified // 0')
rate_5h=$(echo "$DATA" | jq -r '.rateLimit.fiveHour.percentUsed // empty' 2>/dev/null)
rate_7d=$(echo "$DATA" | jq -r '.rateLimit.sevenDay.percentUsed // empty' 2>/dev/null)
workspace=$(echo "$DATA" | jq -r '.workspace.directory // ""')

# Colors
RESET="\033[0m"
GRAY="\033[90m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
MAGENTA="\033[35m"
RED="\033[31m"

# Context percentage & color
if [ "$context_total" -gt 0 ] 2>/dev/null; then
  context_pct=$((context_used * 100 / context_total))
else
  context_pct=0
fi

if [ "$context_pct" -ge 80 ]; then
  ctx_color="$RED"
elif [ "$context_pct" -ge 50 ]; then
  ctx_color="$YELLOW"
else
  ctx_color="$GREEN"
fi

# Build progress bar
bar_width=10
filled=$((context_pct * bar_width / 100))
empty=$((bar_width - filled))
bar=$(printf '%0.s█' $(seq 1 $filled 2>/dev/null))
bar_empty=$(printf '%0.s░' $(seq 1 $empty 2>/dev/null))

# Line 1: Model + Context
line1="${CYAN}${model}${RESET} ${GRAY}│${RESET} ${ctx_color}${bar}${bar_empty} ${context_pct}%${RESET}"

# Line 2: Git + Workspace
line2=""
if [ -n "$git_branch" ]; then
  git_info="${MAGENTA}${git_branch}${RESET}"
  if [ "$git_staged" -gt 0 ] || [ "$git_modified" -gt 0 ]; then
    git_info="${git_info} ${GREEN}+${git_staged}${RESET} ${YELLOW}~${git_modified}${RESET}"
  fi
  line2="${git_info}"
fi

if [ -n "$workspace" ]; then
  ws_short=$(basename "$workspace")
  if [ -n "$line2" ]; then
    line2="${line2} ${GRAY}│${RESET} ${GRAY}${ws_short}${RESET}"
  else
    line2="${GRAY}${ws_short}${RESET}"
  fi
fi

# Line 3: Cost + Duration + Rate limit
line3="${GRAY}\$${cost}${RESET} ${GRAY}│${RESET} ${GRAY}${duration}${RESET}"

if [ -n "$rate_5h" ]; then
  rate_5h_int=${rate_5h%.*}
  if [ "${rate_5h_int:-0}" -ge 80 ]; then
    rate_color="$RED"
  elif [ "${rate_5h_int:-0}" -ge 50 ]; then
    rate_color="$YELLOW"
  else
    rate_color="$GREEN"
  fi
  line3="${line3} ${GRAY}│${RESET} ${rate_color}5h:${rate_5h_int}%${RESET}"
fi

if [ -n "$rate_7d" ]; then
  rate_7d_int=${rate_7d%.*}
  if [ "${rate_7d_int:-0}" -ge 80 ]; then
    rate7_color="$RED"
  elif [ "${rate_7d_int:-0}" -ge 50 ]; then
    rate7_color="$YELLOW"
  else
    rate7_color="$GREEN"
  fi
  line3="${line3} ${rate7_color}7d:${rate_7d_int}%${RESET}"
fi

echo -e "$line1"
echo -e "$line2"
echo -e "$line3"
