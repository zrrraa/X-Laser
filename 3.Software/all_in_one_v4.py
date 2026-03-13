import struct
from collections import OrderedDict
from xml.etree import ElementTree as ET
from svg.path import parse_path, Line, CubicBezier, QuadraticBezier, Arc
import math
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
import sys
import queue
import serial
import serial.tools.list_ports
from PIL import Image, ImageDraw, ImageTk, ImageColor



# --------------------------------------
# 全局配置
# --------------------------------------
CONFIG = {
    'canvas_size': 1024,
    'ilda_range': (-32767, 32767),
    'manual_scale': 1.0,
    'manual_translate_x': 0,
    'manual_translate_y': 0,
    'flip_horizontal': False,
    'flip_vertical': False,
    'laser_pps': 30000
}

PALETTE_RGB = {
    9: (255, 0, 0),
    18: (255, 255, 0),
    27: (0, 255, 0),
    36: (0, 255, 255),
    45: (0, 0, 255),
    54: (255, 0, 255),
    63: (255, 255, 255),
    64: (0, 0, 0)
}

QUALITY_LEVELS = {
    1: '极速', 2: '极速+', 3: '很低', 4: '很低+', 5: '低',
    6: '低+', 7: '较低', 8: '较低+', 9: '中低', 10: '标准',
    11: '标准+', 12: '中高', 13: '中高+', 14: '较高', 15: '较高+',
    16: '高', 17: '高+', 18: '很高', 19: '很高+', 20: '极致'
}


# --------------------------------------
# SVG 转 ILD 相关函数
# --------------------------------------
def interpolate_value(level, start_value, end_value, max_level=12):
    level = max(1, min(max_level, int(level)))
    if max_level <= 1:
        return start_value
    t = (level - 1) / (max_level - 1)
    return start_value + (end_value - start_value) * t


def map_quality_to_internal_params(quality_level):
    level = max(1, min(20, int(quality_level)))
    return {
        'quality_level': level,
        'quality_name': QUALITY_LEVELS[level],
        'visible_spacing': interpolate_value(level, 56.0, 7.0, max_level=20),
        'curve_density': interpolate_value(level, 1.00, 2.85, max_level=20),
        'min_samples': int(round(interpolate_value(level, 2.0, 8.0, max_level=20))),
        'blank_spacing': interpolate_value(level, 132.0, 22.0, max_level=20),
        'visible_begin_dwell': int(round(interpolate_value(level, 0.0, 3.0, max_level=20))),
        'visible_end_dwell': int(round(interpolate_value(level, 1.0, 4.0, max_level=20))),
        'blank_begin_dwell': int(round(interpolate_value(level, 0.0, 3.0, max_level=20))),
        'blank_end_dwell': int(round(interpolate_value(level, 1.0, 5.0, max_level=20))),
        'corner_dwell_max': int(round(interpolate_value(level, 1.0, 8.0, max_level=20))),
        'closed_overlap_points': int(round(interpolate_value(level, 1.0, 8.0, max_level=20))),
        'entry_seam_penalty': interpolate_value(level, 18.0, 40.0, max_level=20),
        'close_threshold': interpolate_value(level, 9.0, 18.0, max_level=20),
        'subpath_break_threshold': interpolate_value(level, 15.0, 28.0, max_level=20),
        'output_simplify_tolerance': interpolate_value(level, 2.40, 0.18, max_level=20),
        'short_blank_threshold': interpolate_value(level, 12.0, 26.0, max_level=20),
        'continuity_bonus': interpolate_value(level, 10.0, 34.0, max_level=20),
        'continuity_angle_weight': interpolate_value(level, 0.18, 0.72, max_level=20),
        'loop_return': True,
        # 兼容旧变量名
        'samples_per_unit': interpolate_value(level, 56.0, 7.0, max_level=20),
        'endpoint_blanking': int(round(interpolate_value(level, 2.0, 8.0, max_level=20)))
    }

def svg_to_laser_json(svg_file, scale=1.0, tx=0, ty=0, flip_h=False, flip_v=False, scan_config=None):
    if scan_config is None:
        scan_config = map_quality_to_internal_params(10)
    scan_config = dict(scan_config)

    CONFIG.update({
        'manual_scale': scale,
        'manual_translate_x': tx,
        'manual_translate_y': ty,
        'flip_horizontal': flip_h,
        'flip_vertical': flip_v
    })

    tree = ET.parse(svg_file)
    root = tree.getroot()
    svg_width, svg_height, viewbox = parse_svg_dimensions(root)
    scale_, offset_x, offset_y = calculate_normalization(root, svg_width, svg_height, viewbox)

    elements = []
    for elem in root.iter():
        if elem.tag.endswith('path') and elem.get('stroke') != 'none':
            elements.extend(process_path(elem, scale_, offset_x, offset_y, scan_config))

    if not elements:
        return None

    optimized_elements = optimize_drawing_sequence(elements, scan_config)
    section = convert_to_ilda_format(optimized_elements, scan_config)
    return [section]


def parse_svg_dimensions(root):
    viewbox = root.get('viewBox')
    if viewbox:
        _, _, vb_w, vb_h = map(float, viewbox.split())
        return vb_w, vb_h, viewbox
    width = float(root.get('width', CONFIG['canvas_size']))
    height = float(root.get('height', CONFIG['canvas_size']))
    return width, height, None


def calculate_normalization(root, svg_w, svg_h, viewbox):
    all_points = []
    for elem in root.iter():
        if elem.tag.endswith('path') and elem.get('d'):
            path = parse_path(elem.get('d'))
            for segment in path:
                try:
                    sample_count = 10 if isinstance(segment, Line) else 20
                    for t in np.linspace(0, 1, sample_count):
                        pt = segment.point(t)
                        all_points.append((pt.real, pt.imag))
                except Exception:
                    continue

    if not all_points:
        return 1.0, 0.0, 0.0

    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    content_width = max_x - min_x
    content_height = max_y - min_y
    scale = 0.95 * CONFIG['canvas_size'] / max(content_width, content_height, 1e-6)
    offset_x = -(min_x + max_x) / 2 * scale + CONFIG['canvas_size'] / 2
    offset_y = -(min_y + max_y) / 2 * scale + CONFIG['canvas_size'] / 2
    return scale, offset_x, offset_y


def process_path(elem, scale, offset_x, offset_y, scan_config):
    path = parse_path(elem.get('d'))
    color_index = svg_color_to_index(elem.get('stroke', 'white'))
    strokes = []
    current_points = []

    for segment in path:
        sampled_points = sample_segment(segment, scale, offset_x, offset_y, scan_config)
        if not sampled_points:
            continue

        start_point = sampled_points[0]
        if current_points and point_distance(current_points[-1], start_point) > scan_config['subpath_break_threshold']:
            finalized = finalize_stroke(current_points, color_index, scan_config)
            if finalized is not None:
                strokes.append(finalized)
            current_points = sampled_points[:]
        else:
            if current_points and point_distance(current_points[-1], start_point) <= 1.0:
                current_points.extend(sampled_points[1:])
            else:
                current_points.extend(sampled_points)

    finalized = finalize_stroke(current_points, color_index, scan_config)
    if finalized is not None:
        strokes.append(finalized)
    return strokes


def sample_segment(segment, scale, offset_x, offset_y, scan_config):
    try:
        seg_length = max(0.0, float(segment.length()) * scale)
    except Exception:
        seg_length = 0.0

    base_samples = max(scan_config['min_samples'], int(seg_length / scan_config['visible_spacing']) + 1)
    if not isinstance(segment, Line):
        base_samples = max(base_samples + 1, int(math.ceil(base_samples * scan_config['curve_density'])))
    base_samples = max(2, min(800, base_samples))

    points = []
    for t in np.linspace(0, 1, base_samples):
        pt = segment.point(t)
        points.append(transform_point(pt.real, pt.imag, scale, offset_x, offset_y))
    return dedupe_consecutive(points)


def transform_point(x_raw, y_raw, scale, offset_x, offset_y):
    canvas_center = CONFIG['canvas_size'] / 2
    canvas_size = CONFIG['canvas_size']

    x_base = x_raw * scale + offset_x
    y_base = CONFIG['canvas_size'] - (y_raw * scale + offset_y)

    if CONFIG['flip_horizontal']:
        x_base = canvas_size - x_base
    if CONFIG['flip_vertical']:
        y_base = canvas_size - y_base

    x_centered = (x_base - canvas_center) * CONFIG['manual_scale'] + canvas_center
    y_centered = (y_base - canvas_center) * CONFIG['manual_scale'] + canvas_center
    x = x_centered + CONFIG['manual_translate_x']
    y = y_centered + CONFIG['manual_translate_y']
    return (x, y)


def finalize_stroke(points, color_index, scan_config):
    points = dedupe_consecutive(points)
    if len(points) < 2:
        return None

    close_threshold = scan_config['close_threshold']
    closed = point_distance(points[0], points[-1]) <= close_threshold
    if closed and point_distance(points[0], points[-1]) > 0:
        points[-1] = points[0]

    simplify_tolerance = scan_config.get('output_simplify_tolerance', 0.8)
    if len(points) >= 4:
        simplified = simplify_polyline(points, simplify_tolerance, closed=closed)
        simplified = dedupe_consecutive(simplified, tolerance=0.12)
        if len(simplified) >= 2:
            points = simplified
            if closed and point_distance(points[0], points[-1]) > 1e-6:
                points.append(points[0])

    rounded_closed = closed and is_rounded_closed_contour(points)

    return {
        'points': points,
        'color_index': color_index,
        'closed': closed,
        'rounded_closed': rounded_closed,
        'start': points[0],
        'end': points[-1]
    }


def dedupe_consecutive(points, tolerance=0.25):
    if not points:
        return []
    out = [points[0]]
    for pt in points[1:]:
        if point_distance(out[-1], pt) > tolerance:
            out.append(pt)
    return out


