"""015 연구 대상지 지도. 입력은 읽기만 하며 지도·타일 파일을 저장하지 않는다.

Matplotlib의 실제 공간자료 SVG 위에 브라우저가 CARTO/OSM 타일을 채운다.
PNG/SVG는 메모리에만 생성한다. GTX 선형은 사용하지 않고 역사만 표시한다.
"""
from pathlib import Path
import base64
import html
import importlib.util
import io
import json
import math
import threading
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle, ConnectionPatch, PathPatch
from matplotlib.path import Path as MplPath
from shapely.geometry import box

ORDER = ['운정중앙', '킨텍스', '대곡']
COLORS = {-1: '#D73027', 0: '#EEEEEE', 1: '#2166AC'}
_SERVERS = []
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


def find_root():
    return next(p for p in [Path.cwd(), *Path.cwd().parents]
                if (p / 'config.py').is_file() and (p / 'code').is_dir())


def setup_font():
    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc'),
                 Path('C:/Windows/Fonts/malgunbd.ttf')]:
        if path.is_file():
            fm.fontManager.addfont(str(path))
            plt.rcParams['font.family'] = fm.FontProperties(fname=str(path)).get_name()
            break
    plt.rcParams.update({'axes.unicode_minus': False, 'font.weight': 'bold',
                         'axes.titleweight': 'bold', 'font.size': 16,
                         'figure.facecolor': 'white', 'svg.fonttype': 'path'})


def load_data(root):
    """011과 동일한 격자 ID 생성 순서를 사용하고 실제 중심점까지 대조한다."""
    base = pd.read_csv(root / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv',
                       encoding='utf-8-sig')
    stops = pd.read_csv(root / 'data/processed/gtx_a/16_새데이터_공급구조유지_250m격자.csv',
                        encoding='utf-8-sig')
    assert len(base) == 126 and base['셀 ID'].is_unique
    assert set(base['셀 ID']) == set(stops['셀 ID'].astype(int))
    np.testing.assert_array_equal(base['change'], base.board_2025 - base.board_2024)
    assert base.groupby('nearest_station').size().to_dict() == {'운정중앙': 63, '킨텍스': 26, '대곡': 37}
    grid_path = next((root / 'data/raw/common/grid/빈격자(250m)').glob('*.shp'))
    grid_crs = gpd.read_file(grid_path, rows=1).crs
    admin = gpd.read_file(root / 'data/raw/common/api_cache_gtx_a_routes/HangJeongDong_ver20260701.geojson').to_crs(grid_crs)
    admin['sgg_code'] = admin.sgg.astype(str).str.extract(r'([0-9]+)')[0].str.zfill(5)
    selected_admin = admin[admin.sgg_code.str.startswith(('4128', '4148'))]
    union = selected_admin.geometry.union_all()
    geometry = gpd.read_file(grid_path, bbox=union.bounds)
    geometry = geometry[geometry.geometry.intersects(union)].copy()
    geometry['_key'] = geometry.geometry.apply(lambda g: g.wkb if g is not None else None)
    geometry = geometry.drop_duplicates('_key').drop(columns='_key').reset_index(drop=True)
    geometry['셀 ID'] = np.arange(1, len(geometry) + 1)
    grid = geometry[['셀 ID', 'geometry']].merge(base, on='셀 ID', validate='one_to_one')
    assert len(grid) == 126 and grid.geometry.is_valid.all()
    centers = grid.geometry.centroid.to_crs(4326)
    np.testing.assert_allclose(centers.x, grid['중심점 경도'], atol=1e-6, rtol=0)
    np.testing.assert_allclose(centers.y, grid['중심점 위도'], atol=1e-6, rtol=0)
    np.testing.assert_allclose(grid.geometry.area, 62500, atol=.1, rtol=0)
    # 기존 지도 코드의 역사 좌표를 읽는다. 노선 선형은 생성하지 않는다.
    spec = importlib.util.spec_from_file_location('station_source_015', root / 'code/03_eda/kakao_period_compare.py')
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    stations = gpd.GeoDataFrame({'역명': ORDER}, geometry=gpd.points_from_xy(
        [source.STATIONS[s][1] for s in ORDER], [source.STATIONS[s][0] for s in ORDER]), crs=4326)
    # 고양의 3개 구를 고양시 하나로 합치며, 주변 시군 경계는 보조 배경이다.
    admin['city_key'] = np.where(admin.sgg_code.str.startswith('4128'), '고양시',
                                  np.where(admin.sgg_code.str.startswith('4148'), '파주시', admin.sgg_code))
    local = admin[admin.geometry.intersects(union.buffer(12000))]
    cities = local[['city_key', 'geometry']].dissolve(by='city_key').to_crs(3857)
    summary = base.groupby('nearest_station').agg(
        격자수=('셀 ID', 'size'), 개통전=('board_2024', 'sum'),
        개통후=('board_2025', 'sum'), 변화량=('change', 'sum')).reindex(ORDER)
    summary['감소'] = base[base.change.lt(0)].groupby('nearest_station').size().reindex(ORDER, fill_value=0)
    summary['유지'] = base[base.change.eq(0)].groupby('nearest_station').size().reindex(ORDER, fill_value=0)
    summary['증가'] = base[base.change.gt(0)].groupby('nearest_station').size().reindex(ORDER, fill_value=0)
    summary.loc['전체'] = summary.sum()
    assert tuple(summary.loc['전체', ['격자수', '개통전', '개통후', '변화량']]) == (126, 7110, 5517, -1593)
    return grid.to_crs(3857), stations.to_crs(3857), cities, summary


