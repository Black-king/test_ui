from PIL import Image, ImageDraw
import os

def create_cyber_terminal_ico():
    """创建赛博朋克风格的终端ICO图标"""
    # 创建48x48的图像
    img = Image.new('RGBA', (48, 48), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制外框 - 赛博朋克蓝色渐变
    draw.rounded_rectangle((2, 2, 46, 46), radius=8, fill=(26, 26, 46, 255), outline=(0, 255, 255, 255), width=2)
    
    # 绘制屏幕区域
    draw.rounded_rectangle((6, 6, 38, 28), radius=2, fill=(10, 10, 10, 255), outline=(0, 255, 255, 255), width=1)
    
    # 绘制终端提示符和代码行
    # 提示符 "$>"
    draw.text((8, 10), "$>", fill=(0, 255, 255, 255))
    
    # 代码行 - 用矩形模拟
    draw.rectangle((18, 12, 26, 13), fill=(0, 255, 255, 255))
    draw.rectangle((8, 16, 20, 17), fill=(255, 107, 107, 255))
    draw.rectangle((8, 20, 24, 21), fill=(0, 255, 255, 255))
    draw.rectangle((8, 24, 18, 25), fill=(255, 107, 107, 255))
    
    # 绘制键盘区域
    draw.rounded_rectangle((6, 32, 38, 42), radius=2, fill=(26, 26, 46, 255), outline=(0, 255, 255, 255), width=1)
    
    # 绘制键盘按键
    for i in range(8):
        x = 8 + i * 4
        draw.rounded_rectangle((x, 34, x+2, 36), radius=1, fill=(0, 255, 255, 255))
        draw.rounded_rectangle((x, 38, x+2, 40), radius=1, fill=(0, 255, 255, 255))
    
    # 确保图标目录存在
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
    if not os.path.exists(icon_dir):
        os.makedirs(icon_dir)
    
    # 保存为ICO文件，包含多个尺寸
    icon_path = os.path.join(icon_dir, 'cyber_terminal.ico')
    # 创建多个尺寸的图像
    sizes = [(16, 16), (32, 32), (48, 48)]
    images = []
    
    for size in sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        images.append(resized)
    
    # 保存ICO文件
    images[0].save(icon_path, format='ICO', sizes=[(img.width, img.height) for img in images], append_images=images[1:])
    print(f"赛博朋克终端图标已创建: {icon_path}")
    return icon_path

if __name__ == "__main__":
    create_cyber_terminal_ico()