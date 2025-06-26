import struct
import json
from collections import OrderedDict

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
        
        # 解析头部字段
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
        
        # 处理结束标记
        if num_records == 0 and format_code in [0, 1, 4, 5]:
            break
        
        # 解析数据记录
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
    
    # 添加当前调色板信息到结果
    if current_palettes:
        result.append({"active_palettes": current_palettes})
    
    return result

# 使用示例
if __name__ == "__main__":
    ilda_data = parse_ilda_file("../test/1.ild")
    print(json.dumps(ilda_data, indent=2))