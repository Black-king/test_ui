# 命令管理器

一个用于管理和执行HDC命令的桌面应用程序，支持文件上传下载和命令管理。

## 功能

- 执行常用HDC命令
- 文件上传和下载，支持路径选择
- 显示命令执行进度和结果
- 命令管理面板，可添加或删减命令按钮

## 安装

1. 确保已安装Python 3.6+
2. 安装依赖包：

```bash
pip install -r requirements.txt
```

## 使用方法

### 开发环境运行

运行以下命令启动应用：

```bash
python main.py
```

或者直接运行`run.bat`批处理文件。

### 打包为可执行文件

1. 运行`build_app.bat`批处理文件
2. 打包完成后，可执行文件位于`dist/HDCManager.exe`

### 安装应用程序

1. 运行`build_app.bat`批处理文件进行打包
2. 运行`install.bat`批处理文件进行安装
3. 安装程序会将应用程序安装到`%USERPROFILE%\HDCManager`目录下，并创建桌面快捷方式

### 卸载应用程序

运行`uninstall.bat`批处理文件即可卸载应用程序，包括删除安装目录和桌面快捷方式

## 自定义命令

您可以通过应用内的"管理命令"按钮添加、编辑或删除命令。

命令类型说明：
- normal: 普通命令
- upload: 上传文件命令（会提示选择本地文件和输入远程路径）
- download: 下载文件命令（会提示输入远程文件路径和选择本地保存位置）
- screenshot: 截图命令（自动处理时间戳，不需要用户手动输入）

## 占位符

在命令中可以使用以下占位符：
- {local_path}: 本地文件路径
- {remote_path}: 远程文件路径
- {package_name}: 包名
- {timestamp}: 时间戳（格式：年月日_时分秒），仅在screenshot类型命令中自动处理
- 其他自定义占位符

对于normal、upload和download类型的命令，程序会在执行命令前提示用户输入这些占位符的值。
对于screenshot类型的命令，程序会自动处理{timestamp}占位符，无需用户手动输入。

## 配置文件

应用程序使用`config.json`文件存储命令配置，格式如下：

```json
{
  "commands": [
    {
      "name": "命令名称",
      "command": "命令内容",
      "type": "命令类型",
      "icon": "图标名称"
    }
  ]
}
```

## 图标

应用程序使用SVG格式的图标，存放在`icons`目录下。可以通过运行`create_icons.py`脚本生成默认图标。

## 注意事项

- 首次运行时，如果`config.json`文件不存在，将自动创建默认配置
- 打包后的应用程序会自动处理资源路径，确保图标等资源正确加载

## 项目结构

```
.
├── main.py              # 主程序文件
├── config.json          # 配置文件
├── requirements.txt     # 依赖包列表
├── README.md           # 说明文档
├── run.bat             # 开发环境运行脚本
├── build_app.bat       # 打包脚本
├── install.bat         # 安装脚本
├── uninstall.bat       # 卸载脚本
├── create_icons.py     # 图标生成脚本
├── icons/              # 图标目录
│   ├── terminal.ico    # 应用程序图标
│   ├── terminal.svg    # 终端图标
│   ├── upload.svg      # 上传图标
│   ├── download.svg    # 下载图标
│   ├── smartphone.svg  # 截图图标
│   ├── trash.svg       # 卸载图标
│   └── ...             # 其他图标
└── dist/               # 打包输出目录
    └── HDCManager.exe  # 打包后的可执行文件
```