def _fit_bounds(bounds, aspect, padding=.07):
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0) * (1 + padding * 2), (y1 - y0) * (1 + padding * 2)
    w = max(w, h * aspect)
    h = max(h, w / aspect)
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _frame(ax, bounds):
    ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor('#FAFAFA')
    for spine in ax.spines.values():
        spine.set_linewidth(.9); spine.set_edgecolor('#252525')


def _scale(ax, bounds, metres):
    # EPSG:3857 거리의 위도 왜곡을 보정하여 실제 지상거리로 표시한다.
    cy = (bounds[1] + bounds[3]) / 2
    lat = math.atan(math.sinh(cy / 6378137))
    length = metres / math.cos(lat)
    x = bounds[0] + (bounds[2] - bounds[0]) * .065
    y = bounds[1] + (bounds[3] - bounds[1]) * .055
    ax.plot([x, x + length], [y, y], color='#222', lw=2.4, zorder=12)
    ax.text(x + length / 2, y + (bounds[3] - bounds[1]) * .015, f'{metres / 1000:g} km',
            fontsize=13, ha='center', va='bottom', zorder=13,
            path_effects=[pe.withStroke(linewidth=3, foreground='white')])


def make_figure(grid, stations, cities):
    setup_font()
    fig = plt.figure(figsize=(21, 12), dpi=150)
    # 넓은 운정·대곡은 좌우에 크게, 가운데는 위치도와 킨텍스 확대도를 둔다.
    positions = {'운정중앙': [.025, .13, .30, .76],
                 'overview': [.37, .51, .26, .38],
                 '킨텍스': [.37, .13, .26, .28],
                 '대곡': [.675, .13, .30, .76]}
    axes = {key: fig.add_axes(pos) for key, pos in positions.items()}
    bounds = {}
    for name in ORDER:
        part = grid[grid.nearest_station.eq(name)]
        st = stations[stations['역명'].eq(name)]
        geom = gpd.GeoSeries([*part.geometry, *st.geometry], crs=3857)
        pos = positions[name]
        bounds[name] = _fit_bounds(geom.total_bounds, pos[2] * 21 / (pos[3] * 12))
        ax = axes[name]
        _frame(ax, bounds[name])
        # SVG의 이 사각형 그룹에만 실제 타일 이미지를 삽입한다.
        ax.add_patch(Rectangle((bounds[name][0], bounds[name][1]),
                              bounds[name][2] - bounds[name][0], bounds[name][3] - bounds[name][1],
                              facecolor='#FAFAFA', edgecolor='none', zorder=.1, gid=f'basemap_{ORDER.index(name)}'))
        part.plot(ax=ax, color=np.sign(part.change).map(COLORS),
                  edgecolor='#383838', linewidth=.65, zorder=4)
        st.plot(ax=ax, marker='*', color='#138A55', markersize=260,
                edgecolor='white', linewidth=1.3, zorder=8)
        ax.set_title(f'{name}역 권역 · {len(part)}개 격자', fontsize=21, pad=15)
        _scale(ax, bounds[name], 2000 if name != '킨텍스' else 1000)
        # 모든 격자와 역이 패널 안에 포함되는지 검사한다.
        assert geom.geometry.covered_by(box(*bounds[name])).all()
    overview = axes['overview']
    target = cities.loc[['파주시', '고양시']]
    bounds['overview'] = _fit_bounds(target.total_bounds,
        positions['overview'][2] * 21 / (positions['overview'][3] * 12), padding=.04)
    _frame(overview, bounds['overview'])
    cities.plot(ax=overview, facecolor='#F1F1F1', edgecolor='#D5D5D5', linewidth=.6, zorder=1)
    target.plot(ax=overview, facecolor='#FFFFFF', edgecolor='#5A5A5A', linewidth=1.0, zorder=2)
    # 작은 위치도에서 분석 격자는 개별 변화색 대신 위치만 얇게 표시한다.
    grid.plot(ax=overview, facecolor='#949494', edgecolor='none', zorder=3)
    stations.plot(ax=overview, marker='*', color='#138A55', markersize=120,
                  edgecolor='white', linewidth=.8, zorder=6)
    overview.set_title('연구 대상지 위치', fontsize=21, pad=15)
    for city in ['파주시', '고양시']:
        p = cities.loc[city].geometry.representative_point()
        label_xy = fig.transFigure.inverted().transform(overview.transData.transform((p.x, p.y)))
        fig.text(*label_xy, city, fontsize=16, ha='center', color='#5B5B5B', zorder=9,
                 bbox=dict(facecolor='white', edgecolor='none', alpha=.95, pad=1.2))
    # 같은 범위의 사각형과 연결선. 색상은 데이터 범례와 충돌하지 않는 회색이다.
    connector_specs = {'운정중앙': ((0, .70), (1, .72)),
                       '킨텍스': ((.5, 0), (.5, 1)),
                       '대곡': ((1, .25), (0, .64))}
    for name in ORDER:
        x0, y0, x1, y1 = bounds[name]
        overview.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, fill=False,
                                    edgecolor='#555555', linewidth=1.1, zorder=5))
        a, b = connector_specs[name]
        point = (x0 + (x1-x0)*a[0], y0 + (y1-y0)*a[1])
        if name == '킨텍스':
            # 아래 패널의 제목을 가로지르지 않고 오른쪽 여백으로 돌아 연결한다.
            start = fig.transFigure.inverted().transform(overview.transData.transform((x1, (y0+y1)/2)))
            end = fig.transFigure.inverted().transform(axes[name].transAxes.transform((1, .78)))
            path = MplPath([start, (.652, start[1]), (.652, end[1]), end],
                           [MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO])
            fig.add_artist(PathPatch(path, transform=fig.transFigure, facecolor='none',
                                     edgecolor='#777777', lw=.9, zorder=3))
        else:
            connection = ConnectionPatch(xyA=point, xyB=b, coordsA='data', coordsB='axes fraction',
                                         axesA=overview, axesB=axes[name], color='#777777',
                                         lw=.9, zorder=3, clip_on=False)
            fig.add_artist(connection)
    overview.text(.94, .94, 'N\n↑', transform=overview.transAxes, ha='center', va='top',
                  fontsize=15, color='#333', zorder=10)
    _scale(overview, bounds['overview'], 5000)
    handles = [Patch(facecolor=COLORS[k], edgecolor='#444', label=label)
               for k, label in [(-1, '감소'), (0, '유지'), (1, '증가')]]
    handles.append(Line2D([], [], marker='*', color='none', markerfacecolor='#138A55',
                          markeredgecolor='white', markersize=17, label='GTX-A역'))
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, .055),
               ncol=4, frameon=False, fontsize=18, handlelength=1.5, columnspacing=2.5)
    fig.text(.5, .025, '하루 전체 광역버스 승차 변화 · 2025.11.06 − 2024.10.17 · 250 m 격자',
             ha='center', color='#4B4B4B', fontsize=14)
    fig.canvas.draw()
    return fig, axes, bounds