def is_rounded_closed_contour(points):
    if len(points) < 10:
        return False
    ring = points[:-1] if point_distance(points[0], points[-1]) <= 1e-6 else points[:]
    if len(ring) < 8:
        return False

    angles = []
    sharp_count = 0
    for i in range(len(ring)):
        a = ring[i - 1]
        b = ring[i]
        c = ring[(i + 1) % len(ring)]
        angle = corner_angle_degrees(a, b, c)
        angles.append(angle)
        if angle < 125:
            sharp_count += 1

    avg_angle = sum(angles) / len(angles)
    return sharp_count <= max(2, int(len(ring) * 0.08)) and avg_angle > 145


def optimize_svg_strokes(elements, scan_config):
    if not elements:
        return []

    prepared = []
    for elem in elements:
        normalized = prepare_stroke_for_optimization(elem, scan_config)
        if normalized is not None:
            prepared.append(normalized)

    if len(prepared) < 2:
        return prepared

    merge_threshold = scan_config.get('svg_merge_threshold', 12.0)
    angle_threshold = scan_config.get('svg_merge_angle_threshold', 90.0)
    bridge_spacing = scan_config.get('svg_merge_bridge_spacing', 12.0)

    remaining = [clone_simple_element(elem) for elem in prepared]
    optimized = []

    while remaining:
        current = remaining.pop(0)
        if current.get('closed'):
            optimized.append(current)
            continue

        merged_any = True
        while merged_any and remaining:
            merged_any = False
            best_idx = None
            best_candidate = None
            best_score = float('inf')

            for idx, other in enumerate(remaining):
                if other.get('closed') or other['color_index'] != current['color_index']:
                    continue
                for reverse_current in (False, True):
                    current_pts = current['points'][::-1] if reverse_current else current['points']
                    for reverse_other in (False, True):
                        other_pts = other['points'][::-1] if reverse_other else other['points']
                        candidate = evaluate_stroke_merge(current_pts, other_pts, merge_threshold, angle_threshold)
                        if candidate and candidate['score'] < best_score:
                            best_score = candidate['score']
                            best_idx = idx
                            best_candidate = {
                                'current_points': current_pts,
                                'other_points': other_pts,
                                **candidate
                            }

            if best_candidate is not None:
                merged_points = merge_stroke_points(
                    best_candidate['current_points'],
                    best_candidate['other_points'],
                    best_candidate['gap'],
                    bridge_spacing
                )
                current = prepare_stroke_for_optimization({
                    'points': merged_points,
                    'color_index': current['color_index'],
                    'closed': False,
                    'rounded_closed': False,
                    'start': merged_points[0],
                    'end': merged_points[-1]
                }, scan_config, force_open=True)
                remaining.pop(best_idx)
                merged_any = current is not None

        if current is not None:
            optimized.append(current)

    return optimized


def clone_simple_element(elem):
    return {
        'points': elem['points'][:],
        'color_index': elem['color_index'],
        'closed': elem.get('closed', False),
        'rounded_closed': elem.get('rounded_closed', False),
        'start': elem['points'][0],
        'end': elem['points'][-1]
    }


def prepare_stroke_for_optimization(elem, scan_config, force_open=False):
    points = dedupe_consecutive(elem.get('points', []))
    if len(points) < 2:
        return None

    closed = False if force_open else (elem.get('closed', False) or point_distance(points[0], points[-1]) <= scan_config['close_threshold'])
    tolerance = scan_config.get('svg_simplify_tolerance', 1.0)
    simplified = simplify_polyline(points, tolerance, closed=closed)
    simplified = dedupe_consecutive(simplified)
    if len(simplified) < 2:
        simplified = points

    if closed:
        if point_distance(simplified[0], simplified[-1]) > 1e-6:
            simplified.append(simplified[0])
        else:
            simplified[-1] = simplified[0]

    rounded_closed = closed and is_rounded_closed_contour(simplified)
    return {
        'points': simplified,
        'color_index': elem['color_index'],
        'closed': closed,
        'rounded_closed': rounded_closed,
        'start': simplified[0],
        'end': simplified[-1]
    }


def simplify_polyline(points, tolerance, closed=False):
    if len(points) <= 2:
        return points[:]

    work = points[:]
    if closed and point_distance(work[0], work[-1]) <= 1e-6:
        work = work[:-1]
    if len(work) <= 2:
        return points[:]

    if closed:
        anchor_idx = min(range(len(work)), key=lambda i: (work[i][0], work[i][1]))
        work = work[anchor_idx:] + work[:anchor_idx] + [work[anchor_idx]]

    simplified = rdp_polyline(work, tolerance)
    if closed and point_distance(simplified[0], simplified[-1]) > 1e-6:
        simplified.append(simplified[0])
    return simplified


def rdp_polyline(points, epsilon):
    if len(points) <= 2:
        return points[:]

    start = points[0]
    end = points[-1]
    max_dist = -1.0
    max_idx = 0
    for i in range(1, len(points) - 1):
        dist = point_to_segment_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = rdp_polyline(points[:max_idx + 1], epsilon)
        right = rdp_polyline(points[max_idx:], epsilon)
        return left[:-1] + right
    return [start, end]


def point_to_segment_distance(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    qx = ax + dx * t
    qy = ay + dy * t
    return math.hypot(px - qx, py - qy)


def average_point(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def evaluate_stroke_merge(current_pts, other_pts, merge_threshold, angle_threshold):
    if len(current_pts) < 2 or len(other_pts) < 2:
        return None

    end_pt = current_pts[-1]
    next_pt = other_pts[0]
    gap_sq = point_distance(end_pt, next_pt)
    gap = math.sqrt(gap_sq)
    if gap > merge_threshold:
        return None

    tail_angle = path_heading(current_pts[-2], current_pts[-1])
    head_angle = path_heading(other_pts[0], other_pts[1])

    if gap > 1e-6:
        bridge_angle = path_heading(end_pt, next_pt)
        angle1 = heading_delta_deg(tail_angle, bridge_angle)
        angle2 = heading_delta_deg(bridge_angle, head_angle)
    else:
        angle1 = 0.0
        angle2 = heading_delta_deg(tail_angle, head_angle)

    combined_angle = max(angle1, angle2)
    if combined_angle > angle_threshold:
        return None

    score = gap * 1.8 + angle1 * 0.7 + angle2 * 0.9
    return {'gap': gap, 'score': score}


def merge_stroke_points(current_pts, other_pts, gap, bridge_spacing):
    merged = current_pts[:]
    start = current_pts[-1]
    end = other_pts[0]

    if gap > 1.0:
        bridge_count = max(0, int(gap / max(2.0, bridge_spacing)))
        for idx in range(1, bridge_count + 1):
            t = idx / (bridge_count + 1)
            merged.append((
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t
            ))
        merged.append(end)
    elif point_distance(start, end) > 0.01:
        merged.append(end)

    if merged and other_pts:
        if point_distance(merged[-1], other_pts[0]) <= 0.01:
            merged.extend(other_pts[1:])
        else:
            merged.extend(other_pts)
    return merged


def path_heading(p1, p2):
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))


def heading_delta_deg(a, b):
    delta = (a - b + 180.0) % 360.0 - 180.0
    return abs(delta)


def optimize_drawing_sequence(elements, scan_config):
    sorted_elements = []
    remaining = elements[:]
    current_pos = None
    current_heading = None
    continuity_bonus = scan_config.get('continuity_bonus', 18.0)
    continuity_angle_weight = scan_config.get('continuity_angle_weight', 0.35)
    continuity_gap_threshold = scan_config.get('short_blank_threshold', 16.0)

    while remaining:
        best_idx = None
        best_candidate = None
        best_cost = float('inf')

        for idx, elem in enumerate(remaining):
            for candidate in build_entry_candidates(elem, current_pos, scan_config):
                ref_pos = (0.0, 0.0) if current_pos is None else current_pos
                gap_sq = point_distance(ref_pos, candidate['entry_point'])
                gap = math.sqrt(gap_sq)
                cost = gap_sq
                cost += candidate.get('entry_sharpness', 0.0) * scan_config['entry_seam_penalty']

                if current_pos is not None and current_heading is not None and len(candidate.get('points', [])) >= 2:
                    head_angle = path_heading(candidate['points'][0], candidate['points'][1])
                    angle_delta = heading_delta_deg(current_heading, head_angle)
                    cost += angle_delta * continuity_angle_weight
                    if gap <= continuity_gap_threshold:
                        gap_ratio = max(0.0, 1.0 - gap / max(1.0, continuity_gap_threshold))
                        angle_ratio = max(0.0, 1.0 - angle_delta / 180.0)
                        cost -= continuity_bonus * gap_ratio * angle_ratio

                if cost < best_cost:
                    best_cost = cost
                    best_idx = idx
                    best_candidate = candidate

        if best_candidate is None:
            break

        sorted_elements.append(best_candidate)
        current_pos = best_candidate['logical_end']
        if len(best_candidate.get('points', [])) >= 2:
            current_heading = path_heading(best_candidate['points'][-2], best_candidate['points'][-1])
        else:
            current_heading = None
        remaining.pop(best_idx)

    return sorted_elements


