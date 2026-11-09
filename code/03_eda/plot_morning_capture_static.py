"""출근시간대 실제 변화량 지도: 주요 지역 확대 + 권역 전체 삽입 지도."""
from pathlib import Path
import importlib.util


def render_morning_static(root, data=None, show=True):
    import geopandas as gpd
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import numpy as np
    from matplotlib.patches import Patch, Rectangle
    from matplotlib.lines import Line2D
    from shapely.geometry import box

    root = Path(root)
    path = root / 'code/03_eda/kakao_morning_capture.py'
    spec = importlib.util.spec_from_file_location('_capture_static_colors', path)
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    helpers = capture.load_helpers(root)
    if data is None:
        data, _ = helpers.load_combined_grid(root)
    data = data.copy()
    data['map_color'] = [capture.COLORS[i] for i in np.searchsorted(capture.BINS, data.morning_change, side='right')]
    font_path = Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
    font = fm.FontProperties(fname=str(font_path)).get_name() if font_path.exists() else 'DejaVu Sans'
    background = gpd.read_file(root / 'data/raw/common/api_cache_gtx_a_routes/HangJeongDong_ver20260701.geojson').to_crs(data.crs)
    background = background.loc[background.geometry.intersects(box(*data.total_bounds))]
    payload = helpers.make_combined_payload(data, root)
    out = root / 'results/paper/figures/출근시간대_승차변화량_확대지도'
    out.mkdir(parents=True, exist_ok=True)
    files = []

    with plt.rc_context({'font.family': font, 'axes.unicode_minus': False, 'font.weight': 'bold'}):
        handles = [Patch(facecolor=color, edgecolor='#555555', label=label.replace("−", "-"))
                   for color, label in zip(capture.COLORS, capture.LABELS)]
        handles += [Line2D([], [], marker='*', linestyle='none', color='#00865A',
                           markersize=15, label='GTX역')]
        for station in helpers.ORDER:
            part = data.loc[data.nearest_station.eq(station)]
            point = gpd.GeoSeries(gpd.points_from_xy([payload[station]['point'][1]], [payload[station]['point'][0]]), crs=4326).to_crs(data.crs).iloc[0]
            all_bounds = gpd.GeoSeries([box(*payload[station]['bounds']['all'])], crs=4326).to_crs(data.crs).total_bounds
            main_bounds = gpd.GeoSeries([box(*payload[station]['bounds']['main'])], crs=4326).to_crs(data.crs).total_bounds
            if station == '킨텍스':
                main_bounds = [point.x-2700, point.y-1900, point.x+3100, point.y+3900]

            def draw(ax, bounds, small=False):
                area = box(*bounds)
                bg = background.loc[background.geometry.intersects(area)].copy()
                bg.geometry = bg.geometry.intersection(area)
                if len(bg):
                    bg.plot(ax=ax, color='#F5F5F5', edgecolor='#CFCFCF', linewidth=.45, zorder=1)
                visible = part.loc[part.geometry.intersects(area)]
                visible.plot(ax=ax, color=visible.map_color, edgecolor='#333333', linewidth=.5 if small else 1, zorder=3)
                ax.scatter([point.x], [point.y], marker='*', s=100 if small else 430,
                           c='#00865A', edgecolors='white', linewidths=1.2, zorder=5)
                if not small:
                    ax.annotate(f'{station}역', (point.x, point.y), xytext=(10, -18), textcoords='offset points',
                                fontsize=15, fontweight='bold', bbox=dict(facecolor='white', edgecolor='none', alpha=.9), zorder=6)
                ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
                ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(small); spine.set_edgecolor('#777777')

            fig, ax = plt.subplots(figsize=(12, 10.5), facecolor='white')
            draw(ax, main_bounds)
            inset = ax.inset_axes([.72, .68, .27, .30])
            inset.set_facecolor('white')
            draw(inset, all_bounds, small=True)
            inset.add_patch(Rectangle((main_bounds[0], main_bounds[1]), main_bounds[2]-main_bounds[0],
                                      main_bounds[3]-main_bounds[1], facecolor='none', edgecolor='#222222', linewidth=1.4, zorder=7))
            inset.set_title('권역 전체', fontsize=13, fontweight='bold', pad=7)
            ax.set_title(f'{station}역 · 출근시간대 승차 변화량', fontsize=23, fontweight='bold', pad=20)
            fig.legend(handles=handles, loc='lower center', ncol=4, frameon=False,
                       fontsize=12, bbox_to_anchor=(.5, .015), columnspacing=1.5, labelspacing=1.1)
            fig.subplots_adjust(left=.035, right=.965, top=.92, bottom=.13)
            target = out / f'{station}_출근시간대_승차변화량_확대_전체.png'
            fig.savefig(target, dpi=300, facecolor='white', bbox_inches='tight')
            files.append(target)
            if show:
                plt.show()
            else:
                plt.close(fig)
    return files


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    for path in render_morning_static(root, show=False):
        print(path)
