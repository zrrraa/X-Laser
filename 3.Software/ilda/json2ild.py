import struct
import json

def write_ilda_file(json_data, output_filename):
    with open(output_filename, 'wb') as f:
        # 处理所有section
        for section in json_data:
            # 跳过调色板信息（如果存在）
            if 'active_palettes' in section:
                continue
            
            format_code = section['format_code']
            name = section['name'].encode('ascii')[:8].ljust(8, b'\x00')  # 确保是 ASCII
            company = section['company'].encode('ascii')[:8].ljust(8, b'\x00')  # 确保是 ASCII
            num_records = section['num_records']
            section_number = section['section_number']
            total_sections = section['total_sections']
            projector = section['projector']
            
            # 修正后的头部构造
            header = struct.pack(
                '>4s4B8s8sHHHBB',  # 大端字节序
                b'ILDA',           # 固定标识符
                0, 0, 0,          # 保留字段
                format_code,
                name,
                company,
                num_records,
                section_number,
                total_sections,
                projector,
                0                 # 最后一个保留字段
            )
            f.write(header)
            
            # 处理数据记录
            if format_code == 0:  # 3D索引色
                for point in section['data']:
                    status = (point['status']['last_point'] << 7) | (point['status']['blanking'] << 6)
                    data = struct.pack(
                        '>hhhBB',
                        point['x'],
                        point['y'],
                        point['z'],
                        status,
                        point['color_index']
                    )
                    f.write(data)
            
            elif format_code == 1:  # 2D索引色
                for point in section['data']:
                    status = (point['status']['last_point'] << 7) | (point['status']['blanking'] << 6)
                    data = struct.pack(
                        '>hhBB',
                        point['x'],
                        point['y'],
                        status,
                        point['color_index']
                    )
                    f.write(data)
            
            elif format_code == 2:  # 调色板
                for color in section['palette']:
                    data = struct.pack('BBB', *color)
                    f.write(data)
            
            elif format_code == 4:  # 3D真彩色
                for point in section['data']:
                    status = (point['status']['last_point'] << 7) | (point['status']['blanking'] << 6)
                    color = point['color']
                    data = struct.pack(
                        '>hhhBBBB',
                        point['x'],
                        point['y'],
                        point['z'],
                        status,
                        color[2],  # Blue
                        color[1],  # Green
                        color[0]   # Red
                    )
                    f.write(data)
            
            elif format_code == 5:  # 2D真彩色
                for point in section['data']:
                    status = (point['status']['last_point'] << 7) | (point['status']['blanking'] << 6)
                    color = point['color']
                    data = struct.pack(
                        '>hhBBBB',
                        point['x'],
                        point['y'],
                        status,
                        color[2],  # Blue
                        color[1],  # Green
                        color[0]   # Red
                    )
                    f.write(data)
        
        # 写入结束标记
        end_header = struct.pack(
            '>4s4B8s8sHHHBB',
            b'ILDA',
            0, 0, 0,
            0,
            b'\x00' * 8,
            b'\x00' * 8,
            0,
            0,
            0,
            0,
            0
        )
        f.write(end_header)

# 使用示例
if __name__ == "__main__":
    with open("../test/hole.json", "r") as json_file:
        ilda_data = json.load(json_file)
    
    write_ilda_file(ilda_data, "../ildfile/HOLE.ild")