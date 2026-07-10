#!/usr/bin/env bash
# ============================================================
#  The Narrative - boot intro (macOS / Linux, bash)
#  Glitch "hacker uplink" theatre that greets: hello mithra
#  Hacker-movie aesthetic only - no third-party brand names.
#  Fast (~2-3s). Mirrors scripts/boot_intro.ps1 exactly.
# ============================================================

ESC=$'\033'
GRN="${ESC}[38;5;46m"   # bright green
CYN="${ESC}[38;5;51m"   # cyan
DIM="${ESC}[38;5;28m"   # dim green
RST="${ESC}[0m"

printf '%s' "${ESC}[2J${ESC}[H"   # clear + home

# --- glitch flicker before the logo locks in ---
chars='#@%&*!?01<>/\|[]__--==~~^'
for i in 1 2 3 4 5; do
  line=""
  for _ in $(seq 1 46); do
    line="${line}${chars:$((RANDOM % ${#chars})):1}"
  done
  printf '%s%s%s\n' "$DIM" "$line" "$RST"
  sleep 0.04
done

# --- MITHRA banner (same art as Windows) ---
printf '\n'
banner=(
' __  __ ___ _____ _   _ ____      _    '
'|  \/  |_ _|_   _| | | |  _ \    / \   '
'| |\/| || |  | | | |_| | |_) |  / _ \  '
'| |  | || |  | | |  _  |  _ <  / ___ \ '
'|_|  |_|___| |_| |_| |_|_| \_\/_/   \_\'
)
for row in "${banner[@]}"; do
  printf '%s%s%s\n' "$CYN" "$row" "$RST"
  sleep 0.035
done
printf '%s        t h e   n a r r a t i v e   b e t a%s\n\n' "$DIM" "$RST"
sleep 0.12

# --- typewriter boot log ---
type_line() {  # $1 = color, $2 = text
  printf '%s> %s' "$GRN" "$1"
  local text="$2" i ch
  for (( i=0; i<${#text}; i++ )); do
    ch="${text:$i:1}"
    printf '%s' "$ch"
    sleep 0.012
  done
  printf '%s\n' "$RST"
  sleep 0.09
}
type_line "$CYN" "hello mithra"
type_line "$GRN" "establishing secure uplink..."
type_line "$GRN" "decrypting world feed..."
type_line "$GRN" "syncing consequence graph..."

# --- progress bar ---
printf '\n'
for p in $(seq 0 5 100); do
  filled=$((p / 5))
  bar=""
  for (( i=0; i<20; i++ )); do
    if [ "$i" -lt "$filled" ]; then bar="${bar}#"; else bar="${bar}."; fi
  done
  printf '\r%s> [%s%s%s] %s%%  %s' "$GRN" "$CYN" "$bar" "$GRN" "$p" "$RST"
  sleep 0.025
done
printf '\n\n'
sleep 0.1
printf '%s  +----------------------------------------+%s\n' "$GRN" "$RST"
printf '%s  |    %s ACCESS GRANTED %s                      |%s\n' "$GRN" "$CYN" "$GRN" "$RST"
printf '%s  +----------------------------------------+%s\n' "$GRN" "$RST"
sleep 0.25
printf '%s' "$RST"
