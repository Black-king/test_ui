@echo off
echo 正在安装依赖...
pip install -r requirements.txt

echo 正在启动HDC命令管理器...
python main.py
pause