#!/usr/bin/env bash
# Match3 web 對外服務開關：本機 http.server(8787) + Cloudflare quick tunnel
# 用 launchctl 跑成使用者層級背景服務，跟終端機完全脫鉤
# 用法: ./serve_web.sh start|stop|status|url
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN=/tmp/match3_serve
PORT=8787
L_HTTP=com.match3.http
L_TUNNEL=com.match3.tunnel
mkdir -p "$RUN"

get_url() { grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/tunnel.log" 2>/dev/null | head -1; }

start() {
  stop >/dev/null 2>&1 || true
  rm -f "$RUN/tunnel.log"
  launchctl submit -l $L_HTTP -o "$RUN/http.log" -e "$RUN/http.log" \
    -- "$(command -v python3)" -m http.server $PORT --directory "$ROOT"
  launchctl submit -l $L_TUNNEL -o "$RUN/tunnel.log" -e "$RUN/tunnel.log" \
    -- "$(command -v cloudflared)" tunnel --url "http://localhost:$PORT"
  printf '等待 tunnel 網址'
  url=""
  for _ in $(seq 1 30); do
    url=$(get_url) || true
    if [ -n "$url" ]; then break; fi
    printf .; sleep 1
  done
  echo
  if [ -z "$url" ]; then echo "拿不到網址，看 $RUN/tunnel.log"; exit 1; fi
  echo "本機:  http://localhost:$PORT/web_game/index.html?theme=deo_cat_ip"
  echo "外網:  $url/web_game/index.html?theme=deo_cat_ip"
}

stop() {
  launchctl remove $L_HTTP 2>/dev/null && echo "stopped http" || true
  launchctl remove $L_TUNNEL 2>/dev/null && echo "stopped tunnel" || true
  # 收掉不是 launchctl 管的殘留程序
  pkill -f "http.server $PORT" 2>/dev/null || true
  pkill -f "cloudflared tunnel --url http://localhost:$PORT" 2>/dev/null || true
}

status() {
  for l in $L_HTTP $L_TUNNEL; do
    if launchctl list "$l" >/dev/null 2>&1; then echo "$l: running"; else echo "$l: stopped"; fi
  done
  url=$(get_url) || true
  if [ -n "$url" ]; then echo "外網: $url/web_game/index.html?theme=deo_cat_ip"; fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  url) get_url ;;
  *) echo "用法: $0 start|stop|status|url"; exit 1 ;;
esac
