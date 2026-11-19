#!/bin/bash
# macOS 双击启动 - LaunchAgent 方式
cd "$(dirname "$0")"

PORT=5001
CF=/Users/moonwoo/.local/bin/cloudflared

# 清理旧进程
pkill -9 -f cloudflared 2>/dev/null
pkill -9 -f "http.server $PORT" 2>/dev/null
sleep 1

# 启动 http.server
python3 -m http.server $PORT --bind 0.0.0.0 &
HTTPD=$!

# 启动 cloudflared
$CF tunnel --url http://localhost:$PORT --no-autoupdate &
CFD=$!

# 等待 tunnel URL
for i in $(seq 1 30); do
    URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf*.log 2>/dev/null | tail -1)
    if [ -n "$URL" ]; then break; fi
    sleep 1
done

clear
cat <<EOF

  ╔══════════════════════════════════════╗
  ║                                      ║
  ║   实时字幕翻译 - 公网链接             ║
  ║                                      ║
  ║   $URL
  ║                                      ║
  ║   (本机: http://127.0.0.1:$PORT)      ║
  ║                                      ║
  ║   关闭此终端 = 停止服务               ║
  ╚══════════════════════════════════════╝

EOF

wait
