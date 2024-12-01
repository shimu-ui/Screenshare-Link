import os
from PIL import Image, ImageDraw, ImageFont
import math

def create_rounded_rectangle(draw, xy, radius, fill):
    """绘制圆角矩形"""
    x1, y1, x2, y2 = xy
    draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
    draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
    draw.pieslice([x1, y1, x1+radius*2, y1+radius*2], 180, 270, fill=fill)
    draw.pieslice([x2-radius*2, y1, x2, y1+radius*2], 270, 360, fill=fill)
    draw.pieslice([x1, y2-radius*2, x1+radius*2, y2], 90, 180, fill=fill)
    draw.pieslice([x2-radius*2, y2-radius*2, x2, y2], 0, 90, fill=fill)

def create_favicon(target_dir, text="SS", color='#3498db'):
    """
    创建favicon图标文件
    :param target_dir: 目标目录
    :param text: 图标文字
    :param color: 图标颜色
    """
    # 创建一个128x128的图像
    size = 128
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制圆角矩形背景
    margin = 10
    create_rounded_rectangle(draw, [margin, margin, size-margin, size-margin], 20, color)
    
    # 尝试加载字体，如果失败则使用默认字体
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 32)
        except:
            font = ImageFont.load_default()
    
    # 添加文字
    draw.text((size/2, size/2), text, 
              font=font, fill='white', anchor="mm")
    
    # 保存不同尺寸的图标
    sizes = [16, 32, 48, 64, 128]
    icons = []
    for s in sizes:
        icons.append(img.resize((s, s), Image.Resampling.LANCZOS))
    
    # 确保static目录存在
    static_dir = os.path.join(target_dir, 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    # 保存为ICO文件
    icons[0].save(os.path.join(static_dir, 'favicon.ico'), 
                 format='ICO', 
                 sizes=[(s, s) for s in sizes])

def create_logo(color='#3498db'):
    """
    创建项目logo
    :param color: 主色调
    :return: PIL Image对象
    """
    # 创建一个更大的图像作为logo
    logo_size = 512  # 增大尺寸以获得更好的质量
    logo_img = Image.new('RGBA', (logo_size, logo_size), (0, 0, 0, 0))
    logo_draw = ImageDraw.Draw(logo_img)
    
    # 绘制渐变背景
    for y in range(logo_size):
        alpha = int(255 * (1 - y/logo_size))
        color_with_alpha = color + hex(alpha)[2:].zfill(2)
        logo_draw.line([(0, y), (logo_size, y)], fill=color_with_alpha)
    
    # 绘制圆角矩形
    padding = 40
    create_rounded_rectangle(logo_draw, 
                           [padding, padding, logo_size-padding, logo_size-padding], 
                           60, color)
    
    # 添加装饰性元素
    circle_radius = 20
    circle_color = '#ffffff'
    for angle in range(0, 360, 45):
        x = logo_size/2 + math.cos(math.radians(angle)) * (logo_size/3)
        y = logo_size/2 + math.sin(math.radians(angle)) * (logo_size/3)
        logo_draw.ellipse([x-circle_radius, y-circle_radius, 
                         x+circle_radius, y+circle_radius], 
                         fill=circle_color)
    
    # 更大的字体
    try:
        logo_font = ImageFont.truetype("arial.ttf", 96)
    except:
        try:
            logo_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 96)
        except:
            logo_font = ImageFont.load_default()
    
    # 添加主标题
    logo_draw.text((logo_size/2, logo_size/2-30), "SS-Link", 
                   font=logo_font, fill='white', anchor="mm")
    
    # 添加副标题
    try:
        subtitle_font = ImageFont.truetype("arial.ttf", 32)
    except:
        try:
            subtitle_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 32)
        except:
            subtitle_font = ImageFont.load_default()
    
    logo_draw.text((logo_size/2, logo_size/2+50), "Screen Share", 
                   font=subtitle_font, fill='#ffffff', anchor="mm")
    
    return logo_img

def main():
    """生成主端和客户端的图标以及项目logo"""
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 生成主端图标
    create_favicon(os.path.join(current_dir, '主端'), "SS", '#3498db')
    print("主端图标已生成")
    
    # 生成客户端图标
    create_favicon(os.path.join(current_dir, '客户端'), "SC", '#2ecc71')
    print("客户端图标已生成")
    
    # 生成项目logo
    docs_dir = os.path.join(current_dir, 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    
    logo = create_logo('#3498db')
    if logo:
        logo.save(os.path.join(docs_dir, 'logo.png'))
        print("项目logo已生成")

if __name__ == '__main__':
    main() 