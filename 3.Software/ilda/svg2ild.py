import xml.etree.ElementTree as ET
from svg.path import parse_path
import json
import math
import numpy as np
import struct
import sys
import argparse  # 新增参数解析库

# 配置参数
CONFIG = {
    'samples_per_unit': 30,
    'min_samples': 5,
    'canvas_size': 1024,
    'ilda_range': (-32767, 32767),
    'endpoint_blanking': 10,
    'manual_scale': 1.0,         # 新增手动缩放系数
    'manual_translate_x': 0,     # 新增X轴平移
    'manual_translate_y': 0      # 新增Y轴平移
}

COLOR_MAP = {
    'red': 0,
    'yellow': 16,
    'green': 24,
    'cyan': 31,
    'blue': 40,
    'magenta': 48,
    'white': 56,
    'black': 64
}

def svg_to_laser_json(svg_file):
    tree = ET.parse(svg_file)
    root = tree.getroot()
    
    svg_width, svg_height, viewbox = parse_svg_dimensions(root)
    scale, offset_x, offset_y = calculate_normalization(root, svg_width, svg_height, viewbox)
    
    elements = []
    for elem in root.iter():
        if elem.tag.endswith('path') and elem.get('stroke') != 'none':
            process_path(elem, elements, scale, offset_x, offset_y)
    
    if not elements:
        print("警告：未找到有效路径")
        return []
    
    optimized_elements = optimize_drawing_sequence(elements)
    return convert_to_ilda_format(optimized_elements)

def parse_svg_dimensions(root):
    """解析SVG尺寸和视口"""
    viewbox = root.get('viewBox')
    if viewbox:
        _, _, vb_w, vb_h = map(float, viewbox.split())
        return vb_w, vb_h, viewbox
    else:
        width = float(root.get('width', CONFIG['canvas_size']))
        height = float(root.get('height', CONFIG['canvas_size']))
        return width, height, None

def calculate_normalization(root, svg_w, svg_h, viewbox):
    """计算坐标标准化参数"""
    all_points = []
    for elem in root.iter():
        if elem.tag.endswith('path'):
            path = parse_path(elem.get('d'))
            for segment in path:
                samples = max(CONFIG['min_samples'], int(segment.length()/10)+1)
                for t in np.linspace(0, 1, samples):
                    pt = segment.point(t)
                    all_points.append((pt.real, pt.imag))
    
    if not all_points:
        return 1.0, 0, 0
    
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    
    content_width = max_x - min_x
    content_height = max_y - min_y
    scale = 0.95 * CONFIG['canvas_size'] / max(content_width, content_height, 1e-6)
    
    offset_x = - (min_x + max_x)/2 * scale + CONFIG['canvas_size']/2
    offset_y = - (min_y + max_y)/2 * scale + CONFIG['canvas_size']/2
    return scale, offset_x, offset_y

def process_path(elem, elements, scale, offset_x, offset_y):
    """处理单个路径元素"""
    path = parse_path(elem.get('d'))
    color = elem.get('stroke', 'black').lower()
    points = []
    
    # 获取画布中心坐标
    canvas_center = CONFIG['canvas_size'] / 2
    
    for segment in path:
        seg_length = segment.length() * scale
        samples = max(CONFIG['min_samples'], int(seg_length / CONFIG['samples_per_unit']) + 1)
        
        for t in np.linspace(0, 1, samples):
            pt = segment.point(t)
            # 基础坐标变换
            x_base = pt.real * scale + offset_x
            y_base = CONFIG['canvas_size'] - (pt.imag * scale + offset_y)
            
            # 以画布中心为基准进行缩放（新增逻辑）
            x_centered = (x_base - canvas_center) * CONFIG['manual_scale'] + canvas_center
            y_centered = (y_base - canvas_center) * CONFIG['manual_scale'] + canvas_center
            
            # 应用平移
            x = x_centered + CONFIG['manual_translate_x']
            y = y_centered + CONFIG['manual_translate_y']
            
            points.append((x, y))
    
    if len(points) >= 2:
        elements.append({
            'points': points,
            'color': color,
            'start': points[0],
            'end': points[-1]
        })

def optimize_drawing_sequence(elements):
    """优化绘制顺序算法"""
    sorted_elements = []
    remaining = elements.copy()
    current_pos = None
    
    while remaining:
        best_elem = None
        best_distance = float('inf')
        reverse = False
        
        for elem in remaining:
            for check_reverse in [False, True]:
                target_pos = elem['end'] if check_reverse else elem['start']
                dist = distance((0,0), target_pos) if not current_pos else distance(current_pos, target_pos)
                
                if dist < best_distance:
                    best_distance = dist
                    best_elem = elem
                    reverse = check_reverse
        
        if best_elem:
            if reverse:
                best_elem['points'] = best_elem['points'][::-1]
                best_elem['start'], best_elem['end'] = best_elem['end'], best_elem['start']
            
            sorted_elements.append(best_elem)
            remaining.remove(best_elem)
            current_pos = best_elem['end']
    
    return sorted_elements

