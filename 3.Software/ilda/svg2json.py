import xml.etree.ElementTree as ET
from svg.path import parse_path
import json
import math
import numpy as np

# 配置参数
CONFIG = {
    'samples_per_unit': 30,        # 每单位长度采样数
    'min_samples': 5,              # 单路径最少采样点数
    'canvas_size': 512,           # 标准化画布尺寸
    'ilda_range': (-32767, 32767), # ILDA坐标范围
    'endpoint_blanking': 10         # 路径起止点空白点数
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

def svg_to_laser_json(svg_file, output_json):
    tree = ET.parse(svg_file)
    root = tree.getroot()
    
    # 解析SVG尺寸
    svg_width, svg_height, viewbox = parse_svg_dimensions(root)
    
    # 计算标准化参数
    scale, offset_x, offset_y = calculate_normalization(root, svg_width, svg_height, viewbox)
    
    # 处理路径元素
    elements = []
    for elem in root.iter():
        if elem.tag.endswith('path') and elem.get('stroke') != 'none':
            process_path(elem, elements, scale, offset_x, offset_y)
    
    if not elements:
        print("警告：未找到有效路径")
        return
    
    # 优化绘制顺序
    optimized_elements = optimize_drawing_sequence(elements)
    
    # 生成ILDA数据
    ilda_data = convert_to_ilda_format(optimized_elements)
    
    # 写入JSON文件
    with open(output_json, 'w') as f:
        json.dump(ilda_data, f, indent=2)
    print(f"转换完成，共生成 {len(ilda_data[0]['data'])} 个激光点")

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
    
    # 计算内容边界
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    
    # 计算缩放比例
    content_width = max_x - min_x
    content_height = max_y - min_y
    scale = 0.95 * CONFIG['canvas_size'] / max(content_width, content_height, 1e-6)
    
    # 计算偏移量
    offset_x = - (min_x + max_x)/2 * scale + CONFIG['canvas_size']/2
    offset_y = - (min_y + max_y)/2 * scale + CONFIG['canvas_size']/2
    
    return scale, offset_x, offset_y

def process_path(elem, elements, scale, offset_x, offset_y):
    """处理单个路径元素"""
    path = parse_path(elem.get('d'))
    color = elem.get('stroke', 'black').lower()
    
    points = []
    for segment in path:
        # 计算采样数量
        seg_length = segment.length() * scale
        samples = max(
            CONFIG['min_samples'],
            int(seg_length / CONFIG['samples_per_unit']) + 1
        )
        
        # 生成采样点
        for t in np.linspace(0, 1, samples):
            pt = segment.point(t)
            x = pt.real * scale + offset_x
            y = CONFIG['canvas_size'] - (pt.imag * scale + offset_y)  # Y轴翻转
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
        
        # 遍历所有剩余路径的起点和终点
        for elem in remaining:
            for check_reverse in [False, True]:
                target_pos = elem['end'] if check_reverse else elem['start']
                
                if current_pos is None:  # 首个元素选择最近的起点
                    dist = distance((0,0), target_pos)
                else:
                    dist = distance(current_pos, target_pos)
                
                if dist < best_distance:
                    best_distance = dist
                    best_elem = elem
                    reverse = check_reverse
        
        if best_elem:
            # 反转路径点顺序
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
        # 添加起始点空白
        laser_points.extend(generate_endpoint_blanking(elem['start']))
        
        # 添加路径点
        color_index = COLOR_MAP.get(elem['color'], 0)
        for x, y in elem['points']:
            laser_points.append({
                'x': scale_coord(x),
                'y': scale_coord(y),
                'z': 0,
                'status': {'blanking': 0, 'last_point': 0},
                'color_index': color_index
            })
        
        # 添加结束点空白
        laser_points.extend(generate_endpoint_blanking(elem['end']))
    
    # 设置最终点标记（最后一个空白点）
    if laser_points:
        # 移除最后一个空白点的last_point标记
        for p in reversed(laser_points):
            if p['status']['blanking'] == 1:
                p['status']['last_point'] = 1
                break
    
    return [{
        "format_code": 0,
        "name": "HOLE",
        "company": "ZRRRAA",
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python svg2json.py input.svg output.json")
        sys.exit(1)
    svg_to_laser_json(sys.argv[1], sys.argv[2])