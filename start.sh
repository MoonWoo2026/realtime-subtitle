#!/bin/bash
# 纯静态版：Python http.server + cloudflared tunnel
# 彻底用 nohup 脱离终端，不会被 shell 关闭杀死

cd "$(dirname "$0")"
PORT=5001
CF_BIN=/Users/moonwoo/.local/bin/cloudflared

# 清理旧进程
pkill -f "http.server $PORT" 2>/dev/null
pkill -f cloudflared 2>/dev/null
sleep 1

# 1. 启动静态文件服务器（不依赖 Flask 了！）
nohup python3 -m http.server $PORT --bind 0.0.0.0 > /tmp/httpd.log 2>&1 &
HTTPD_PID=$!
disown $HTTPD_PID
sleep 2

if ! curl -s -o /dev/null http://127.0.0.1:$PORT/; then
    echo "[FAIL] http.server 未启动"
    exit 1
fi

# 2. 启动 cloudflared tunnel
nohup $CF_BIN tunnel --url http://localhost:$PORT --no-autoupdate > /tmp/cf.log 2>&1 &
CF_PID=$!
disown $CF_PID
sleep 8

TUNNEL_URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf.log | head -1)
if [ -z "$TUNNEL_URL" ]; then
    echo "[FAIL] Tunnel 未创建"
    tail -5 /tmp/cf.log
    exit 1
fi

echo "=========================================="
echo "  实时字幕翻译 - 公网链接"
echo "  $TUNNEL_URL"
echo "=========================================="

# 3. Watchdog（独立后台进程）
(
while true; do
    sleep 20
    # 检查 http.server
    if ! curl -s -o /dev/null http://127.0.0.1:$PORT/; then
        pkill -f "http.server $PORT" 2>/dev/null
        sleep 1
        nohup python3 -m http.server $PORT --bind 0.0.0.0 >> /tmp/httpd.log 2>&1 &
        disown
    fi
    # 检查 cloudflared
    if ! curl -s -o /dev/null --max-time 8 "$TUNNEL_URL"; then
        pkill -f cloudflared 2>/dev/null
        sleep 2
        nohup $CF_BIN tunnel --url http://localhost:$PORT --no-autoupdate >> /tmp/cf.log 2>&1 &
        disown
        sleep 8
        NEW_URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf.log | tail -1)
        if [ -n "$NEW_URL" ] && [ "$NEW_URL" != "$TUNNEL_URL" ]; then
            TUNNEL_URL="$NEW_URL"
            echo ""
            echo "=========================================="
            echo "  Tunnel 已重建，请使用新链接："
            echo "  $NEW_URL"
            echo "=========================================="
            echo ""
        fi
    fi
done
) > /tmp/watchdog.log 2>&1 &
disown

echo "  Watchdog 已在后台启动"
echo "  关闭终端不会影响服务"
echo "=========================================="