def _capture_footprint(pixels, part, station):
    """사진 속 실제 색상 격자와 GIS 격자를 대조해 캡처 범위를 추정한다.

    사진을 변형하지 않는다. 대응 격자 중심점의 잔차가 2.5 px 이내인 경우만
    중앙 위치도의 범위 표시로 사용하며, 캡처 범위를 임의 좌표로 채우지 않는다.
    """
    from scipy import ndimage
    from scipy.spatial import cKDTree
    from shapely.geometry import Polygon
    rgb = pixels[:, :, :3].astype(float)
    r, g, b = rgb.transpose(2, 0, 1)
    green = (r < 100) & (g > 70) & (g > r * 1.5) & (g > b * 1.15)
    labels, _ = ndimage.label(green)
    stars = []
    for i, obj in enumerate(ndimage.find_objects(labels), 1):
        if obj is not None and (labels[obj] == i).sum() > 300:
            yy, xx = np.nonzero(labels == i)
            stars.append([xx.mean(), yy.mean()])
    if len(stars) != 1:
        raise ValueError('캡처에서 GTX역 별을 하나로 식별하지 못했습니다. 제공한 원본 캡처를 확인해 주세요.')
    pairs = []
    masks = [(-1, (r > 140) & (r > g*1.35) & (r > b*1.3) & (g < 170) & (b < 170)),
             (1, (b > r*1.15) & (b > g*.98) & (b > 90) & (r < 160) & (g < 190))]
    for sign, mask in masks:
        labels, _ = ndimage.label(mask)
        detections = []
        for i, obj in enumerate(ndimage.find_objects(labels), 1):
            if obj is None:
                continue
            count = (labels[obj] == i).sum()
            h, w = obj[0].stop-obj[0].start, obj[1].stop-obj[1].start
            if count > 1300 and 55 < w < 95 and 55 < h < 95 and count/(w*h) > .75:
                detections.append([(obj[1].start+obj[1].stop-1)/2,
                                   (obj[0].start+obj[0].stop-1)/2])
        selected = part[np.sign(part.change).eq(sign)]
        centers = selected.geometry.centroid
        # 제공된 사진의 250 m 격자 한 변 약 75 px를 대응점 검색의 초기값으로만 사용.
        initial = np.column_stack([(centers.x-station.x)*.30+stars[0][0],
                                   -(centers.y-station.y)*.30+stars[0][1]])
        distances, indices = cKDTree(initial).query(detections)
        for pixel, distance, j in zip(detections, distances, indices):
            if distance < 25:
                pairs.append((centers.x.iloc[j]-station.x, centers.y.iloc[j]-station.y,
                              pixel[0], pixel[1], int(selected.iloc[j]['셀 ID'])))
    pairs = np.asarray(pairs)
    if len(pairs) < 8 or len(set(pairs[:, 4])) != len(pairs):
        raise ValueError('사진과 실제 격자의 대응점을 충분히 확인하지 못했습니다.')
    original_pair_count = len(pairs)
    # 두꺼운 강조선·지도 글자가 가린 격자는 이미지 대응점으로만 제외한다.
    # 분석 격자와 사진 픽셀은 그대로 두며 최소 80%의 대응점이 남아야 한다.
    max_rejected = int(original_pair_count * .2)
    for rejected in range(max_rejected + 1):
        design = np.column_stack([pairs[:, :2], np.ones(len(pairs))])
        affine = np.linalg.lstsq(design, pairs[:, 2:4], rcond=None)[0]
        residual = np.linalg.norm(design @ affine-pairs[:, 2:4], axis=1)
        if residual.max() <= 2.5:
            break
        if rejected == max_rejected or len(pairs) <= 8:
            raise ValueError(f'캡처 범위 대조 오차가 큽니다: {residual.max():.2f} px')
        pairs = np.delete(pairs, residual.argmax(), axis=0)
    height, width = pixels.shape[:2]
    corners = np.asarray([[0, 0], [width, 0], [width, height], [0, height]])
    world = (corners-affine[2]) @ np.linalg.inv(affine[:2]) + [station.x, station.y]
    footprint = Polygon(world)
    assert footprint.is_valid and footprint.covers(station)
    return footprint, {'대응 격자': len(pairs), '최대 잔차(px)': float(residual.max()),
                       '가려진 대응점 제외': original_pair_count-len(pairs)}


