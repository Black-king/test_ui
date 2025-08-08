@echo off
echo 正在卸载命令管理器...

set INSTALL_DIR=%USERPROFILE%\CommandManager

if exist "%USERPROFILE%\Desktop\命令管理器.lnk" (
    echo 正在删除桌面快捷方式...
    del "%USERPROFILE%\Desktop\命令管理器.lnk"
)

if exist "%INSTALL_DIR%" (
    echo 正在删除安装目录...
    rd /s /q "%INSTALL_DIR%"
)

echo 卸载完成！
pause