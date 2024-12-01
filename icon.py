from PIL import Image, ImageDraw, ImageFont

def create_icon():
    # 创建一个128x128的图像
    size = 128
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制SS-Link图标
    margin = 10
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 fill='#3498db')
    
    # 添加文字
    font = ImageFont.truetype("arial.ttf", 32)
    draw.text((size/2, size/2), "SS", 
              font=font, fill='white', anchor="mm")
    
    # 保存不同尺寸的图标
    sizes = [16, 32, 48, 64, 128]
    icons = []
    for s in sizes:
        icons.append(img.resize((s, s), Image.Resampling.LANCZOS))
    
    # 保存为ICO文件
    icons[0].save('主端/static/favicon.ico', 
                 format='ICO', 
                 sizes=[(s, s) for s in sizes])
    print("图标文件已生成")

if __name__ == '__main__':
    create_icon() 