def convert_to_ilda_format(sorted_elements):
    """转换为ILDA格式"""
    laser_points = []
    
    for elem in sorted_elements:
        laser_points.extend(generate_endpoint_blanking(elem['start']))
        
        color_index = COLOR_MAP.get(elem['color'], 0)
        for x, y in elem['points']:
            laser_points.append({
                'x': scale_coord(x),
                'y': scale_coord(y),
                'z': 0,
                'status': {'blanking': 0, 'last_point': 0},
                'color_index': color_index
            })
        
        laser_points.extend(generate_endpoint_blanking(elem['end']))
    
    if laser_points:
        for p in reversed(laser_points):
            if p['status']['blanking'] == 1:
                p['status']['last_point'] = 1
                break
    
    return [{
        "format_code": 0,
        "name": "SVG_IMAGE",
        "company": "SVG2ILDA",
        "num_records": len(laser_points),
        "section_number": 0,
        "total_sections": 1,
        "projector": 0,
        "data": laser_points
    }]

def generate_endpoint_blanking(point):
    """生成端点空白点"""
    return [create_blanking_point(*point) for _ in range(CONFIG['endpoint_blanking'])]

def create_blanking_point(x, y):
    """创建空白点"""
    return {
        'x': scale_coord(x),
        'y': scale_coord(y),
        'z': 0,
        'status': {'blanking': 1, 'last_point': 0},
        'color_index': 0
    }

def scale_coord(value):
    """坐标标准化"""
    normalized = (value / CONFIG['canvas_size'] - 0.5) * 2
    return int(normalized * CONFIG['ilda_range'][1])

def distance(p1, p2):
    """计算平方距离"""
    return (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2

def write_ilda_file(json_data, output_filename):
    with open(output_filename, 'wb') as f:
        for section in json_data:
            if 'active_palettes' in section:
                continue
            
            format_code = section['format_code']
            name = section['name'].encode('ascii')[:8].ljust(8, b'\x00')
            company = section['company'].encode('ascii')[:8].ljust(8, b'\x00')
            num_records = section['num_records']
            section_number = section['section_number']
            total_sections = section['total_sections']
            projector = section['projector']
            
            header = struct.pack(
                '>4s4B8s8sHHHBB',
                b'ILDA',
                0, 0, 0,
                format_code,
                name,
                company,
                num_records,
                section_number,
                total_sections,
                projector,
                0
            )
            f.write(header)
            
            if format_code == 0:
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
            elif format_code == 1:
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
            elif format_code == 2:
                for color in section['palette']:
                    data = struct.pack('BBB', *color)
                    f.write(data)
            elif format_code == 4:
                for point in section['data']:
                    status = (point['status']['last_point'] << 7) | (point['status']['blanking'] << 6)
                    color = point['color']
                    data = struct.pack(
                        '>hhhBBBB',
                        point['x'],
                        point['y'],
                        point['z'],
                        status,
                        color[2],
                        color[1],
                        color[0]
                    )
                    f.write(data)
            elif format_code == 5:
                for point in section['data']:
                    status = (point['status']['last_point'] << 7) | (point['status']['blanking'] << 6)
                    color = point['color']
                    data = struct.pack(
                        '>hhBBBB',
                        point['x'],
                        point['y'],
                        status,
                        color[2],
                        color[1],
                        color[0]
                    )
                    f.write(data)
        
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

if __name__ == "__main__":
    # 配置命令行参数解析（新增部分）
    parser = argparse.ArgumentParser(description='Convert SVG to ILDA laser show format')
    parser.add_argument('input_svg', help='Input SVG file path')
    parser.add_argument('output_ild', help='Output ILDA file path')
    parser.add_argument('--scale', type=float, default=1.0,
                       help='Manual scaling factor (default: 1.0)')
    parser.add_argument('--tx', type=int, default=0,
                       help='X-axis translation in pixels (default: 0)')
    parser.add_argument('--ty', type=int, default=0,
                       help='Y-axis translation in pixels (default: 0)')
    
    args = parser.parse_args()
    
    # 更新配置参数（新增部分）
    CONFIG['manual_scale'] = args.scale
    CONFIG['manual_translate_x'] = args.tx
    CONFIG['manual_translate_y'] = args.ty
    
    ilda_data = svg_to_laser_json(args.input_svg)
    if ilda_data:
        write_ilda_file(ilda_data, args.output_ild)
        print(f"转换成功！参数：缩放={args.scale}X, 平移=({args.tx},{args.ty})")
        print(f"生成激光点：{len(ilda_data[0]['data'])}个")
    else:
        print("转换失败：未生成有效数据")