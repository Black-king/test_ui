from PIL import Image, ImageDraw
import os

# 创建一个简单的图标
def create_icon():
    # 创建一个新的图像，大小为48x48像素，背景为透明
    img = Image.new('RGBA', (48, 48), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制一个蓝色的圆形背景
    draw.ellipse((4, 4, 44, 44), fill=(52, 152, 219, 255))
    
    # 绘制终端图标
    draw.rectangle((14, 14, 34, 34), fill=(255, 255, 255, 255))
    draw.line((18, 22, 24, 22), fill=(52, 152, 219, 255), width=2)
    draw.line((18, 26, 30, 26), fill=(52, 152, 219, 255), width=2)
    draw.line((18, 30, 27, 30), fill=(52, 152, 219, 255), width=2)
    
    # 确保图标目录存在
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
    if not os.path.exists(icon_dir):
        os.makedirs(icon_dir)
    
    # 保存为ICO文件
    icon_path = os.path.join(icon_dir, 'terminal.ico')
    img.save(icon_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"图标已创建: {icon_path}")

if __name__ == "__main__":
    create_icon()