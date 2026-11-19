#!/bin/bash
# 实时字幕翻译启动脚本
# 用法:
#   ./run.sh                  # 默认黎巴嫩阿拉伯语
#   ./run.sh --lang lebanon   # 黎巴嫩
#   ./run.sh --lang philippines
#   ./run.sh --lang bangladesh
#   ./run.sh --lang korea
#   ./run.sh --list-devices   # 列出音频设备
#   ./run.sh --debug          # 调试模式

cd "$(dirname "$0")"
source venv/bin/activate
python3 main.py "$@"
