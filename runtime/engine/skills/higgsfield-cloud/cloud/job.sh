#!/usr/bin/env bash
# job.sh — named jobs with state/log/progress, built for sandbox_exec background:true (15-min cap per call).
#   job.sh run NAME -- CMD...   run CMD now and wait (the sandbox_exec call itself is background:true)
#   job.sh status [NAME]        one line per job: state, elapsed, progress %, ETA, exit, last log line
#   job.sh tail NAME [N]        last N log lines (default 20)
#   job.sh stop NAME            kill the job and its children
#   job.sh list                 job names
# State lives in ~/hfc_jobs/NAME/{state,pid,start,end,exit,cmd,log,progress,total_us}.
# Commands that understand $HFC_JOB_DIR (hfc enc/whisper/html2mp4) write progress there.
set -uo pipefail
J=${HFC_JOBS:-$HOME/hfc_jobs}; mkdir -p "$J"
sub=${1:-status}; shift || true
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
line() {
  local d=$1 n st pid s e x el pct="" eta="" last
  n=$(basename "$d"); st=$(cat "$d/state" 2>/dev/null || echo "?"); pid=$(cat "$d/pid" 2>/dev/null)
  s=$(cat "$d/start" 2>/dev/null || echo 0); e=$(cat "$d/end" 2>/dev/null || date +%s); x=$(cat "$d/exit" 2>/dev/null || echo "-")
  [ "$st" = running ] && ! alive "$pid" && st="lost(sandbox replaced or killed)"
  el=$(( e - s ))
  if [ -s "$d/total_us" ] && [ -s "$d/progress" ]; then
    local tot cur; tot=$(cat "$d/total_us"); cur=$(grep -E '^out_time_us=[0-9]+' "$d/progress" | tail -1 | cut -d= -f2)
    if [ -n "$cur" ] && [ "$tot" -gt 0 ] 2>/dev/null; then
      pct=$(awk "BEGIN{p=$cur/$tot*100; if(p>100)p=100; printf \"%.0f\", p}")
      [ "$st" = running ] && [ "$cur" -gt 0 ] && eta=$(awk "BEGIN{printf \"%.0f\", $el*($tot-$cur)/$cur}")
    fi
  fi
  last=$(grep -v '^\s*$' "$d/log" 2>/dev/null | tail -1 | tr -d '\r' | cut -c1-140)
  printf '%-18s %-9s %5ss %s%s exit=%s | %s\n' "$n" "$st" "$el" "${pct:+$pct% }" "${eta:+eta=${eta}s }" "$x" "$last"
}
case "$sub" in
  run)
    name=${1:?NAME}; shift; [ "${1:-}" = "--" ] && shift
    [ $# -ge 1 ] || { echo "job run: missing command" >&2; exit 2; }
    d="$J/$name"; mkdir -p "$d"
    if [ "$(cat "$d/state" 2>/dev/null)" = running ] && alive "$(cat "$d/pid" 2>/dev/null)"; then
      echo "job $name is already running (hfc job status $name)" >&2; exit 3; fi
    rm -f "$d"/{end,exit,progress,total_us}; : > "$d/log"
    echo running > "$d/state"; echo $$ > "$d/pid"; date +%s > "$d/start"; printf '%q ' "$@" > "$d/cmd"
    export HFC_JOB_DIR="$d"
    "$@" >> "$d/log" 2>&1; rc=$?
    date +%s > "$d/end"; echo $rc > "$d/exit"
    [ $rc = 0 ] && echo done > "$d/state" || echo failed > "$d/state"
    line "$d"; tail -n 5 "$d/log"; exit $rc ;;
  status)
    if [ -n "${1:-}" ]; then [ -d "$J/$1" ] || { echo "no job $1"; exit 1; }; line "$J/$1"
    else found=0; for d in "$J"/*/; do [ -d "$d" ] && { line "${d%/}"; found=1; }; done; [ $found = 1 ] || echo "no jobs"; fi ;;
  tail) tail -n "${2:-20}" "$J/${1:?NAME}/log" ;;
  stop)
    d="$J/${1:?NAME}"; pid=$(cat "$d/pid" 2>/dev/null)
    killtree() { local c; for c in $(pgrep -P "$1" 2>/dev/null); do killtree "$c"; done; kill -TERM "$1" 2>/dev/null; }
    if alive "$pid"; then killtree "$pid"; sleep 1
      echo stopped > "$d/state"; date +%s > "$d/end"; echo "stopped $1"; else echo "$1 not running"; fi ;;
  list) ls -1 "$J" 2>/dev/null ;;
  *) echo "job.sh: run|status|tail|stop|list" >&2; exit 2 ;;
esac
