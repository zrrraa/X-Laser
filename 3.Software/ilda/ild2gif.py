import struct
import json
from collections import OrderedDict
from PIL import Image, ImageDraw
import argparse

def parse_ilda_file(filename):
    with open(filename, 'rb') as f:
        data = f.read()
    
    ptr = 0
    result = []
    current_palettes = {}  # 按投影机编号存储当前调色板
    
    while ptr < len(data):
        # 解析头部
        header = data[ptr:ptr+32]
        if len(header) < 32:
            break
        
        ilda_id = header[0:4].decode('ascii')
        if ilda_id != 'ILDA':
            raise ValueError("Invalid ILDA file header")
        
        format_code = header[7]
        name = header[8:16].split(b'\x00')[0].decode('ascii', 'ignore').strip()
        company = header[16:24].split(b'\x00')[0].decode('ascii', 'ignore').strip()
        num_records = struct.unpack('>H', header[24:26])[0]
        section_number = struct.unpack('>H', header[26:28])[0]
        total_sections = struct.unpack('>H', header[28:30])[0]
        projector = header[30]
        
        section = OrderedDict([
            ("format_code", format_code),
            ("name", name),
            ("company", company),
            ("num_records", num_records),
            ("section_number", section_number),
            ("total_sections", total_sections),
            ("projector", projector),
            ("data", [])
        ])
        
        ptr += 32
        
        if num_records == 0 and format_code in [0, 1, 4, 5]:
            break
        
        if format_code == 0:  # 3D索引色
            record_size = 8
            for _ in range(num_records):
                record = data[ptr:ptr+record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                z = struct.unpack('>h', record[4:6])[0]
                status = record[6]
                color_index = record[7]
                
                section['data'].append(OrderedDict([
                    ("x", x), ("y", y), ("z", z),
                    ("status", {
                        "last_point": (status & 0x80) >> 7,
                        "blanking": (status & 0x40) >> 6
                    }),
                    ("color_index", color_index)
                ]))
                ptr += record_size
        
        elif format_code == 1:  # 2D索引色
            record_size = 6
            for _ in range(num_records):
                record = data[ptr:ptr+record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                status = record[4]
                color_index = record[5]
                
                section['data'].append(OrderedDict([
                    ("x", x), ("y", y), ("z", None),
                    ("status", {
                        "last_point": (status & 0x80) >> 7,
                        "blanking": (status & 0x40) >> 6
                    }),
                    ("color_index", color_index)
                ]))
                ptr += record_size
        
        elif format_code == 2:  # 调色板
            record_size = 3
            palette = []
            for _ in range(num_records):
                record = data[ptr:ptr+record_size]
                r = record[0]
                g = record[1]
                b = record[2]
                palette.append([r, g, b])
                ptr += record_size
            
            current_palettes[projector] = palette
            section['palette'] = palette
        
        elif format_code == 4:  # 3D真彩色
            record_size = 10
            for _ in range(num_records):
                record = data[ptr:ptr+record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                z = struct.unpack('>h', record[4:6])[0]
                status = record[6]
                blue = record[7]
                green = record[8]
                red = record[9]
                
                section['data'].append(OrderedDict([
                    ("x", x), ("y", y), ("z", z),
                    ("status", {
                        "last_point": (status & 0x80) >> 7,
                        "blanking": (status & 0x40) >> 6
                    }),
                    ("color", [red, green, blue])
                ]))
                ptr += record_size
        
        elif format_code == 5:  # 2D真彩色
            record_size = 8
            for _ in range(num_records):
                record = data[ptr:ptr+record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                status = record[4]
                blue = record[5]
                green = record[6]
                red = record[7]
                
                section['data'].append(OrderedDict([
                    ("x", x), ("y", y), ("z", None),
                    ("status", {
                        "last_point": (status & 0x80) >> 7,
                        "blanking": (status & 0x40) >> 6
                    }),
                    ("color", [red, green, blue])
                ]))
                ptr += record_size
        
        result.append(section)
    
    return result, current_palettes

def ilda_to_gif(ild_data, palettes, output_gif, canvas_size=800, fps=30):
    color_map = {
        0: (255, 0, 0),
        24: (0, 255, 0),
        16: (255, 255, 0),
        40: (0, 0, 255),
        48: (255, 0, 255),
        31: (0, 255, 255),
        56: (255, 255, 255),
        64: (0, 0, 0),
    }

    def find_closest_color(target_index):
        """查找数值上最接近的颜色索引"""
        predefined = list(color_map.keys())
        closest = min(predefined, key=lambda x: abs(x - target_index))
        return color_map[closest]

    def get_color(section_projector, color_index):
        # 优先使用文件内定义的调色板
        if section_projector in palettes:
            palette = palettes[section_projector]
            if color_index < len(palette):
                return tuple(palette[color_index])
        
        # 其次使用预定义颜色映射
        if color_index in color_map:
            return color_map[color_index]
        
        # 最后进行颜色近似匹配
        return find_closest_color(color_index)

    scale = canvas_size / 65536
    frame_delay = int(1000 / fps)
    all_frames = []
    
    for section in ild_data:
        if section.get("format_code") not in [0, 1, 4, 5] or section.get("num_records", 0) == 0:
            continue
        
        img = Image.new("RGB", (canvas_size, canvas_size), "black")
        draw = ImageDraw.Draw(img)
        current_path = []
        current_color = (255, 255, 255)
        projector = section["projector"]
        
        for point in section["data"]:
            x = int((point["x"] + 32768) * scale)
            y = int((32767 - point["y"]) * scale)
            
            if point["status"]["blanking"]:
                if current_path:
                    draw.line(current_path, fill=current_color, width=1)
                    current_path = []
            else:
                if section["format_code"] in [0, 1]:
                    color_index = point["color_index"]
                    current_color = get_color(projector, color_index)
                else:
                    current_color = tuple(point["color"][:3])
                
                current_path.append((x, y))
        
        if current_path:
            draw.line(current_path, fill=current_color, width=1)
        
        all_frames.append(img)
    
    if all_frames:
        all_frames[0].save(
            output_gif,
            save_all=True,
            append_images=all_frames[1:],
            duration=frame_delay,
            loop=0,
            optimize=True
        )
        print(f"成功生成 {len(all_frames)} 帧动画到 {output_gif}")
    else:
        print("未找到有效帧数据")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert ILDA files to GIF animations")
    parser.add_argument("input_ild", help="Path to input ILD file")
    parser.add_argument("output_gif", help="Path to output GIF file")
    parser.add_argument("--size", type=int, default=800, help="Canvas size (default: 800)")
    parser.add_argument("--fps", type=int, default=30, help="Animation FPS (default: 30)")
    
    args = parser.parse_args()
    
    ild_data, palettes = parse_ilda_file(args.input_ild)
    ilda_to_gif(ild_data, palettes, args.output_gif, args.size, args.fps)