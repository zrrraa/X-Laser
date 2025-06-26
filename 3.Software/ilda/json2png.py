import json
from PIL import Image, ImageDraw

def find_closest_color(color_index, color_map):
    """查找数值上最接近的颜色索引"""
    # 将十六进制颜色索引转换为十进制整数
    target = int(color_index)
    # 获取所有预定义的颜色索引
    predefined = list(color_map.keys())
    # 计算差值最小的颜色
    closest = min(predefined, key=lambda x: abs(x - target))
    return color_map[closest]

def save_frame_as_png(json_path, output_png="frame.png", frame_index=0, canvas_size=800):
    # 定义颜色映射表
    color_map = {
        0: (255, 0, 0),     # 红色
        24: (0, 255, 0),     # 绿色
        16: (255, 255, 0),   # 黄色
        40: (0, 0, 255),     # 蓝色
        48: (255, 0, 255),   # 品红
        31: (0, 255, 255),   # 青色
        56: (255, 255, 255), # 白色
        64: (0, 0, 0),       # 黑色
    }
    
    # 加载JSON数据
    with open(json_path) as f:
        data = json.load(f)

    # 初始化参数
    scale = canvas_size / 65536  # 坐标缩放因子
    target_frame = None

    # 遍历数据寻找目标帧（跳过调色板部分）
    frame_counter = 0
    for section in data:
        # 检查有效帧
        if section.get("format_code") in [0, 1, 4, 5] and section.get("num_records", 0) > 0:
            if frame_counter == frame_index:
                target_frame = section
                break
            frame_counter += 1

    if not target_frame:
        raise ValueError(f"未找到第 {frame_index} 帧，文件共 {frame_counter} 个有效帧")

    # 创建画布
    img = Image.new("RGB", (canvas_size, canvas_size), "black")
    draw = ImageDraw.Draw(img)

    # 处理坐标和颜色
    current_path = []
    current_color = (255, 255, 255)  # 默认白色

    for point in target_frame["data"]:
        # 坐标转换
        x = int((point["x"] + 32768) * scale)
        y = int((32767 - point["y"]) * scale)  # Y轴翻转

        # 处理blanking状态
        if point["status"]["blanking"]:
            if current_path:
                draw.line(current_path, fill=current_color, width=1)
                current_path = []
        else:
            # 获取颜色
            if target_frame["format_code"] in [0, 1]:  # 索引色
                color_index = point["color_index"]
                # 查找最近颜色
                current_color = color_map.get(color_index) or find_closest_color(color_index, color_map)
            else:  # 真彩色
                current_color = tuple(point["color"][:3])  # 取RGB前三个值

            current_path.append((x, y))

    # 绘制最后未完成的路径
    if current_path:
        draw.line(current_path, fill=current_color, width=1)

    # 保存图像
    img.save(output_png)
    print(f"成功保存第 {frame_index} 帧到 {output_png}")

# 使用示例
if __name__ == "__main__":
    save_frame_as_png(
        "../test/1.json",
        output_png="../test/1.png",
        frame_index=0,      # 保存第一帧
        canvas_size=1024    # 设置画布尺寸
    )