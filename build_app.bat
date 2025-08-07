@echo off
pip install -r requirements.txt

if not exist icons mkdir icons

pyinstaller --noconfirm --onefile --windowed --icon="icons\cyber_terminal.ico" --add-data="icons;icons" --name="HDCManager" main.py

if exist config.json copy config.json dist\

pause