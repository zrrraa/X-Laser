import struct
from collections import OrderedDict
from xml.etree import ElementTree as ET
from svg.path import parse_path
import json
import math
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
import sys
import serial
import serial.tools.list_ports
from PIL import Image, ImageDraw, ImageTk


# --------------------------------------
# 全局配置
# --------------------------------------
CONFIG = {
    'samples_per_unit': 30,
    'min_samples': 5,
    'canvas_size': 1024,
    'ilda_range': (-32767, 32767),
    'endpoint_blanking': 10,
    'manual_scale': 1.0,
    'manual_translate_x': 0,
    'manual_translate_y': 0
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


# --------------------------------------
# SVG 转 ILD 相关函数
# --------------------------------------
def svg_to_laser_json(svg_file, scale=1.0, tx=0, ty=0):
    CONFIG['manual_scale'] = scale
    CONFIG['manual_translate_x'] = tx
    CONFIG['manual_translate_y'] = ty
    tree = ET.parse(svg_file)
    root = tree.getroot()
    svg_width, svg_height, viewbox = parse_svg_dimensions(root)
    scale_, offset_x, offset_y = calculate_normalization(root, svg_width, svg_height, viewbox)
    elements = []
    for elem in root.iter():
        if elem.tag.endswith('path') and elem.get('stroke') != 'none':
            process_path(elem, elements, scale_, offset_x, offset_y)
    if not elements:
        return None
    optimized_elements = optimize_drawing_sequence(elements)
    return convert_to_ilda_format(optimized_elements)


def parse_svg_dimensions(root):
    viewbox = root.get('viewBox')
    if viewbox:
        _, _, vb_w, vb_h = map(float, viewbox.split())
        return vb_w, vb_h, viewbox
    else:
        width = float(root.get('width', CONFIG['canvas_size']))
        height = float(root.get('height', CONFIG['canvas_size']))
        return width, height, None


def calculate_normalization(root, svg_w, svg_h, viewbox):
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
    offset_x = -(min_x + max_x)/2 * scale + CONFIG['canvas_size']/2
    offset_y = -(min_y + max_y)/2 * scale + CONFIG['canvas_size']/2
    return scale, offset_x, offset_y


def process_path(elem, elements, scale, offset_x, offset_y):
    path = parse_path(elem.get('d'))
    color = elem.get('stroke', 'black').lower()
    points = []
    canvas_center = CONFIG['canvas_size'] / 2
    for segment in path:
        seg_length = segment.length() * scale
        samples = max(CONFIG['min_samples'], int(seg_length / CONFIG['samples_per_unit']) + 1)
        for t in np.linspace(0, 1, samples):
            pt = segment.point(t)
            x_base = pt.real * scale + offset_x
            y_base = CONFIG['canvas_size'] - (pt.imag * scale + offset_y)
            x_centered = (x_base - canvas_center) * CONFIG['manual_scale'] + canvas_center
            y_centered = (y_base - canvas_center) * CONFIG['manual_scale'] + canvas_center
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
    return [create_blanking_point(*point) for _ in range(CONFIG['endpoint_blanking'])]


def create_blanking_point(x, y):
    return {
        'x': scale_coord(x),
        'y': scale_coord(y),
        'z': 0,
        'status': {'blanking': 1, 'last_point': 0},
        'color_index': 0
    }


def scale_coord(value):
    normalized = (value / CONFIG['canvas_size'] - 0.5) * 2
    return int(normalized * CONFIG['ilda_range'][1])


def distance(p1, p2):
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


# --------------------------------------
# ILDA 解析和转换函数
# --------------------------------------
def parse_ilda_file(filename):
    with open(filename, 'rb') as f:
        data = f.read()
    ptr = 0
    result = []
    current_palettes = {}
    while ptr < len(data):
        header = data[ptr:ptr+32]
        if len(header) < 32:
            break
        ilda_id = header[0:4].decode('ascii', errors='ignore')
        if ilda_id != 'ILDA':
            raise ValueError("Invalid ILDA file header")
        format_code = header[7]
        name = header[8:16].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
        company = header[16:24].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
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
        if format_code == 0:
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
        elif format_code == 1:
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
        elif format_code == 2:
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
        elif format_code == 4:
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
        elif format_code == 5:
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


# --------------------------------------
# 转换为 GIF 函数
# --------------------------------------
def ilda_to_gif(ild_data, palettes, output_gif, canvas_size=800, fps=30):
    color_map = {
        0: (255, 0, 0),
        24: (0, 255, 0),
        16: (255, 255, 0),
        40: (0, 0, 255),
        48: (255, 0, 255),
        31: (0, 255, 255),
        56: (255, 255, 255),
        255: (0, 0, 0), # 上调64至255防止太接近64被判为黑色
    }
    def find_closest_color(target_index):
        predefined = list(color_map.keys())
        closest = min(predefined, key=lambda x: abs(x - target_index))
        return color_map[closest]
    def get_color(section_projector, color_index):
        if section_projector in palettes:
            palette = palettes[section_projector]
            if color_index < len(palette):
                return tuple(palette[color_index])
        if color_index in color_map:
            return color_map[color_index]
        return find_closest_color(color_index)
    def scale_point(val):
        return int((val + 32768) * (canvas_size / 65536))
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
            x = scale_point(point["x"])
            y = scale_point(-point["y"])
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
            duration=int(1000 / fps),
            loop=0,
            optimize=True
        )
        return True
    else:
        return False