def make_capture_figure(grid, stations, cities, root):
    """중앙 GIS 위치도와 사용자가 제공한 카카오맵 사진 3개를 합성. 파일 저장 없음."""
    from PIL import Image
    from matplotlib.patches import Polygon as MplPolygon
    setup_font()
    root = Path(root)
    projected = grid.to_crs(5179)
    projected_stations = stations.to_crs(5179).set_index('역명')
    photos, footprints, validation = {}, {}, {}
    filenames = {'운정중앙': '운정중앙 카맵.png', '킨텍스': '킨텍스 카맵.png',
                 '대곡': '대곡역 카맵.png'}
    for name in ORDER:
        path = root / filenames[name]
        if not path.is_file():
            raise FileNotFoundError(f'제공된 카카오맵 캡처 파일이 필요합니다: {path}')
        # 원본 전체 픽셀과 카카오 출처·축척을 그대로 사용한다.
        photos[name] = np.asarray(Image.open(path).convert('RGB'))
        footprint, check = _capture_footprint(photos[name],
            projected[projected.nearest_station.eq(name)], projected_stations.loc[name].geometry)
        footprints[name] = gpd.GeoSeries([footprint], crs=5179).to_crs(3857).iloc[0]
        validation[name] = check
    fig = plt.figure(figsize=(21, 12), dpi=150, facecolor='white')
    positions = {'운정중앙': [.02, .55, .31, .31*21/12*photos['운정중앙'].shape[0]/photos['운정중앙'].shape[1]],
                 '킨텍스': [.02, .085, .31, .31*21/12*photos['킨텍스'].shape[0]/photos['킨텍스'].shape[1]],
                 '대곡': [.67, .33, .31, .31*21/12*photos['대곡'].shape[0]/photos['대곡'].shape[1]],
                 'overview': [.375, .255, .25, .57]}
    axes = {}
    for name in ORDER:
        ax = fig.add_axes(positions[name]); axes[name] = ax
        ax.imshow(photos[name], interpolation='none')
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_linewidth(.8); spine.set_edgecolor('#333333')
        ax.set_title(f'{name}역 권역', fontsize=22, fontweight='bold', pad=13)
    overview = fig.add_axes(positions['overview']); axes['overview'] = overview
    target = cities.loc[['파주시', '고양시']]
    bounds = _fit_bounds(target.total_bounds, positions['overview'][2]*21/(positions['overview'][3]*12), .04)
    _frame(overview, bounds)
    cities.plot(ax=overview, facecolor='#F1F1F1', edgecolor='#D5D5D5', linewidth=.6, zorder=1)
    target.plot(ax=overview, facecolor='white', edgecolor='#666666', linewidth=.9, zorder=2)
    grid.plot(ax=overview, facecolor='#929292', edgecolor='none', zorder=3)
    stations.plot(ax=overview, marker='*', color='#138A55', markersize=115,
                  edgecolor='white', linewidth=.7, zorder=5)
    overview.set_title('연구 대상지 위치', fontsize=21, pad=15)
    for city in ['파주시', '고양시']:
        p = cities.loc[city].geometry.representative_point()
        label_xy = fig.transFigure.inverted().transform(overview.transData.transform((p.x, p.y)))
        fig.text(*label_xy, city, ha='center', fontsize=16, color='#555555', zorder=10,
                 bbox=dict(facecolor='white', edgecolor='none', alpha=.95, pad=1))
    connections = {'운정중앙': ((0, .7), (1, .6)),
                   '킨텍스': ((0, .35), (1, .55)),
                   '대곡': ((1, .5), (0, .5))}
    for name in ORDER:
        polygon = footprints[name]
        overview.add_patch(MplPolygon(np.asarray(polygon.exterior.coords), fill=False,
                                       edgecolor='#333333', linewidth=1, zorder=6))
        x0, y0, x1, y1 = polygon.bounds
        start, end = connections[name]
        point = (x0+(x1-x0)*start[0], y0+(y1-y0)*start[1])
        fig.add_artist(ConnectionPatch(xyA=point, xyB=end, coordsA='data', coordsB='axes fraction',
                                       axesA=overview, axesB=axes[name], color='#747474',
                                       lw=.85, zorder=4, clip_on=False))
    overview.text(.94, .96, 'N\n↑', transform=overview.transAxes, fontsize=14,
                  ha='center', va='top', zorder=10)
    _scale(overview, bounds, 5000)
    handles = [Patch(facecolor=COLORS[k], edgecolor='#444444', label=label)
               for k, label in [(-1, '감소'), (0, '유지'), (1, '증가')]]
    handles.append(Line2D([], [], marker='*', color='none', markerfacecolor='#138A55',
                          markeredgecolor='white', markersize=17, label='GTX-A역'))
    handles.insert(3, Patch(facecolor='white', edgecolor='#00E5FF', linewidth=3,
                            label='40건 이상 감소',
                            path_effects=[pe.withStroke(linewidth=5, foreground='#111111')]))
    # Matplotlib의 열 우선 배치에 맞춰 첫 줄은 감소·유지·증가 순서로 둔다.
    legend_handles = [handles[i] for i in [0, 3, 1, 4, 2]]
    fig.legend(handles=legend_handles, loc='lower center', bbox_to_anchor=(.665, .13), ncol=3,
               frameon=False, fontsize=16, handlelength=1.2, columnspacing=1.5, labelspacing=.8)
    fig.text(.665, .09, '하루 전체 광역버스 승차 변화 · 2025.11.06 − 2024.10.17',
             ha='center', fontsize=13, color='#444444')
    fig.text(.665, .061, '중앙 위치도: 분석 격자 126개 · 확대 사진: 각 권역의 일부 지역',
             ha='center', fontsize=13, color='#444444')
    fig.canvas.draw()
    return fig, axes, validation


