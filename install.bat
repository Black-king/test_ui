@echo off
echo 正在安装命令管理器...

set INSTALL_DIR=%USERPROFILE%\CommandManager

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

if not exist dist\CommandManager.exe (
    echo 未找到可执行文件，请先运行build_app.bat进行打包
    pause
    exit /b 1
)

echo 正在复制文件...
copy dist\CommandManager.exe "%INSTALL_DIR%"

if exist config.json (
    copy config.json "%INSTALL_DIR%"
)

if exist icons (
    if not exist "%INSTALL_DIR%\icons" mkdir "%INSTALL_DIR%\icons"
    xcopy /s /y icons "%INSTALL_DIR%\icons\"
)

echo 正在创建桌面快捷方式...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\命令管理器.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\CommandManager.exe'; $Shortcut.Save()"

echo 安装完成！
echo 应用程序已安装到: %INSTALL_DIR%
echo 桌面快捷方式已创建

pause