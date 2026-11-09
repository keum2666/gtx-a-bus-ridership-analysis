"""출근시간대 변화량 정적 지도 배치 3안. TOP 3·순위 표시는 사용하지 않는다."""
from pathlib import Path
import importlib.util
import math


def render_options(root, show=True, options=(1, 2, 3)):
    import geopandas as gpd
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import numpy as np
    from matplotlib.patches import Patch, Rectangle
    from matplotlib.lines import Line2D
    from shapely.geometry import box

    root = Path(root)
    path = root/'code/03_eda/kakao_combined_grid_overlay.py'
    spec = importlib.util.spec_from_file_location('_static_options_data', path)
    helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    data, _ = helpers.load_combined_grid(root)
    color_path = root/'code/03_eda/kakao_morning_capture.py'
    color_spec = importlib.util.spec_from_file_location('_capture_shared_legend', color_path)
    palette = importlib.util.module_from_spec(color_spec); color_spec.loader.exec_module(palette)
    codes = np.searchsorted(palette.BINS, data.morning_change, side='right')
    data['color'] = [palette.COLORS[i] for i in codes]
    handles = [Patch(facecolor=color, edgecolor='#555555', label=label.replace('−', '-'))
               for color, label in zip(palette.COLORS, palette.LABELS)]
    handles.append(Line2D([], [], marker='*', linestyle='none', color='#00865A', markersize=15, label='GTX역'))
    admin = gpd.read_file(root/'data/raw/common/api_cache_gtx_a_routes/HangJeongDong_ver20260701.geojson').to_crs(data.crs)
    admin = admin.loc[admin.geometry.intersects(box(*data.total_bounds))]
    gridpath = next((root/'data/raw/common/grid/빈격자(250m)').glob('*.shp'))
    background = gpd.read_file(gridpath, bbox=tuple(data.total_bounds))
    # 색칠하지 않은 250m 격자 경계도 옅게 표시하여 기존 지도와 같은 공간 맥락을 유지한다.
    background = background.drop_duplicates(subset='geometry')
    payload = helpers.make_combined_payload(data, root)
    out = root/'results/paper/figures/출근시간대_정적지도_배치비교'; out.mkdir(parents=True, exist_ok=True)
    fontpath = Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
    font = fm.FontProperties(fname=str(fontpath)).get_name() if fontpath.exists() else 'DejaVu Sans'
    files = []
    with plt.rc_context({'font.family':font, 'axes.unicode_minus':False}):
        for station in helpers.ORDER:
            part = data.loc[data.nearest_station.eq(station)]
            point = gpd.GeoSeries(gpd.points_from_xy([payload[station]['point'][1]], [payload[station]['point'][0]]), crs=4326).to_crs(data.crs).iloc[0]
            full = part.total_bounds.copy(); pad = np.array([450,450,450,450]); full += pad*np.array([-1,-1,1,1])
            # 실제 격자 중심에서 밀집 구간을 고르고, 두 번째 확대 구간은 떨어진 곳을 우선한다.
            centers = part.geometry.centroid
            xy = np.column_stack([centers.x, centers.y])
            def dense_window(width, height, excluded=None):
                candidates = xy if excluded is None else xy[~((np.abs(xy[:,0]-excluded[0])<width*.65)&(np.abs(xy[:,1]-excluded[1])<height*.65))]
                if len(candidates)==0: candidates = xy
                scores = [((np.abs(xy[:,0]-x)<=width/2)&(np.abs(xy[:,1]-y)<=height/2)).sum() for x,y in candidates]
                x,y = candidates[int(np.argmax(scores))]
                return [x-width/2,y-height/2,x+width/2,y+height/2], (x,y)
            main, _ = dense_window(7200,6200)
            zoom1, center1 = dense_window(4200,3600)
            zoom2, _ = dense_window(4200,3600,center1)

            def draw(ax, bounds, small=False, title=None):
                area = box(*bounds)
                bg = background.cx[bounds[0]:bounds[2],bounds[1]:bounds[3]]
                if len(bg): bg.plot(ax=ax, facecolor='#F7F7F7', edgecolor='#DEDEDE', linewidth=.20, zorder=1)
                adm = admin.loc[admin.geometry.intersects(area)]
                if len(adm): adm.boundary.plot(ax=ax, color='#AAAAAA', linewidth=.6, zorder=2)
                visible = part.loc[part.geometry.intersects(area)]
                if len(visible): visible.plot(ax=ax, color=visible.color, edgecolor='#333333', linewidth=.55 if small else 1.05, zorder=3)
                ax.scatter([point.x],[point.y],marker='*',s=100 if small else 310,c='#00865A',edgecolors='white',linewidths=1,zorder=5)
                ax.set_xlim(bounds[0],bounds[2]); ax.set_ylim(bounds[1],bounds[3]); ax.set_aspect('equal')
                ax.set_xticks([]); ax.set_yticks([])
                for spine in ax.spines.values(): spine.set_edgecolor('#AAAAAA'); spine.set_linewidth(.6)
                if title: ax.set_title(title,fontsize=17,fontweight='bold',pad=12)

            def rect(ax, bounds, label=None, color='#333333'):
                ax.add_patch(Rectangle((bounds[0],bounds[1]),bounds[2]-bounds[0],bounds[3]-bounds[1],
                                      facecolor='none',edgecolor=color,linewidth=1.6,zorder=8))
                if label: ax.text(bounds[0]+100,bounds[3]-150,label,va='top',fontsize=12,fontweight='bold',
                                  bbox=dict(facecolor='white',edgecolor='none',alpha=.95),zorder=9)

            for option in options:
                if option==1:
                    fig, ax = plt.subplots(figsize=(13,10),facecolor='white')
                    draw(ax, main)
                    inset = ax.inset_axes([.74,.66,.25,.32]); draw(inset,full,True,'권역 전체'); rect(inset,main)
                    fig.subplots_adjust(left=.035,right=.965,top=.90,bottom=.14)
                elif option==2:
                    fig = plt.figure(figsize=(17,9),facecolor='white')
                    gs = fig.add_gridspec(1,2,width_ratios=[1,1.7],left=.035,right=.975,top=.85,bottom=.16,wspace=.09)
                    ax1=fig.add_subplot(gs[0]); ax2=fig.add_subplot(gs[1])
                    draw(ax1,full,True,'권역 전체');rect(ax1,main,'확대 범위')
                    draw(ax2,main,False,'주요 지역 확대')
                else:
                    fig = plt.figure(figsize=(16,11),facecolor='white')
                    gs = fig.add_gridspec(2,2,width_ratios=[1.1,1.2],left=.035,right=.975,top=.88,bottom=.15,wspace=.09,hspace=.23)
                    ax1=fig.add_subplot(gs[:,0]); ax2=fig.add_subplot(gs[0,1]); ax3=fig.add_subplot(gs[1,1])
                    draw(ax1,full,True,'권역 전체');rect(ax1,zoom1,'확대 1');rect(ax1,zoom2,'확대 2', '#666666')
                    draw(ax2,zoom1,False,'확대 1');draw(ax3,zoom2,False,'확대 2')
                fig.suptitle(f'{station}역 · 출근시간대 광역버스 승차 변화량',fontsize=24,fontweight='bold',y=.97)
                fig.legend(handles=handles,loc='lower center',ncol=4,frameon=False,
                           fontsize=12,bbox_to_anchor=(.5,.015),columnspacing=2.0,labelspacing=1.1)
                target=out/f'대안{option}_{station}_출근시간대_승차변화량.png'
                fig.savefig(target,dpi=250,facecolor='white',bbox_inches='tight');files.append(target)
                if show: plt.show()
                else: plt.close(fig)
    return files


if __name__=='__main__':
    for result in render_options(Path(__file__).resolve().parents[2],show=False): print(result)