def build_entry_candidates(elem, current_pos, scan_config):
    if not elem['closed']:
        points = elem['points']
        return [
            build_open_candidate(points, elem['color_index'], reverse=False, scan_config=scan_config),
            build_open_candidate(points, elem['color_index'], reverse=True, scan_config=scan_config)
        ]

    ring = elem['points'][:-1] if point_distance(elem['points'][0], elem['points'][-1]) <= 1e-6 else elem['points'][:]
    candidates = []
    for reverse in (False, True):
        oriented_ring = ring[::-1] if reverse else ring[:]
        start_idx = choose_closed_start_index(oriented_ring, current_pos, scan_config)
        rotated = rotate_ring(oriented_ring, start_idx)
        overlap = 0
        logical_end = rotated[0]
        if elem['rounded_closed']:
            overlap = min(scan_config['closed_overlap_points'], max(2, len(rotated) // 8))
            overlap = min(overlap, max(1, len(rotated) // 3))
            logical_end = rotated[overlap]
        candidates.append({
            'points': rotated + [rotated[0]],
            'color_index': elem['color_index'],
            'closed': True,
            'rounded_closed': elem['rounded_closed'],
            'entry_point': rotated[0],
            'entry_sharpness': point_sharpness(oriented_ring, start_idx),
            'logical_end': logical_end,
            'closed_overlap_points': overlap
        })
    return candidates


def build_open_candidate(points, color_index, reverse, scan_config):
    pts = points[::-1] if reverse else points[:]
    entry_sharpness = 180.0 - corner_angle_degrees(pts[0], pts[1], pts[min(2, len(pts) - 1)]) if len(pts) >= 3 else 0.0
    return {
        'points': pts,
        'color_index': color_index,
        'closed': False,
        'rounded_closed': False,
        'entry_point': pts[0],
        'entry_sharpness': max(0.0, entry_sharpness),
        'logical_end': pts[-1],
        'closed_overlap_points': 0
    }


def choose_closed_start_index(ring, current_pos, scan_config):
    if not ring:
        return 0
    if current_pos is None:
        current_pos = (0.0, 0.0)
    step = max(1, len(ring) // 24)

    best_idx = 0
    best_cost = float('inf')
    candidate_indices = list(range(0, len(ring), step))
    if (len(ring) - 1) not in candidate_indices:
        candidate_indices.append(len(ring) - 1)

    for idx in candidate_indices:
        dist_cost = point_distance(current_pos, ring[idx])
        seam_cost = point_sharpness(ring, idx) * scan_config['entry_seam_penalty']
        cost = dist_cost + seam_cost
        if cost < best_cost:
            best_cost = cost
            best_idx = idx
    return best_idx


def rotate_ring(ring, start_idx):
    return ring[start_idx:] + ring[:start_idx]


def point_sharpness(ring, idx):
    if len(ring) < 3:
        return 0.0
    a = ring[idx - 1]
    b = ring[idx]
    c = ring[(idx + 1) % len(ring)]
    return max(0.0, 180.0 - corner_angle_degrees(a, b, c))


def snap_sequence_connections(sorted_elements, scan_config):
    if len(sorted_elements) < 2:
        return sorted_elements

    same_color_threshold = scan_config.get('svg_cross_color_snap_threshold', 10.0)
    cross_color_threshold = scan_config.get('svg_cross_color_join_threshold', 6.0)
    angle_threshold = min(150.0, scan_config.get('svg_merge_angle_threshold', 90.0) + 34.0)
    snap_tolerance = scan_config.get('svg_snap_tolerance', 1.0)

    snapped = [clone_sequence_candidate(elem) for elem in sorted_elements]
    for elem in snapped:
        elem['continuous_from_prev'] = False
        elem['continuous_to_next'] = False

    for idx in range(len(snapped) - 1):
        current = snapped[idx]
        nxt = snapped[idx + 1]
        if current.get('closed') or nxt.get('closed'):
            continue
        if len(current.get('points', [])) < 2 or len(nxt.get('points', [])) < 2:
            continue

        end_pt = current['points'][-1]
        next_pt = nxt['points'][0]
        gap = math.sqrt(point_distance(end_pt, next_pt))

        same_color = current.get('color_index') == nxt.get('color_index')
        join_threshold = same_color_threshold if same_color else cross_color_threshold
        if gap > join_threshold:
            continue

        tail_angle = path_heading(current['points'][-2], current['points'][-1])
        head_angle = path_heading(nxt['points'][0], nxt['points'][1])
        if gap > 1e-6:
            bridge_angle = path_heading(end_pt, next_pt)
            angle1 = heading_delta_deg(tail_angle, bridge_angle)
            angle2 = heading_delta_deg(bridge_angle, head_angle)
            direct_angle = heading_delta_deg(tail_angle, head_angle)
        else:
            angle1 = 0.0
            angle2 = heading_delta_deg(tail_angle, head_angle)
            direct_angle = angle2

        if max(angle1, angle2, direct_angle) > angle_threshold:
            continue

        if same_color:
            anchor = average_point(end_pt, next_pt) if gap > snap_tolerance else end_pt
        else:
            if gap > cross_color_threshold:
                continue
            anchor = average_point(end_pt, next_pt)

        current['points'][-1] = anchor
        current['logical_end'] = anchor
        current['end'] = anchor
        nxt['points'][0] = anchor
        nxt['entry_point'] = anchor
        nxt['start'] = anchor
        current['continuous_to_next'] = True
        nxt['continuous_from_prev'] = True

    return snapped


def rebuild_continuous_chain_geometry(sorted_elements, scan_config):
    if len(sorted_elements) < 2:
        return sorted_elements

    rebuilt = []
    idx = 0
    while idx < len(sorted_elements):
        chain = [clone_sequence_candidate(sorted_elements[idx])]
        j = idx
        while j < len(sorted_elements) - 1:
            cur = sorted_elements[j]
            nxt = sorted_elements[j + 1]
            if cur.get('closed') or nxt.get('closed'):
                break
            if not cur.get('continuous_to_next') or not nxt.get('continuous_from_prev'):
                break
            chain.append(clone_sequence_candidate(nxt))
            j += 1

        if len(chain) >= 2:
            rebuilt.extend(rebuild_single_chain(chain, scan_config))
        else:
            rebuilt.append(chain[0])
        idx = j + 1
    return rebuilt


def rebuild_single_chain(chain, scan_config):
    if len(chain) < 2:
        return chain

    original_lengths = [max(1e-6, polyline_length(elem['points'])) for elem in chain]
    total_original_length = sum(original_lengths)
    if total_original_length <= 1e-6:
        return chain

    mother_points = []
    for elem in chain:
        pts = dedupe_consecutive(elem['points'])
        if not pts:
            continue
        if not mother_points:
            mother_points.extend(pts)
        else:
            if point_distance(mother_points[-1], pts[0]) <= 1.0:
                mother_points.extend(pts[1:])
            else:
                mother_points.extend(pts)
    mother_points = dedupe_consecutive(mother_points)
    if len(mother_points) < 2:
        return chain

    mother_points = smooth_chain_polyline(mother_points, chain, scan_config)
    mother_points = dedupe_consecutive(mother_points, tolerance=0.1)
    mother_length = polyline_length(mother_points)
    if mother_length <= 1e-6 or len(mother_points) < 2:
        return chain

    rebuilt = []
    cumulative_original = 0.0
    previous_boundary = mother_points[0]
    for seg_idx, elem in enumerate(chain):
        seg_original_length = original_lengths[seg_idx]
        start_dist = mother_length * (cumulative_original / total_original_length)
        cumulative_original += seg_original_length
        end_dist = mother_length * (cumulative_original / total_original_length)
        if seg_idx == 0:
            start_point = mother_points[0]
        else:
            start_point = previous_boundary
        if seg_idx == len(chain) - 1:
            end_point = mother_points[-1]
        else:
            end_point = point_at_polyline_distance(mother_points, end_dist)

        desired_count = max(2, max(len(elem['points']), int(seg_original_length / max(2.0, scan_config['visible_spacing'])) + 1))
        seg_points = sample_polyline_interval(mother_points, start_dist, end_dist, desired_count)
        if seg_points:
            seg_points[0] = start_point
            seg_points[-1] = end_point
        seg_points = dedupe_consecutive(seg_points, tolerance=0.1)
        if len(seg_points) < 2:
            seg_points = [start_point, end_point]

        new_elem = clone_sequence_candidate(elem)
        new_elem['points'] = seg_points
        new_elem['entry_point'] = seg_points[0]
        new_elem['logical_end'] = seg_points[-1]
        new_elem['start'] = seg_points[0]
        new_elem['end'] = seg_points[-1]
        rebuilt.append(new_elem)
        previous_boundary = end_point

    return rebuilt


def smooth_chain_polyline(points, chain, scan_config):
    if len(points) < 3:
        return points

    iterations = estimate_chain_smoothing_iterations(chain, scan_config)
    if iterations <= 0:
        return points

    smoothed = points[:]
    for _ in range(iterations):
        smoothed = chaikin_open(smoothed)
        if len(smoothed) > 2500:
            break

    target_count = max(len(points), int(polyline_length(points) / max(3.0, scan_config['visible_spacing'] * 0.55)) + 1)
    target_count = min(2500, max(target_count, len(points)))
    resampled = sample_polyline_interval(smoothed, 0.0, polyline_length(smoothed), target_count)
    if resampled:
        resampled[0] = points[0]
        resampled[-1] = points[-1]
        return resampled
    return points


def estimate_chain_smoothing_iterations(chain, scan_config):
    joint_angles = []
    long_count = 0
    for idx in range(len(chain) - 1):
        a = dedupe_consecutive(chain[idx]['points'])
        b = dedupe_consecutive(chain[idx + 1]['points'])
        if len(a) < 2 or len(b) < 2:
            continue
        if polyline_length(a) > scan_config['visible_spacing'] * 1.8 and polyline_length(b) > scan_config['visible_spacing'] * 1.8:
            long_count += 1
        angle = corner_angle_degrees(a[-2], a[-1], b[1])
        joint_angles.append(angle)

    if not joint_angles:
        return 0

    avg_angle = sum(joint_angles) / len(joint_angles)
    min_angle = min(joint_angles)
    if min_angle < 70:
        return 0
    if avg_angle > 150 and len(chain) >= 3:
        return 2
    if avg_angle > 128 and len(chain) >= 2:
        return 1 if long_count >= 1 else 0
    return 0


def chaikin_open(points):
    if len(points) < 3:
        return points[:]
    out = [points[0]]
    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
        r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
        out.extend([q, r])
    out.append(points[-1])
    return dedupe_consecutive(out, tolerance=0.05)


def polyline_length(points):
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        total += math.sqrt(point_distance(points[i - 1], points[i]))
    return total


def point_at_polyline_distance(points, target_distance):
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]
    if target_distance <= 0.0:
        return points[0]

    accumulated = 0.0
    for i in range(1, len(points)):
        a = points[i - 1]
        b = points[i]
        seg_len = math.sqrt(point_distance(a, b))
        if seg_len <= 1e-9:
            continue
        if accumulated + seg_len >= target_distance:
            t = (target_distance - accumulated) / seg_len
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        accumulated += seg_len
    return points[-1]


def sample_polyline_interval(points, start_distance, end_distance, count):
    if count <= 1:
        return [point_at_polyline_distance(points, start_distance)]
    if end_distance < start_distance:
        start_distance, end_distance = end_distance, start_distance
    if abs(end_distance - start_distance) <= 1e-9:
        pt = point_at_polyline_distance(points, start_distance)
        return [pt, pt]
    ts = np.linspace(start_distance, end_distance, count)
    return [point_at_polyline_distance(points, t) for t in ts]


def clone_sequence_candidate(elem):
    cloned = dict(elem)
    if 'points' in elem:
        cloned['points'] = elem['points'][:]
        if cloned['points']:
            cloned['start'] = cloned['points'][0]
            cloned['end'] = cloned['points'][-1]
    return cloned


def convert_to_ilda_format(sorted_elements, scan_config):
    laser_points = []
    current_pos = None
    first_entry_point = None

    for elem in sorted_elements:
        entry_point = elem['points'][0]
        if first_entry_point is None:
            first_entry_point = entry_point

        if not elem.get('continuous_from_prev', False):
            laser_points.extend(build_blank_transition(current_pos, entry_point, scan_config))
        current_pos = entry_point

        begin_dwell = 0 if elem.get('continuous_from_prev', False) else None
        end_dwell = 0 if elem.get('continuous_to_next', False) else None

        if elem['closed'] and elem['rounded_closed'] and len(elem['points']) > 8:
            current_pos = emit_rounded_closed_stroke(laser_points, elem, scan_config, begin_dwell=begin_dwell, end_dwell=end_dwell)
        else:
            current_pos = emit_visible_polyline(
                laser_points,
                elem['points'],
                elem['color_index'],
                scan_config,
                begin_dwell=begin_dwell,
                end_dwell=end_dwell
            )

    if scan_config.get('loop_return') and first_entry_point is not None and current_pos is not None:
        laser_points.extend(build_blank_transition(current_pos, first_entry_point, scan_config))

    if laser_points:
        laser_points[-1]['status']['last_point'] = 1

    return {
        'format_code': 0,
        'name': 'SVG_IMAGE',
        'company': 'SVG2ILDA',
        'num_records': len(laser_points),
        'section_number': 0,
        'total_sections': 1,
        'projector': 0,
        'data': laser_points
    }


def emit_rounded_closed_stroke(laser_points, elem, scan_config, begin_dwell=None, end_dwell=None):
    ring = elem['points'][:-1]
    if len(ring) < 6:
        return emit_visible_polyline(
            laser_points,
            elem['points'],
            elem['color_index'],
            scan_config,
            begin_dwell=begin_dwell,
            end_dwell=end_dwell
        )

    overlap = elem.get('closed_overlap_points', 0)
    overlap = min(overlap, max(1, len(ring) // 3))
    overlap = max(1, overlap)

    pre_roll = ring[:overlap + 1]
    for pt in pre_roll:
        laser_points.append(create_laser_point(pt[0], pt[1], blanking=1, color_index=0))
    visible_points = ring[overlap:] + ring[:overlap + 1]
    return emit_visible_polyline(
        laser_points,
        visible_points,
        elem['color_index'],
        scan_config,
        begin_dwell=begin_dwell,
        end_dwell=end_dwell
    )


def generate_visible_ramp_points(points, count, at_begin=True):
    if count <= 0 or len(points) < 2:
        return []
    usable = max(1, min(len(points) - 1, 3))
    segment_end = points[usable] if at_begin else points[-usable - 1]
    anchor = points[0] if at_begin else points[-1]
    fractions = np.linspace(0.0, 0.32, count + 2)[1:-1]
    ramp = []
    for f in fractions:
        if at_begin:
            ramp.append((anchor[0] + (segment_end[0] - anchor[0]) * f, anchor[1] + (segment_end[1] - anchor[1]) * f))
        else:
            ramp.append((anchor[0] + (segment_end[0] - anchor[0]) * f, anchor[1] + (segment_end[1] - anchor[1]) * f))
    if not at_begin:
        ramp.reverse()
    return ramp


def emit_visible_polyline(laser_points, points, color_index, scan_config, begin_dwell=None, end_dwell=None):
    if not points:
        return None

    if begin_dwell is None:
        begin_dwell = scan_config['visible_begin_dwell']
    if end_dwell is None:
        end_dwell = scan_config['visible_end_dwell']

    begin_dwell = max(0, int(begin_dwell))
    end_dwell = max(0, int(end_dwell))

    lead_count = max(0, begin_dwell - 1)
    tail_count = max(0, end_dwell - 1)

    if begin_dwell > 0:
        laser_points.append(create_laser_point(points[0][0], points[0][1], blanking=0, color_index=color_index))
        for pt in generate_visible_ramp_points(points, lead_count, at_begin=True):
            laser_points.append(create_laser_point(pt[0], pt[1], blanking=0, color_index=color_index))

    for idx, pt in enumerate(points):
        laser_points.append(create_laser_point(pt[0], pt[1], blanking=0, color_index=color_index))
        if 0 < idx < len(points) - 1:
            extra_dwell = compute_corner_dwell(points[idx - 1], pt, points[idx + 1], scan_config['corner_dwell_max'])
            for _ in range(extra_dwell):
                laser_points.append(create_laser_point(pt[0], pt[1], blanking=0, color_index=color_index))

    if end_dwell > 0:
        for pt in generate_visible_ramp_points(points, tail_count, at_begin=False):
            laser_points.append(create_laser_point(pt[0], pt[1], blanking=0, color_index=color_index))
        laser_points.append(create_laser_point(points[-1][0], points[-1][1], blanking=0, color_index=color_index))
    return points[-1]


def build_blank_transition(start_point, end_point, scan_config):
    if end_point is None:
        return []

    transition = []
    blank_begin = max(0, int(scan_config['blank_begin_dwell']))
    blank_end = max(1, int(scan_config['blank_end_dwell']))
    short_threshold = max(2.0, float(scan_config.get('short_blank_threshold', 16.0)))

    if start_point is None:
        for _ in range(blank_end):
            transition.append(create_laser_point(end_point[0], end_point[1], blanking=1, color_index=0))
        return transition

    distance_sq = point_distance(start_point, end_point)
    distance_value = math.sqrt(distance_sq)

    if distance_value <= 0.75:
        transition.append(create_laser_point(end_point[0], end_point[1], blanking=1, color_index=0))
        return transition

    if distance_value <= short_threshold:
        if blank_begin > 0:
            transition.append(create_laser_point(start_point[0], start_point[1], blanking=1, color_index=0))
        if distance_value > short_threshold * 0.55:
            mid = ((start_point[0] + end_point[0]) / 2.0, (start_point[1] + end_point[1]) / 2.0)
            transition.append(create_laser_point(mid[0], mid[1], blanking=1, color_index=0))
        transition.append(create_laser_point(end_point[0], end_point[1], blanking=1, color_index=0))
        return transition

    for _ in range(blank_begin):
        transition.append(create_laser_point(start_point[0], start_point[1], blanking=1, color_index=0))

    internal_count = max(0, int(distance_value / scan_config['blank_spacing']) - 1)
    if internal_count > 0:
        params = nonlinear_spacing_parameters(internal_count + 2)[1:-1]
        for t in params:
            x = start_point[0] + (end_point[0] - start_point[0]) * t
            y = start_point[1] + (end_point[1] - start_point[1]) * t
            transition.append(create_laser_point(x, y, blanking=1, color_index=0))

    for _ in range(blank_end):
        transition.append(create_laser_point(end_point[0], end_point[1], blanking=1, color_index=0))
    return transition


def nonlinear_spacing_parameters(count):
    u = np.linspace(0.0, 1.0, count)
    return 0.5 - 0.5 * np.cos(np.pi * u)


def compute_corner_dwell(prev_point, point, next_point, corner_dwell_max):
    angle = corner_angle_degrees(prev_point, point, next_point)
    if angle >= 165:
        return 0
    sharpness_ratio = max(0.0, min(1.0, (165.0 - angle) / 120.0))
    extra = int(round(sharpness_ratio * corner_dwell_max))
    if angle < 95:
        extra = max(extra, max(1, corner_dwell_max // 2))
    return extra


def corner_angle_degrees(a, b, c):
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 < 1e-9 or n2 < 1e-9:
        return 180.0
    cos_value = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cos_value = max(-1.0, min(1.0, cos_value))
    return math.degrees(math.acos(cos_value))


def create_laser_point(x, y, blanking, color_index):
    return {
        'x': scale_coord(x),
        'y': scale_coord(y),
        'z': 0,
        'status': {'blanking': int(blanking), 'last_point': 0},
        'color_index': color_index
    }


def svg_color_to_index(color_value):
    if not color_value:
        return 63
    color_text = str(color_value).strip().lower()
    if color_text == 'none':
        return 64
    try:
        rgb = ImageColor.getrgb(color_text)
    except Exception:
        named_map = {
            'red': (255, 0, 0),
            'yellow': (255, 255, 0),
            'green': (0, 255, 0),
            'cyan': (0, 255, 255),
            'blue': (0, 0, 255),
            'magenta': (255, 0, 255),
            'white': (255, 255, 255),
            'black': (0, 0, 0)
        }
        rgb = named_map.get(color_text, (255, 255, 255))

    if len(rgb) == 4:
        rgb = rgb[:3]

    best_index = 63
    best_distance = float('inf')
    for palette_index, palette_rgb in PALETTE_RGB.items():
        dist = (
            (rgb[0] - palette_rgb[0]) ** 2 +
            (rgb[1] - palette_rgb[1]) ** 2 +
            (rgb[2] - palette_rgb[2]) ** 2
        )
        if dist < best_distance:
            best_distance = dist
            best_index = palette_index
    return best_index


def scale_coord(value):
    normalized = (value / CONFIG['canvas_size'] - 0.5) * 2.0
    clipped = max(-1.0, min(1.0, normalized))
    return int(clipped * CONFIG['ilda_range'][1])


def point_distance(p1, p2):
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def distance(p1, p2):
    return point_distance(p1, p2)


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
        header = data[ptr:ptr + 32]
        if len(header) < 32:
            break
        ilda_id = header[0:4].decode('ascii', errors='ignore')
        if ilda_id != 'ILDA':
            raise ValueError('Invalid ILDA file header')
        format_code = header[7]
        name = header[8:16].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
        company = header[16:24].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
        num_records = struct.unpack('>H', header[24:26])[0]
        section_number = struct.unpack('>H', header[26:28])[0]
        total_sections = struct.unpack('>H', header[28:30])[0]
        projector = header[30]
        section = OrderedDict([
            ('format_code', format_code),
            ('name', name),
            ('company', company),
            ('num_records', num_records),
            ('section_number', section_number),
            ('total_sections', total_sections),
            ('projector', projector),
            ('data', [])
        ])
        ptr += 32
        if num_records == 0 and format_code in [0, 1, 4, 5]:
            break
        if format_code == 0:
            record_size = 8
            for _ in range(num_records):
                record = data[ptr:ptr + record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                z = struct.unpack('>h', record[4:6])[0]
                status = record[6]
                color_index = record[7]
                section['data'].append(OrderedDict([
                    ('x', x), ('y', y), ('z', z),
                    ('status', {
                        'last_point': (status & 0x80) >> 7,
                        'blanking': (status & 0x40) >> 6
                    }),
                    ('color_index', color_index)
                ]))
                ptr += record_size
        elif format_code == 1:
            record_size = 6
            for _ in range(num_records):
                record = data[ptr:ptr + record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                status = record[4]
                color_index = record[5]
                section['data'].append(OrderedDict([
                    ('x', x), ('y', y), ('z', None),
                    ('status', {
                        'last_point': (status & 0x80) >> 7,
                        'blanking': (status & 0x40) >> 6
                    }),
                    ('color_index', color_index)
                ]))
                ptr += record_size
        elif format_code == 2:
            record_size = 3
            palette = []
            for _ in range(num_records):
                record = data[ptr:ptr + record_size]
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
                record = data[ptr:ptr + record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                z = struct.unpack('>h', record[4:6])[0]
                status = record[6]
                blue = record[7]
                green = record[8]
                red = record[9]
                section['data'].append(OrderedDict([
                    ('x', x), ('y', y), ('z', z),
                    ('status', {
                        'last_point': (status & 0x80) >> 7,
                        'blanking': (status & 0x40) >> 6
                    }),
                    ('color', [red, green, blue])
                ]))
                ptr += record_size
        elif format_code == 5:
            record_size = 8
            for _ in range(num_records):
                record = data[ptr:ptr + record_size]
                x = struct.unpack('>h', record[0:2])[0]
                y = struct.unpack('>h', record[2:4])[0]
                status = record[4]
                blue = record[5]
                green = record[6]
                red = record[7]
                section['data'].append(OrderedDict([
                    ('x', x), ('y', y), ('z', None),
                    ('status', {
                        'last_point': (status & 0x80) >> 7,
                        'blanking': (status & 0x40) >> 6
                    }),
                    ('color', [red, green, blue])
                ]))
                ptr += record_size
        result.append(section)
    return result, current_palettes


# --------------------------------------
# 转换为 GIF 函数
# --------------------------------------
def ilda_to_gif(ild_data, palettes, output_gif, canvas_size=800, fps=30):
    color_map = {
        9: (255, 0, 0),
        18: (255, 255, 0),
        27: (0, 255, 0),
        36: (0, 255, 255),
        45: (0, 0, 255),
        54: (255, 0, 255),
        63: (255, 255, 255),
        64: (0, 0, 0)
    }
    intervals = [
        (-float('inf'), 9, color_map[9]),
        (9, 18, color_map[18]),
        (18, 27, color_map[27]),
        (27, 36, color_map[36]),
        (36, 45, color_map[45]),
        (45, 54, color_map[54]),
        (54, 63, color_map[63]),
        (63, float('inf'), color_map[64])
    ]

    def find_closest_color(target_index):
        for low, high, color in intervals:
            if low < target_index <= high:
                return color
        return color_map[64]

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
        if section.get('format_code') not in [0, 1, 4, 5] or section.get('num_records', 0) == 0:
            continue
        img = Image.new('RGB', (canvas_size, canvas_size), 'black')
        draw = ImageDraw.Draw(img)
        current_path = []
        current_color = (255, 255, 255)
        projector = section['projector']
        for point in section['data']:
            x = scale_point(point['x'])
            y = scale_point(-point['y'])
            if point['status']['blanking']:
                if current_path:
                    draw.line(current_path, fill=current_color, width=1)
                    current_path = []
            else:
                if section['format_code'] in [0, 1]:
                    color_index = point['color_index']
                    current_color = get_color(projector, color_index)
                else:
                    current_color = tuple(point['color'][:3])
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
    return False


# --------------------------------------
# 主程序类
# --------------------------------------
class LaserShowConverter(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath('.')

        icon_path = os.path.join(base_path, 'icon.ico')
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.title('X-Laser PC 控制端')
        self.geometry('1420x860+20+20')
        self.resizable(False, False)
        self.serial_port = None
        self.available_ports = []
        self.stop_thread = False
        self.lock = threading.Lock()
        self.ui_queue = queue.Queue()
        self.output_ild = os.path.abspath('output.ild')
        self.output_gif = os.path.abspath('output.gif')
        self.after_id = None
        self.ui_poll_after_id = None
        self.port_poll_after_id = None
        self.frames = []
        self.current_frame = 0
        self.current_conversion_type = None
        self.canvas_size = 400, 400
        self.flip_h = tk.BooleanVar()
        self.flip_v = tk.BooleanVar()
        self.quality_level = tk.IntVar(value=10)
        self.preview_meta_var = tk.StringVar(
            value='等待生成预览，转换完成后会在这里循环播放 GIF 动画'
        )
        self.port_badge_var = tk.StringVar(value='正在扫描串口')
        self.conversion_ok = False
        self.conversion_error = None
        self.generated_file_path = None
        self.is_converting = False

        self.create_widgets()
        self.set_status('等待操作...', tone='idle')
        self.update_quality_labels()
        self.ui_poll_after_id = self.after(40, self.process_ui_queue)
        self.poll_ports()

        self.reader_thread = threading.Thread(target=self.read_serial_output, daemon=True)
        self.reader_thread.start()
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    def setup_theme(self):
        self.colors = {
            'bg': '#f4f7fb',
            'surface': '#ffffff',
            'surface_alt': '#f8fbff',
            'border': '#d7e0ec',
            'text': '#182235',
            'muted': '#66758f',
            'accent': '#2563eb',
            'accent_hover': '#1d4ed8',
            'accent_soft': '#eaf1ff',
            'success': '#0f9f6e',
            'success_soft': '#eafaf2',
            'warning': '#b7791f',
            'warning_soft': '#fff6e6',
            'danger': '#cf3f4f',
            'danger_soft': '#fff0f3',
            'dark_surface': '#0f172a',
            'dark_border': '#24324c',
            'dark_text': '#f8fbff',
            'dark_muted': '#9db0cb',
            'canvas_bg': '#050b16',
            'canvas_border': '#1e3354'
        }

        self.configure(bg=self.colors['bg'])
        self.option_add('*TCombobox*Listbox.font', ('Microsoft YaHei UI', 10))

        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')

        base_font = ('Microsoft YaHei UI', 10)
        strong_font = ('Microsoft YaHei UI', 10, 'bold')

        style.configure('.', background=self.colors['bg'], foreground=self.colors['text'], font=base_font)
        style.configure('App.TFrame', background=self.colors['bg'])
        style.configure('Surface.TFrame', background=self.colors['surface'])
        style.configure('Surface.TLabel', background=self.colors['surface'], foreground=self.colors['text'], font=base_font)
        style.configure('Field.TLabel', background=self.colors['surface'], foreground=self.colors['muted'], font=('Microsoft YaHei UI', 9))
        style.configure('Hint.TLabel', background=self.colors['surface'], foreground=self.colors['muted'], font=('Microsoft YaHei UI', 9))
        style.configure('Title.TLabel', background=self.colors['bg'], foreground=self.colors['text'], font=('Microsoft YaHei UI', 20, 'bold'))
        style.configure('Subtitle.TLabel', background=self.colors['bg'], foreground=self.colors['muted'], font=('Microsoft YaHei UI', 10))
        style.configure('CardTitle.TLabel', background=self.colors['surface'], foreground=self.colors['text'], font=('Microsoft YaHei UI', 12, 'bold'))
        style.configure('CardSubtitle.TLabel', background=self.colors['surface'], foreground=self.colors['muted'], font=('Microsoft YaHei UI', 9))

        style.configure(
            'App.TEntry',
            fieldbackground=self.colors['surface_alt'],
            background=self.colors['surface_alt'],
            foreground=self.colors['text'],
            bordercolor=self.colors['border'],
            lightcolor=self.colors['border'],
            darkcolor=self.colors['border'],
            insertcolor=self.colors['text'],
            relief='flat',
            padding=(10, 8)
        )
        style.map(
            'App.TEntry',
            fieldbackground=[('readonly', self.colors['surface_alt'])],
            foreground=[('readonly', self.colors['text'])]
        )

        style.configure(
            'App.TCombobox',
            fieldbackground=self.colors['surface_alt'],
            background=self.colors['surface_alt'],
            foreground=self.colors['text'],
            bordercolor=self.colors['border'],
            lightcolor=self.colors['border'],
            darkcolor=self.colors['border'],
            arrowsize=16,
            relief='flat',
            padding=(10, 8)
        )
        style.map(
            'App.TCombobox',
            fieldbackground=[('readonly', self.colors['surface_alt'])],
            selectbackground=[('readonly', self.colors['surface_alt'])],
            selectforeground=[('readonly', self.colors['text'])]
        )

        style.configure(
            'App.TSpinbox',
            fieldbackground=self.colors['surface_alt'],
            background=self.colors['surface_alt'],
            foreground=self.colors['text'],
            bordercolor=self.colors['border'],
            lightcolor=self.colors['border'],
            darkcolor=self.colors['border'],
            arrowsize=14,
            relief='flat',
            padding=(8, 6)
        )

        style.configure(
            'Primary.TButton',
            background=self.colors['accent'],
            foreground='#ffffff',
            borderwidth=0,
            focuscolor=self.colors['accent'],
            focusthickness=0,
            padding=(16, 10),
            font=strong_font
        )
        style.map(
            'Primary.TButton',
            background=[('active', self.colors['accent_hover']), ('disabled', '#9ab8f7')],
            foreground=[('disabled', '#eef4ff')]
        )

        style.configure(
            'Secondary.TButton',
            background=self.colors['accent_soft'],
            foreground=self.colors['accent'],
            borderwidth=0,
            focuscolor=self.colors['accent_soft'],
            focusthickness=0,
            padding=(14, 9),
            font=strong_font
        )
        style.map(
            'Secondary.TButton',
            background=[('active', '#dbe7ff'), ('disabled', '#eef2f7')],
            foreground=[('disabled', '#8a96aa')]
        )

        style.configure(
            'Neutral.TButton',
            background='#eef2f7',
            foreground=self.colors['text'],
            borderwidth=0,
            focuscolor='#eef2f7',
            focusthickness=0,
            padding=(14, 9),
            font=strong_font
        )
        style.map(
            'Neutral.TButton',
            background=[('active', '#e3e8f0'), ('disabled', '#f3f5f8')],
            foreground=[('disabled', '#9aa5b5')]
        )

        style.configure('App.TCheckbutton', background=self.colors['surface'], foreground=self.colors['text'], font=base_font)

    def create_card(self, parent, title, subtitle=None, dark=False):
        background = self.colors['dark_surface'] if dark else self.colors['surface']
        border = self.colors['dark_border'] if dark else self.colors['border']
        title_fg = self.colors['dark_text'] if dark else self.colors['text']
        subtitle_fg = self.colors['dark_muted'] if dark else self.colors['muted']

        card = tk.Frame(
            parent,
            bg=background,
            bd=0,
            highlightthickness=1,
            highlightbackground=border
        )

        header = tk.Frame(card, bg=background)
        header.pack(fill=tk.X, padx=18, pady=(16, 4))

        tk.Label(
            header,
            text=title,
            bg=background,
            fg=title_fg,
            font=('Microsoft YaHei UI', 12, 'bold')
        ).pack(anchor='w')

        if subtitle:
            tk.Label(
                header,
                text=subtitle,
                bg=background,
                fg=subtitle_fg,
                font=('Microsoft YaHei UI', 9),
                justify='left',
                wraplength=360
            ).pack(anchor='w', pady=(4, 0))

        if dark:
            body = tk.Frame(card, bg=background)
        else:
            body = ttk.Frame(card, style='Surface.TFrame')
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=(8, 18))
        return card, body

    def set_status(self, message, tone='idle'):
        palette = {
            'idle': ('#eef3fb', self.colors['text']),
            'working': (self.colors['warning_soft'], self.colors['warning']),
            'success': (self.colors['success_soft'], self.colors['success']),
            'error': (self.colors['danger_soft'], self.colors['danger']),
            'connected': (self.colors['accent_soft'], self.colors['accent'])
        }
        bg, fg = palette.get(tone, palette['idle'])
        self.status_lbl.config(text=message, bg=bg, fg=fg)

    def set_port_badge(self, message, tone='idle'):
        palette = {
            'idle': ('#edf2fb', self.colors['muted']),
            'success': (self.colors['success_soft'], self.colors['success']),
            'warning': (self.colors['warning_soft'], self.colors['warning']),
            'connected': (self.colors['accent_soft'], self.colors['accent'])
        }
        bg, fg = palette.get(tone, palette['idle'])
        self.port_badge_var.set(message)
        self.port_badge.config(bg=bg, fg=fg)

    def set_preview_badge(self, message, tone='idle'):
        palette = {
            'idle': ('#172033', '#b4c3d9'),
            'working': ('#3f2a12', '#ffd08a'),
            'success': ('#173524', '#8be3b6'),
            'error': ('#40202a', '#ffb0bb')
        }
        bg, fg = palette.get(tone, palette['idle'])
        self.preview_badge.config(text=message, bg=bg, fg=fg)

    def enqueue_ui(self, callback, *args, **kwargs):
        self.ui_queue.put((callback, args, kwargs))

    def process_ui_queue(self):
        while True:
            try:
                callback, args, kwargs = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args, **kwargs)
            except tk.TclError:
                return

        if not self.stop_thread:
            self.ui_poll_after_id = self.after(40, self.process_ui_queue)

    def poll_ports(self):
        if self.stop_thread:
            return

        ports = serial.tools.list_ports.comports()
        port_list = [f"{p.device} ({p.description.split(' ')[0]})" for p in ports]
        if port_list != self.available_ports:
            self.available_ports = port_list
            self.refresh_port_combobox(port_list)

        self.port_poll_after_id = self.after(1000, self.poll_ports)

    def set_conversion_busy(self, busy):
        self.is_converting = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.svg_convert_btn.config(state=state)
        self.ild_preview_btn.config(state=state)

    def create_widgets(self):
        self.setup_theme()

        shell = ttk.Frame(self, style='App.TFrame')
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        hero = ttk.Frame(shell, style='App.TFrame')
        hero.pack(fill=tk.X, pady=(0, 16))

        hero_left = ttk.Frame(hero, style='App.TFrame')
        hero_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(hero_left, text='X-Laser PC 控制端', style='Title.TLabel').pack(anchor='w')
        ttk.Label(
            hero_left,
            text='SVG 转换、ILD 预览与串口传输集中在一个更清晰的工作台中。',
            style='Subtitle.TLabel',
            wraplength=760,
            justify='left'
        ).pack(anchor='w', pady=(4, 0))

        self.port_badge = tk.Label(
            hero,
            textvariable=self.port_badge_var,
            bg='#edf2fb',
            fg=self.colors['muted'],
            font=('Microsoft YaHei UI', 9, 'bold'),
            padx=14,
            pady=8
        )
        self.port_badge.pack(side=tk.RIGHT, pady=4)

        content = tk.Frame(shell, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True)

        left_column = tk.Frame(content, bg=self.colors['bg'], width=470)
        left_column.pack(side=tk.LEFT, fill=tk.Y)
        left_column.pack_propagate(False)

        center_column = tk.Frame(content, bg=self.colors['bg'], width=500)
        center_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 18))

        right_column = tk.Frame(content, bg=self.colors['bg'], width=378)
        right_column.pack(side=tk.RIGHT, fill=tk.Y)
        right_column.pack_propagate(False)

        svg_card, svg_group = self.create_card(
            left_column,
            'SVG 转 ILD',
            '导入 SVG 后设置翻转、质量和缩放参数，直接生成输出文件。'
        )
        svg_card.pack(fill=tk.X, pady=(0, 14))
        svg_group.columnconfigure(0, weight=1)

        self.svg_path = tk.StringVar()
        ttk.Label(svg_group, text='SVG 文件路径', style='Field.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Entry(svg_group, textvariable=self.svg_path, width=35, style='App.TEntry').grid(
            row=1, column=0, padx=(0, 10), pady=(6, 14), sticky='ew'
        )
        ttk.Button(svg_group, text='浏览...', command=self.select_svg, style='Secondary.TButton').grid(
            row=1, column=1, pady=(6, 14), sticky='ew'
        )

        flip_frame = ttk.Frame(svg_group, style='Surface.TFrame')
        flip_frame.grid(row=2, column=0, columnspan=2, pady=(0, 14), sticky='w')
        ttk.Checkbutton(flip_frame, text='水平翻转', variable=self.flip_h, style='App.TCheckbutton').pack(side=tk.LEFT, padx=(0, 18))
        ttk.Checkbutton(flip_frame, text='垂直翻转', variable=self.flip_v, style='App.TCheckbutton').pack(side=tk.LEFT)

        param_frame = ttk.Frame(svg_group, style='Surface.TFrame')
        param_frame.grid(row=3, column=0, columnspan=2, pady=(0, 14), sticky='ew')
        param_frame.columnconfigure(2, weight=1)

        ttk.Label(param_frame, text='输出质量', style='Field.TLabel').grid(row=0, column=0, sticky='w')
        self.quality_spin = ttk.Spinbox(
            param_frame,
            from_=1,
            to=20,
            width=5,
            textvariable=self.quality_level,
            command=self.update_quality_labels,
            style='App.TSpinbox'
        )
        self.quality_spin.grid(row=0, column=1, padx=(10, 10), sticky='w')
        self.quality_spin.bind('<KeyRelease>', lambda e: self.update_quality_labels())
        self.quality_spin.bind('<<Increment>>', lambda e: self.update_quality_labels())
        self.quality_spin.bind('<<Decrement>>', lambda e: self.update_quality_labels())

        self.quality_desc_var = tk.StringVar(value='标准')
        self.quality_chip = tk.Label(
            param_frame,
            textvariable=self.quality_desc_var,
            bg=self.colors['accent_soft'],
            fg=self.colors['accent'],
            font=('Microsoft YaHei UI', 9, 'bold'),
            padx=12,
            pady=6
        )
        self.quality_chip.grid(row=0, column=2, sticky='w')

        transform_frame = ttk.Frame(svg_group, style='Surface.TFrame')
        transform_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(0, 16))
        for idx in range(3):
            transform_frame.columnconfigure(idx, weight=1)

        ttk.Label(transform_frame, text='X 平移', style='Field.TLabel').grid(row=0, column=0, sticky='w')
        self.tx_var = tk.IntVar(value=0)
        ttk.Entry(transform_frame, textvariable=self.tx_var, width=10, style='App.TEntry').grid(
            row=1, column=0, sticky='ew', padx=(0, 10), pady=(6, 0)
        )

        ttk.Label(transform_frame, text='Y 平移', style='Field.TLabel').grid(row=0, column=1, sticky='w')
        self.ty_var = tk.IntVar(value=0)
        ttk.Entry(transform_frame, textvariable=self.ty_var, width=10, style='App.TEntry').grid(
            row=1, column=1, sticky='ew', padx=(0, 10), pady=(6, 0)
        )

        ttk.Label(transform_frame, text='缩放倍数', style='Field.TLabel').grid(row=0, column=2, sticky='w')
        self.scale_var = tk.DoubleVar(value=1.0)
        ttk.Entry(transform_frame, textvariable=self.scale_var, width=10, style='App.TEntry').grid(
            row=1, column=2, sticky='ew', pady=(6, 0)
        )

        self.svg_convert_btn = ttk.Button(
            svg_group,
            text='转换为 ILD',
            command=self.convert_svg_to_ild,
            style='Primary.TButton'
        )
        self.svg_convert_btn.grid(
            row=5, column=0, columnspan=2, sticky='ew'
        )

        ild_card, ild_group = self.create_card(
            left_column,
            'ILD 预览',
            '选择已有 ILD 文件，快速生成 GIF 动画并同步到发送文件列表。'
        )
        ild_card.pack(fill=tk.X)
        ild_group.columnconfigure(0, weight=1)

        self.ild_path = tk.StringVar()
        ttk.Label(ild_group, text='ILD 文件路径', style='Field.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Entry(ild_group, textvariable=self.ild_path, width=35, style='App.TEntry').grid(
            row=1, column=0, padx=(0, 10), pady=(6, 14), sticky='ew'
        )
        ttk.Button(ild_group, text='浏览...', command=self.select_ild, style='Secondary.TButton').grid(
            row=1, column=1, pady=(6, 14), sticky='ew'
        )
        self.ild_preview_btn = ttk.Button(
            ild_group,
            text='开始预览',
            command=self.convert_ild_to_gif,
            style='Primary.TButton'
        )
        self.ild_preview_btn.grid(
            row=2, column=0, columnspan=2, sticky='ew'
        )

        preview_card, preview_group = self.create_card(
            center_column,
            '实时预览',
            'GIF 会在这里按原始帧率循环播放，方便在发送前确认效果。',
            dark=True
        )
        preview_card.pack(fill=tk.BOTH, expand=True)

        preview_header = tk.Frame(preview_group, bg=self.colors['dark_surface'])
        preview_header.pack(fill=tk.X, pady=(0, 14))

        self.preview_badge = tk.Label(
            preview_header,
            text='等待预览',
            bg='#172033',
            fg='#b4c3d9',
            font=('Microsoft YaHei UI', 9, 'bold'),
            padx=12,
            pady=6
        )
        self.preview_badge.pack(anchor='w')

        self.preview_meta_label = tk.Label(
            preview_header,
            textvariable=self.preview_meta_var,
            bg=self.colors['dark_surface'],
            fg=self.colors['dark_muted'],
            font=('Microsoft YaHei UI', 9),
            anchor='w',
            justify='left',
            wraplength=460
        )
        self.preview_meta_label.pack(fill=tk.X, pady=(8, 0))

        preview_frame = tk.Frame(
            preview_group,
            bg=self.colors['dark_surface'],
            bd=0
        )
        preview_frame.pack(fill=tk.BOTH, expand=True)
        preview_frame.pack_propagate(False)

        self.preview_viewport = tk.Frame(
            preview_frame,
            width=self.canvas_size[0] + 32,
            height=self.canvas_size[1] + 32,
            bg=self.colors['canvas_border'],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors['canvas_border']
        )
        self.preview_viewport.pack(expand=True)
        self.preview_viewport.pack_propagate(False)

        self.canvas = tk.Label(
            self.preview_viewport,
            bg=self.colors['canvas_bg'],
            fg=self.colors['dark_muted'],
            text='等待 GIF 预览',
            font=('Microsoft YaHei UI', 15, 'bold')
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        serial_card, serial_container = self.create_card(
            right_column,
            '串口传输',
            '选择串口与待发送文件，查看传输日志并完成下位机同步。'
        )
        serial_card.pack(fill=tk.BOTH, expand=True)
        serial_container.columnconfigure(0, weight=1)
        serial_container.rowconfigure(3, weight=1)

        ttk.Label(serial_container, text='选择串口', style='Field.TLabel').grid(row=0, column=0, sticky='w')
        self.port_var = tk.StringVar()
        self.port_combobox = ttk.Combobox(
            serial_container,
            textvariable=self.port_var,
            width=30,
            style='App.TCombobox',
            state='readonly'
        )
        self.port_combobox.grid(row=1, column=0, sticky='ew', pady=(6, 14))

        ttk.Label(serial_container, text='待发送文件', style='Field.TLabel').grid(row=2, column=0, sticky='w')
        file_frame = ttk.Frame(serial_container, style='Surface.TFrame')
        file_frame.grid(row=3, column=0, sticky='ew', pady=(6, 14))
        file_frame.columnconfigure(0, weight=1)
        self.file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_var, width=50, state='readonly', style='App.TEntry').grid(row=0, column=0, sticky='ew')
        ttk.Button(file_frame, text='选择文件', command=self.select_file, style='Secondary.TButton').grid(row=0, column=1, padx=(10, 0))

        btn_frame = ttk.Frame(serial_container, style='Surface.TFrame')
        btn_frame.grid(row=4, column=0, sticky='w', pady=(0, 14))
        self.send_btn = ttk.Button(btn_frame, text='发送文件', command=self.start_send, style='Primary.TButton')
        self.send_btn.pack(side=tk.LEFT, padx=5)
        self.clear_btn = ttk.Button(btn_frame, text='清空日志', command=self.clear_log, style='Neutral.TButton')
        self.clear_btn.pack(side=tk.LEFT)

        log_frame = ttk.Frame(serial_container, style='Surface.TFrame')
        log_frame.grid(row=5, column=0, sticky='nsew')
        ttk.Label(log_frame, text='传输日志', style='Field.TLabel').pack(fill=tk.X, anchor='w')
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=20,
            state='disabled',
            bg=self.colors['surface_alt'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            relief='flat',
            borderwidth=0,
            font=('Consolas', 10),
            padx=10,
            pady=10
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        status_container = tk.Frame(
            shell,
            bg='#eef3fb',
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors['border']
        )
        status_container.pack(fill=tk.X, pady=(16, 0))

        self.status_lbl = tk.Label(
            status_container,
            text='等待操作...',
            bg='#eef3fb',
            fg=self.colors['text'],
            font=('Microsoft YaHei UI', 10),
            anchor='w',
            justify='left',
            padx=14,
            pady=10,
            wraplength=1110
        )
        self.status_lbl.pack(fill=tk.X)

    def clamp_quality_level(self):
        try:
            quality = int(self.quality_level.get())
        except tk.TclError:
            quality = 10
        quality = max(1, min(20, quality))
        self.quality_level.set(quality)
        return quality

    def update_quality_labels(self):
        quality = self.clamp_quality_level()
        self.quality_desc_var.set(f"{QUALITY_LEVELS[quality]}")

    def select_svg(self):
        path = filedialog.askopenfilename(filetypes=[('SVG Files', '*.svg')])
        if path:
            self.svg_path.set(path)
            self.set_status(f'已选择 SVG 文件：{os.path.basename(path)}', tone='idle')

    def select_ild(self):
        path = filedialog.askopenfilename(filetypes=[('ILDA Files', '*.ild')])
        if path:
            self.ild_path.set(path)
            self.file_var.set(path)
            self.set_status(f'已选择 ILD 文件：{os.path.basename(path)}', tone='idle')
            self.preview_meta_var.set(f'当前预览源文件：{os.path.basename(path)}')
            self.set_preview_badge('等待预览', tone='idle')

    def convert_svg_to_ild(self):
        if self.is_converting:
            self.set_status('当前已有渲染任务进行中，请稍候。', tone='working')
            return

        svg_path = self.svg_path.get()
        if not os.path.exists(svg_path):
            messagebox.showerror('错误', '无效的 SVG 文件路径')
            return

        try:
            scale = self.scale_var.get()
            tx = self.tx_var.get()
            ty = self.ty_var.get()
            quality = self.clamp_quality_level()
            mapped = map_quality_to_internal_params(quality)
        except tk.TclError:
            messagebox.showerror('错误', '请输入有效的数值参数')
            return

        self.conversion_ok = False
        self.conversion_error = None
        self.generated_file_path = None
        self.set_conversion_busy(True)
        self.set_status(f'正在转换 SVG 到 ILD... 输出：{self.output_ild}', tone='working')
        self.set_preview_badge('正在渲染', tone='working')
        self.preview_meta_var.set('SVG 已提交转换，正在生成 ILD 与 GIF 输出')
        self.current_conversion_type = 'svg'
        thread = threading.Thread(
            target=self._convert_svg,
            args=(
                svg_path,
                scale,
                tx,
                ty,
                self.flip_h.get(),
                self.flip_v.get(),
                mapped
            ),
            daemon=True
        )
        thread.start()
        self.after(100, self.check_conversion_thread, thread)

    def _convert_svg(self, svg_path, scale, tx, ty, flip_h, flip_v, scan_config):
        try:
            ilda_data = svg_to_laser_json(svg_path, scale, tx, ty, flip_h, flip_v, scan_config)
            if not ilda_data:
                raise ValueError('未生成有效数据')
            write_ilda_file(ilda_data, self.output_ild)
            success = ilda_to_gif(ilda_data, {}, self.output_gif, 200, 30)
            self.conversion_ok = success
            self.generated_file_path = self.output_ild
        except Exception as e:
            self.conversion_ok = False
            self.conversion_error = str(e)
            print(f'转换失败：{e}')

    def convert_ild_to_gif(self):
        if self.is_converting:
            self.set_status('当前已有渲染任务进行中，请稍候。', tone='working')
            return

        input_path = self.ild_path.get()
        if not os.path.exists(input_path):
            messagebox.showerror('错误', '请先选择一个有效的 ILD 文件')
            return
        self.conversion_ok = False
        self.conversion_error = None
        self.generated_file_path = None
        self.set_conversion_busy(True)
        self.set_status('转换中，请稍候...', tone='working')
        self.set_preview_badge('正在渲染', tone='working')
        self.preview_meta_var.set(f'当前预览源文件：{os.path.basename(input_path)}')
        self.file_var.set(input_path)
        self.current_conversion_type = 'ild'
        thread = threading.Thread(target=self._convert_ild, args=(input_path,), daemon=True)
        thread.start()
        self.after(100, self.check_conversion_thread, thread)

    def _convert_ild(self, input_path):
        try:
            ild_data, palettes = parse_ilda_file(input_path)
            success = ilda_to_gif(
                ild_data,
                palettes,
                self.output_gif,
                canvas_size=640,
                fps=30
            )
            self.conversion_ok = success
        except Exception as e:
            self.conversion_ok = False
            self.conversion_error = str(e)
            print(f'转换失败：{e}')

    def check_conversion_thread(self, thread):
        if thread.is_alive():
            self.after(100, self.check_conversion_thread, thread)
            return

        self.set_conversion_busy(False)

        if hasattr(self, 'conversion_ok') and self.conversion_ok:
            if self.current_conversion_type == 'svg':
                status_text = (
                    f'转换完成，文件已生成：\n'
                    f'ILDA: {self.output_ild}\n'
                    f'GIF: {self.output_gif}'
                )
            elif self.current_conversion_type == 'ild':
                status_text = f'转换完成，GIF文件已生成：\n{self.output_gif}'
            else:
                status_text = '转换完成'
            if self.generated_file_path:
                self.file_var.set(self.generated_file_path)
            self.set_status(status_text, tone='success')
            self.set_preview_badge('预览已更新', tone='success')
            self.load_and_play_gif(self.output_gif)
        else:
            error_text = '转换失败，请检查输入文件和参数'
            if self.conversion_error:
                error_text = f'转换失败：{self.conversion_error}'
            self.set_status(error_text, tone='error')
            self.set_preview_badge('预览失败', tone='error')
            self.preview_meta_var.set('没有可显示的 GIF 结果，请检查输入文件与参数')
            self.canvas.configure(image=None, text='预览生成失败')

    def fit_preview_frame(self, frame, target_size):
        target_w, target_h = target_size
        preview = Image.new('RGB', (target_w, target_h), 'black')

        src_w, src_h = frame.size
        if src_w <= 0 or src_h <= 0:
            return preview

        scale = min(target_w / src_w, target_h / src_h)
        render_w = max(1, int(round(src_w * scale)))
        render_h = max(1, int(round(src_h * scale)))
        resized = frame.resize((render_w, render_h), Image.LANCZOS)
        offset_x = (target_w - render_w) // 2
        offset_y = (target_h - render_h) // 2
        preview.paste(resized, (offset_x, offset_y))
        return preview

    def load_and_play_gif(self, gif_path):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.canvas.configure(image='', text='正在载入 GIF 预览')
        self.canvas.image = None
        self.frames.clear()
        self.update_idletasks()
        target_w = max(280, self.canvas.winfo_width() - 24)
        target_h = max(280, self.canvas.winfo_height() - 24)
        try:
            self.gif = Image.open(gif_path)
        except Exception as e:
            self.set_preview_badge('预览失败', tone='error')
            self.preview_meta_var.set('无法加载 GIF 文件，请检查输出结果')
            messagebox.showerror('错误', f'无法加载 GIF 文件: {e}')
            return

        source_frames = []
        try:
            while True:
                frame = self.gif.copy().convert('RGB')
                source_frames.append(frame)
                self.gif.seek(len(source_frames))
        except EOFError:
            pass

        if not source_frames:
            self.set_preview_badge('预览失败', tone='error')
            self.preview_meta_var.set('GIF 中没有有效帧可用于预览')
            messagebox.showerror('错误', 'GIF 文件中没有有效帧')
            return

        self.frames = [
            ImageTk.PhotoImage(self.fit_preview_frame(frame, (target_w, target_h)))
            for frame in source_frames
        ]

        self.current_frame = 0
        self.preview_meta_var.set(
            f'共 {len(self.frames)} 帧，预览区域 {target_w} x {target_h}，整张 GIF 已缩放显示'
        )
        self.canvas.configure(text='')
        self.update_frame()

    def update_frame(self):
        frame = self.frames[self.current_frame]
        self.canvas.configure(image=frame)
        self.canvas.image = frame
        self.current_frame = (self.current_frame + 1) % len(self.frames)
        delay = self.gif.info.get('duration', 100)
        self.after_id = self.after(delay, self.update_frame)

    def refresh_port_combobox(self, port_list):
        self.port_combobox['values'] = port_list
        if port_list:
            current_value = self.port_var.get()
            if current_value not in port_list:
                preferred_index = 0
                for idx, value in enumerate(port_list):
                    if value.startswith('COM5'):
                        preferred_index = idx
                        break
                self.port_combobox.current(preferred_index)
            self.set_port_badge(f'检测到 {len(port_list)} 个串口', tone='success')
        else:
            self.port_var.set('')
            self.set_port_badge('未检测到串口', tone='warning')

    def read_serial_output(self):
        while not self.stop_thread:
            with self.lock:
                if self.serial_port and self.serial_port.is_open:
                    try:
                        if self.serial_port.in_waiting > 0:
                            output = self.serial_port.readline().decode(errors='ignore').strip()
                            if output:
                                self.enqueue_ui(self.log_message, f'ESP32 >> {output}')
                    except serial.SerialException as e:
                        self.enqueue_ui(self.log_message, f'串口异常: {str(e)}')
                        self.enqueue_ui(self.set_port_badge, '串口连接中断', 'warning')
                        if self.serial_port:
                            self.serial_port.close()
                            self.serial_port = None
            time.sleep(0.01)

    def select_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.file_var.set(file_path)
            self.set_status(f'已选择发送文件：{os.path.basename(file_path)}', tone='idle')

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)

    def start_send(self):
        if not self.file_var.get():
            messagebox.showwarning('错误', '请选择要发送的文件')
            return

        selected_port = self.port_var.get().split(' ')[0]
        if not selected_port:
            messagebox.showwarning('错误', '请选择有效的串口')
            return

        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

            self.serial_port = serial.Serial(selected_port, 921600, timeout=1)
            time.sleep(0.5)
            self.set_status(f'已连接到 {selected_port}', tone='connected')
            self.set_port_badge(f'已连接 {selected_port}', tone='connected')
        except Exception as e:
            messagebox.showerror('错误', f'无法打开串口: {str(e)}')
            return

        self.send_btn.config(state=tk.DISABLED)
        self.log_message(f'开始传输文件: {self.file_var.get()}')

        send_thread = threading.Thread(target=self.send_file, args=(self.file_var.get(),), daemon=True)
        send_thread.start()

    def send_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)

                header = f'FILENAME:{file_name}:{file_size}:'
                self.enqueue_ui(self.log_message, f'发送文件头: {header.strip()}')

                with self.lock:
                    self.serial_port.write(header.encode())

                time.sleep(0.5)
                if self.serial_port.in_waiting > 0:
                    with self.lock:
                        response = self.serial_port.readline().decode().strip()
                    if 'READY' not in response:
                        self.enqueue_ui(self.log_message, f'设备未就绪: {response}')
                        self.serial_port.close()
                        self.enqueue_ui(self.send_btn.config, state=tk.NORMAL)
                        return

                self.enqueue_ui(self.set_status, '发送中，请稍等……', 'working')

                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    with self.lock:
                        self.serial_port.write(chunk)
                    time.sleep(0.01)

                self.enqueue_ui(self.log_message, '文件传输完成')
                self.enqueue_ui(self.set_port_badge, '发送完成', 'success')

        except Exception as e:
            self.enqueue_ui(self.log_message, f'传输失败: {str(e)}')
            self.enqueue_ui(self.set_status, f'传输失败：{str(e)}', 'error')
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.enqueue_ui(self.send_btn.config, state=tk.NORMAL)
            self.enqueue_ui(self.set_status, '就绪', 'idle')
            self.enqueue_ui(self.set_port_badge, '等待发送', 'idle')

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

    def on_close(self):
        self.stop_thread = True
        if self.after_id:
            self.after_cancel(self.after_id)
        if self.ui_poll_after_id:
            self.after_cancel(self.ui_poll_after_id)
        if self.port_poll_after_id:
            self.after_cancel(self.port_poll_after_id)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.destroy()


# --------------------------------------
# 启动主循环
# --------------------------------------
if __name__ == '__main__':
    app = LaserShowConverter()
    app.mainloop()
