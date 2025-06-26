import json
from PIL import Image, ImageDraw
from collections import OrderedDict

def json_to_gif(json_path, output_gif="animation.gif", canvas_size=800, fps=30):
    # 定义颜色映射表
    color_map = {
        0xE0: (255, 0, 0),     # 红色
        0x18: (0, 255, 0),     # 绿色
        0xF8: (255, 255, 0),   # 黄色
        0x07: (0, 0, 255),     # 蓝色
        0xE7: (255, 0, 255),   # 品红
        0x1F: (0, 255, 255),   # 青色
        0xFF: (255, 255, 255), # 白色
        0x00: (0, 0, 0),       # 黑色
    }

    def find_closest_color(color_index):
        """查找数值上最接近的颜色索引"""
        target = int(color_index)
        predefined = list(color_map.keys())
        closest = min(predefined, key=lambda x: abs(x - target))
        return color_map[closest]

    # 加载JSON数据
    with open(json_path) as f:
        data = json.load(f, object_pairs_hook=OrderedDict)

    # 初始化参数
    scale = canvas_size / 65536
    frame_delay = int(1000 / fps)  # 转换为毫秒
    all_frames = []
    frame_counter = 0

    # 预处理数据（跳过调色板部分）
    for section in data:
        # 只处理有效帧
        if section.get("format_code") in [0, 1, 4, 5] and section.get("num_records", 0) > 0:
            # 创建画布
            img = Image.new("RGB", (canvas_size, canvas_size), "black")
            draw = ImageDraw.Draw(img)
            current_path = []
            current_color = (255, 255, 255)  # 默认白色

            # 处理每个点
            for point in section["data"]:
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
                    if section["format_code"] in [0, 1]:  # 索引色
                        color_index = point["color_index"]
                        current_color = color_map.get(color_index) or find_closest_color(color_index)
                    else:  # 真彩色
                        current_color = tuple(point["color"][:3])

                    current_path.append((x, y))

            # 绘制最后未完成的路径
            if current_path:
                draw.line(current_path, fill=current_color, width=1)

            all_frames.append(img)
            frame_counter += 1

    # 保存为GIF
    if all_frames:
        all_frames[0].save(
            output_gif,
            save_all=True,
            append_images=all_frames[1:],
            duration=frame_delay,
            loop=0,
            optimize=True
        )
        print(f"成功生成 {frame_counter} 帧动画到 {output_gif}")
    else:
        print("未找到有效帧数据")

# 使用示例
if __name__ == "__main__":
    json_to_gif(
        "../test/hole3.json",
        output_gif="../test/hole3.gif",
        canvas_size=1024,
        fps=24
    )