def _tiles(bounds, zoom):
    origin = math.pi * 6378137
    width = 2 * origin / (2 ** zoom)
    x0, y0, x1, y1 = bounds
    for x in range(math.floor((x0 + origin)/width), math.floor((x1+origin)/width)+1):
        for y in range(math.floor((origin-y1)/width), math.floor((origin-y0)/width)+1):
            yield {'url': f'https://a.basemaps.cartocdn.com/light_nolabels/{zoom}/{x}/{y}.png',
                   'extent': [x*width-origin, origin-(y+1)*width, (x+1)*width-origin, origin-y*width]}


def browser_page(fig, axes, bounds, dpi=300):
    """SVG/PNG와 타일 URL을 메모리에서 조합. 외부 요청은 브라우저에서만 한다."""
    buffer = io.StringIO()
    fig.savefig(buffer, format='svg', facecolor='white')  # 파일 경로 없이 메모리 출력
    svg = ET.fromstring(buffer.getvalue())
    width, height = [float(v) for v in svg.attrib['viewBox'].split()[2:]]
    definitions = svg.find(f'{{{NS}}}defs')
    tile_jobs = []
    for name in ORDER:
        i = ORDER.index(name)
        group = svg.find(f'.//*[@id="basemap_{i}"]')
        pos = axes[name].get_position()
        left, top, w, h = pos.x0*width, (1-pos.y1)*height, pos.width*width, pos.height*height
        clip_id = f'tile_clip_{i}'
        cp = ET.SubElement(definitions, f'{{{NS}}}clipPath', {'id': clip_id})
        ET.SubElement(cp, f'{{{NS}}}rect', {'x': str(left), 'y': str(top), 'width': str(w), 'height': str(h)})
        group.set('clip-path', f'url(#{clip_id})')
        b = bounds[name]
        # 250 m 격자를 충분히 읽을 수 있는 원본 타일 해상도. 패널당 약 15~40장.
        zoom = 13 if name == '킨텍스' else 12
        for j, tile in enumerate(_tiles(b, zoom)):
            x0, y0, x1, y1 = tile.pop('extent')
            attrs = {'id': f'tile_{i}_{j}', 'x': str(left+(x0-b[0])/(b[2]-b[0])*w),
                     'y': str(top+(b[3]-y1)/(b[3]-b[1])*h),
                     'width': str((x1-x0)/(b[2]-b[0])*w+.02),
                     'height': str((y1-y0)/(b[3]-b[1])*h+.02),
                     'preserveAspectRatio': 'none', 'opacity': '.85'}
            ET.SubElement(group, f'{{{NS}}}image', attrs)
            tile_jobs.append({'id': attrs['id'], 'url': tile['url']})
    # 지도 출처를 그림 자체에도 포함한다.
    attribution = ET.SubElement(svg, f'{{{NS}}}text', {
        'x': str(width-10), 'y': str(height-5), 'text-anchor': 'end',
        'font-size': '7', 'fill': '#777', 'font-family': 'sans-serif'})
    attribution.text = 'Basemap © OpenStreetMap contributors © CARTO'
    svg_text = ET.tostring(svg, encoding='unicode')
    template = r'''<!doctype html><html lang="ko"><meta charset="utf-8">
<style>body{margin:0;background:white;font-family:Arial,sans-serif}header{padding:10px 14px;color:#444;font-size:14px}
button{border:1px solid #bbb;background:white;padding:6px 12px;margin-right:8px;border-radius:4px;cursor:pointer}
#vectors svg,#raster img{width:100%;height:auto;display:block}#raster{display:none}#error{color:#a32;padding:8px 14px;display:none}</style>
<header><button id="png" disabled>PNG 보기</button><button id="svg">SVG 보기</button><span id="status">실제 배경지도 불러오는 중…</span></header>
<div id="error"></div><div id="vectors">__SVG__</div><div id="raster"></div>
<script>
const jobs=__JOBS__, NS='http://www.w3.org/2000/svg';
const status=document.getElementById('status');
async function dataURL(blob){return await new Promise((resolve,reject)=>{let r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(blob);});}
let cursor=0,ok=0,failed=0;
async function worker(){while(cursor<jobs.length){let j=jobs[cursor++];try{
 const response=await fetch(j.url,{signal:AbortSignal.timeout(20000)});
 if(!response.ok)throw Error(response.status);
 document.getElementById(j.id).setAttribute('href',await dataURL(await response.blob()));ok++;
 }catch(e){failed++;} status.textContent=`배경지도 ${ok}/${jobs.length}장 불러옴`;
}}
async function main(){await Promise.all(Array.from({length:6},worker));
 if(failed){let e=document.getElementById('error');e.style.display='block';e.textContent=`배경지도 ${failed}장이 로드되지 않았습니다. 인터넷 연결을 확인한 뒤 셀을 다시 실행해 주세요. 지형이 빠진 그림을 완성본으로 사용하지 마세요.`;}
 const s=document.querySelector('#vectors svg');
 // 현재 SVG에 타일이 모두 data URL로 들어 있으므로 새 이미지에도 재요청하지 않는다.
 const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(s)],{type:'image/svg+xml;charset=utf-8'}));
 let picture=new Image();picture.src=url;await picture.decode();
 const canvas=document.createElement('canvas');canvas.width=__PXW__;canvas.height=__PXH__;
 const context=canvas.getContext('2d');context.fillStyle='white';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(picture,0,0,canvas.width,canvas.height);
 let png=new Image();png.alt='GTX-A 연구 대상지 지도';png.src=canvas.toDataURL('image/png');
 await png.decode();document.getElementById('raster').replaceChildren(png);URL.revokeObjectURL(url);
 document.getElementById('png').disabled=false;
 status.textContent=failed?'배경지도 일부 누락 · 연결 확인 필요':'완료 · 이미지 우클릭으로 복사 · 파일 자동 저장 없음';
 document.getElementById('png').click();
}
document.getElementById('png').onclick=()=>{document.getElementById('raster').style.display='block';document.getElementById('vectors').style.display='none';};
document.getElementById('svg').onclick=()=>{document.getElementById('raster').style.display='none';document.getElementById('vectors').style.display='block';};
main().catch(e=>{status.textContent='PNG 표시 오류: '+e.message;});
</script></html>'''
    return (template.replace('__SVG__', svg_text).replace('__JOBS__', json.dumps(tile_jobs))
            .replace('__PXW__', str(round(fig.get_figwidth()*dpi)))
            .replace('__PXH__', str(round(fig.get_figheight()*dpi))))


def show_browser_map(page, height=790):
    """지도는 로컬 메모리 서버로만 제공. HTML·PNG·SVG·타일 파일 쓰기 없음."""
    from IPython.display import display, IFrame, HTML
    for old in _SERVERS:
        old.shutdown(); old.server_close()
    _SERVERS.clear()
    payload = page.encode('utf-8')
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(payload)
        def log_message(self, *args):
            pass
    try:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    except OSError:
        # 포트 사용이 제한된 환경도 파일을 생성하지 않고 노트북 안에 표시한다.
        display(HTML(f'<iframe srcdoc="{html.escape(page, quote=True)}" '
                     f'width="100%" height="{int(height)}" style="border:0" '
                     'sandbox="allow-scripts allow-same-origin"></iframe>'))
        return '노트북 내부 지도 (별도 포트 사용 없음)'
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _SERVERS.append(server)
    url = f'http://127.0.0.1:{server.server_port}/'
    display(IFrame(url, width='100%', height=height))
    return url