# --------------------------------------
# 主程序类
# --------------------------------------
class LaserShowConverter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("X-Laser PC 控制端")
        self.geometry("900x750+20+20")
        self.resizable(False, False)

        # 设置窗口图标（跨平台）
        try:
            # PyInstaller 创建的临时文件夹路径
            base_path = sys._MEIPASS
        except Exception:
            # 正常开发环境下的路径
            base_path = os.path.abspath(".")
        self.iconbitmap(os.path.join(base_path, "icon.ico"))
        
        # 初始化串口相关属性
        self.serial_port = None
        self.available_ports = []
        self.stop_thread = False
        self.lock = threading.Lock()
        self.output_ild = os.path.abspath("output.ild")
        self.output_gif = os.path.abspath("output.gif")
        self.after_id = None
        self.frames = []
        self.current_frame = 0
        self.current_conversion_type = None  # 标记当前操作类型
        self.canvas_size = (300, 300)
        
        self.create_widgets()
        
        # 启动串口检测线程
        self.port_check_thread = threading.Thread(target=self.update_ports, daemon=True)
        self.port_check_thread.start()
        
        # 启动串口读取线程
        self.reader_thread = threading.Thread(target=self.read_serial_output, daemon=True)
        self.reader_thread.start()

    def create_widgets(self):
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TEntry", font=("Segoe UI", 10))

        # 顶部容器 - 左右布局
        top_container = ttk.Frame(self)
        top_container.pack(fill=tk.BOTH, expand=False, padx=10, pady=10)

        # 左侧面板（SVG+ILD功能区）
        left_frame = ttk.Frame(top_container, width=500)
        left_frame.pack_propagate(False)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)

        # SVG 转 ILD 分组框
        svg_group = ttk.LabelFrame(left_frame, text="SVG 转 ILD", padding="10")
        svg_group.pack(fill=tk.X, pady=5)
        self.svg_path = tk.StringVar()
        ttk.Label(svg_group, text="SVG 文件:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(svg_group, textvariable=self.svg_path, width=35).grid(
            row=0, column=1, padx=5, pady=2, sticky='ew')
        ttk.Button(svg_group, text="浏览...", command=self.select_svg).grid(
            row=0, column=2, padx=5, pady=2)
        
        ttk.Label(svg_group, text="X 平移:").grid(row=1, column=0, sticky="w", pady=2)
        self.tx_var = tk.IntVar(value=0)
        ttk.Entry(svg_group, textvariable=self.tx_var, width=10).grid(
            row=1, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(svg_group, text="Y 平移:").grid(row=2, column=0, sticky="w", pady=2)
        self.ty_var = tk.IntVar(value=0)
        ttk.Entry(svg_group, textvariable=self.ty_var, width=10).grid(
            row=2, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(svg_group, text="缩放倍数:").grid(row=3, column=0, sticky="w", pady=2)
        self.scale_var = tk.DoubleVar(value=1.0)
        ttk.Entry(svg_group, textvariable=self.scale_var, width=10).grid(
            row=3, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Button(svg_group, text="转换为 ILD", command=self.convert_svg_to_ild).grid(
            row=4, columnspan=3, pady=8)

        # ILD 预览分组框
        ild_group = ttk.LabelFrame(left_frame, text="ILD 预览", padding="10")
        ild_group.pack(fill=tk.X, pady=5)
        self.ild_path = tk.StringVar()
        ttk.Label(ild_group, text="ILD 文件:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(ild_group, textvariable=self.ild_path, width=35).grid(
            row=0, column=1, padx=5, pady=2, sticky='ew')
        ttk.Button(ild_group, text="浏览...", command=self.select_ild).grid(
            row=0, column=2, padx=5, pady=2)
        ttk.Button(ild_group, text="开始预览", command=self.convert_ild_to_gif).grid(
            row=1, columnspan=3, pady=8)

        # 右侧面板（预览区域）
        right_frame = ttk.Frame(top_container, width=350, height=350)
        right_frame.pack_propagate(False)
        right_frame.pack(side=tk.RIGHT, padx=10)
        ttk.Label(right_frame, text="预览区域", font=("Segoe UI", 12, "bold")).pack(pady=(0, 5))
        self.canvas = tk.Label(right_frame, bg="black", width=350, height=350)
        self.canvas.pack_propagate(False)
        self.canvas.pack()

        # 底部容器 - 串口传输区域
        bottom_container = ttk.LabelFrame(self, text="串口传输", padding="10")
        bottom_container.pack(fill=tk.X, padx=10, pady=5)

        # 端口选择行
        port_frame = ttk.Frame(bottom_container)
        port_frame.pack(pady=2)
        ttk.Label(port_frame, text="选择串口:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combobox = ttk.Combobox(port_frame, textvariable=self.port_var, width=40)
        self.port_combobox.pack(side=tk.LEFT, padx=5)

        # 文件选择行
        file_frame = ttk.Frame(bottom_container)
        file_frame.pack(pady=2)
        self.file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_var, width=50, state='readonly').pack(
            side=tk.LEFT)
        ttk.Button(file_frame, text="选择文件", command=self.select_file).pack(
            side=tk.LEFT, padx=5)

        # 操作按钮行
        btn_frame = ttk.Frame(bottom_container)
        btn_frame.pack(pady=5)
        self.send_btn = ttk.Button(btn_frame, text="发送文件", command=self.start_send)
        self.send_btn.pack(side=tk.LEFT, padx=5)
        self.clear_btn = ttk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT)

        # 日志显示区域
        log_frame = ttk.Frame(bottom_container)
        log_frame.pack(pady=5)
        ttk.Label(log_frame, text="传输日志:", anchor='w').pack(fill=tk.X)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state='disabled')
        self.log_text.pack(fill=tk.X)

        # 状态栏
        self.status_lbl = ttk.Label(self, text="等待操作...", foreground="white",
                                  background="#2e2e2e", font=("Segoe UI", 9))
        self.status_lbl.pack(side=tk.BOTTOM, anchor="w", fill=tk.X)
        
    def select_svg(self):
        path = filedialog.askopenfilename(filetypes=[("SVG Files", "*.svg")])
        if path:
            self.svg_path.set(path)

    def select_ild(self):
        path = filedialog.askopenfilename(filetypes=[("ILDA Files", "*.ild")])
        if path:
            self.ild_path.set(path)
            self.file_var.set(path)

    def convert_svg_to_ild(self):
        svg_path = self.svg_path.get()
        if not os.path.exists(svg_path):
            messagebox.showerror("错误", "无效的 SVG 文件路径")
            return
        try:
            scale = self.scale_var.get()
            tx = self.tx_var.get()
            ty = self.ty_var.get()
        except tk.TclError:
            messagebox.showerror("错误", "请输入有效的数值参数")
            return

        self.status_lbl.config(text=f"正在转换 SVG 到 ILD... 输出：{self.output_ild}")
        self.current_conversion_type = 'svg'  # 设置为 SVG 转 ILD 类型
        thread = threading.Thread(target=self._convert_svg,
                                  args=(svg_path, scale, tx, ty),
                                  daemon=True)
        thread.start()
        self.after(100, self.check_conversion_thread, thread)

    def _convert_svg(self, svg_path, scale, tx, ty):
        try:
            ilda_data = svg_to_laser_json(svg_path, scale, tx, ty)
            if not ilda_data:
                raise ValueError("未生成有效数据")
            write_ilda_file(ilda_data, self.output_ild)

            # 新增：直接使用 ilda_data 生成 GIF
            success = ilda_to_gif(ilda_data, {},
                                  self.output_gif,
                                  canvas_size=200,
                                  fps=30)
            self.conversion_ok = success
            self.file_var.set(self.output_ild)
            print(f"转换成功！ILDA 文件已保存至：{self.output_ild}")
            print(f"GIF 文件已保存至：{self.output_gif}")
        except Exception as e:
            self.conversion_ok = False
            print(f"转换失败：{e}")

    def convert_ild_to_gif(self):
        input_path = self.ild_path.get()
        if not os.path.exists(input_path):
            messagebox.showerror("错误", "请先选择一个有效的 ILD 文件")
            return
        self.status_lbl.config(text=f"转换中，请稍候...")
        self.file_var.set(input_path)
        self.current_conversion_type = 'ild'  # 设置为 ILD 预览类型
        thread = threading.Thread(target=self._convert_ild,
                                  args=(input_path, ),
                                  daemon=True)
        thread.start()
        self.after(100, self.check_conversion_thread, thread)

    def _convert_ild(self, input_path):
        try:
            ild_data, palettes = parse_ilda_file(input_path)
            success = ilda_to_gif(ild_data,
                                  palettes,
                                  self.output_gif,
                                  canvas_size=200,
                                  fps=30)
            self.conversion_ok = success
        except Exception as e:
            self.conversion_ok = False
            print(f"转换失败：{e}")

    def check_conversion_thread(self, thread):
        if thread.is_alive():
            self.after(100, self.check_conversion_thread, thread)
        else:
            if hasattr(self, 'conversion_ok') and self.conversion_ok:
                if self.current_conversion_type == 'svg':
                    status_text = (
                        f"转换完成，文件已生成：\n"
                        f"ILDA: {self.output_ild}\n"
                        f"GIF: {self.output_gif}"
                    )
                elif self.current_conversion_type == 'ild':
                    status_text = f"转换完成，GIF文件已生成：\n{self.output_gif}"
                else:
                    status_text = "转换完成"
                self.status_lbl.config(text=status_text)
                self.load_and_play_gif(self.output_gif)
            else:
                self.status_lbl.config(text="转换失败，请检查输入文件和参数")

    def load_and_play_gif(self, gif_path):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.frames.clear()
        self.canvas.configure(image=None)
        try:
            self.gif = Image.open(gif_path)
        except Exception as e:
            messagebox.showerror("错误", f"无法加载 GIF 文件: {e}")
            return
        try:
            while True:
                # 强制缩放到固定尺寸
                frame = self.gif.copy().convert("RGB").resize(self.canvas_size, Image.LANCZOS)
                self.frames.append(ImageTk.PhotoImage(frame))
                self.gif.seek(len(self.frames))  # 获取下一帧
        except EOFError:
            pass
        if not self.frames:
            messagebox.showerror("错误", "GIF 文件中没有有效帧")
            return
        self.current_frame = 0
        self.update_frame()

    def update_frame(self):
        frame = self.frames[self.current_frame]
        self.canvas.configure(image=frame)
        self.current_frame = (self.current_frame + 1) % len(self.frames)
        delay = self.gif.info.get('duration', 100)
        self.after_id = self.after(delay, self.update_frame)

    # 新增的串口功能方法
    def update_ports(self):
        while not self.stop_thread:
            ports = serial.tools.list_ports.comports()
            port_list = [f"{p.device} ({p.description.split(' ')[0]})" for p in ports]
            
            if port_list != self.available_ports:
                self.available_ports = port_list
                self.port_combobox['values'] = self.available_ports
                if self.available_ports:
                    self.port_combobox.current(0)
            time.sleep(1)

    def read_serial_output(self):
        while not self.stop_thread:
            with self.lock:  # 使用锁保护整个条件判断和操作
                if self.serial_port and self.serial_port.is_open:
                    try:
                        if self.serial_port.in_waiting > 0:  # 此时 in_waiting 是安全的
                            output = self.serial_port.readline().decode(errors='ignore').strip()
                            if output:
                                self.after(0, self.log_message, f"ESP32 >> {output}")
                    except serial.SerialException as e:
                        # 捕获串口异常并清理资源
                        self.after(0, self.log_message, f"串口异常: {str(e)}")
                        if self.serial_port:
                            self.serial_port.close()
                            self.serial_port = None
            time.sleep(0.01)

    def select_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.file_var.set(file_path)

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)

    def start_send(self):
        if not self.file_var.get():
            messagebox.showwarning("错误", "请选择要发送的文件")
            return

        selected_port = self.port_var.get().split(' ')[0]
        if not selected_port:
            messagebox.showwarning("错误", "请选择有效的串口")
            return

        # 尝试打开串口
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                
            self.serial_port = serial.Serial(selected_port, 921600, timeout=1)
            time.sleep(0.5)
            self.status_lbl.config(text=f"已连接到 {selected_port}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开串口: {str(e)}")
            return

        # 禁用按钮
        self.send_btn.config(state=tk.DISABLED)
        self.log_message(f"开始传输文件: {self.file_var.get()}")

        # 启动发送线程
        send_thread = threading.Thread(target=self.send_file, args=(self.file_var.get(),))
        send_thread.daemon = True
        send_thread.start()

    def send_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                # 发送文件头
                header = f"FILENAME:{file_name}:{file_size}:"
                self.log_message(f"发送文件头: {header.strip()}")
                
                with self.lock:
                    self.serial_port.write(header.encode())
                
                # 等待ESP32就绪
                time.sleep(0.5)
                if self.serial_port.in_waiting > 0:
                    with self.lock:
                        response = self.serial_port.readline().decode().strip()
                    if "READY" not in response:
                        self.log_message(f"设备未就绪: {response}")
                        self.serial_port.close()
                        self.send_btn.config(state=tk.NORMAL)
                        return
                
                # 更新发送状态
                self.after(0, lambda: self.status_lbl.config(text="发送中，请稍等……"))

                # 发送文件内容
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    with self.lock:
                        self.serial_port.write(chunk)
                    time.sleep(0.01)  # 防止缓冲区溢出
                
                self.log_message("文件传输完成")
        
        except Exception as e:
            self.log_message(f"传输失败: {str(e)}")
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.send_btn.config(state=tk.NORMAL)
            self.status_lbl.config(text="就绪")

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

    def on_close(self):
        self.stop_thread = True
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.destroy()

# --------------------------------------
# 启动主循环
# --------------------------------------
if __name__ == "__main__":
    app = LaserShowConverter()
    app.mainloop()
