"""그림 6 대안 3종: 기존 그림·생성 코드·분석자료는 읽기만 한다.

실행: python code/03_eda/figure06_alternatives.py --dpi 400
입력: 기존 논문용_사진.ipynb와 동일한 S1, 공급구조 유지 표, 원시 교통카드,
      행정경계, 250m 원본 shapefile. 카카오 API나 네트워크 연결은 필요 없다.
출력: results/paper/{figures,tables}/figure06_alternatives/
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Patch, Polygon, Rectangle, PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.lines import Line2D
from shapely.geometry import box, Polygon as GeoPolygon

ORDER = [-1, 0, 1]
LABELS = {-1: '감소', 0: '유지', 1: '증가'}
BASE_COLORS = {-1: '#D73027', 0: '#EEEEEE', 1: '#2166AC'}
TYPE_NAMES = ['두 시간대 모두 감소', '두 시간대 모두 유지', '두 시간대 모두 증가',
              '유지 여부가 다름', '감소·증가 방향이 반대']
TYPE_COLORS = ['#E6D3D8', '#E9E9E9', '#CEDFEA', '#F39A20', '#CC2529']


def find_root():
    return next(p for p in [Path.cwd(), *Path.cwd().parents]
                if (p / 'config.py').is_file() and (p / 'code').is_dir())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def setup_font():
    candidates = [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                  Path(r'C:\Windows\Fonts\malgunbd.ttf'),
                  Path('/Library/Fonts/NanumGothicBold.ttf'),
                  Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]
    for p in candidates:
        if p.is_file():
            fm.fontManager.addfont(str(p))
            plt.rcParams['font.family'] = fm.FontProperties(fname=str(p)).get_name()
            break
    else:
        raise FileNotFoundError('한글 글꼴 경로를 확인해 주세요.')
    plt.rcParams.update({'axes.unicode_minus': False, 'font.size': 14,
                         'font.weight': 'bold', 'pdf.fonttype': 42,
                         'axes.titleweight': 'bold', 'figure.facecolor': 'white'})


def load_and_verify(root, table_dir):
    base_path = root / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv'
    stop_path = root / 'data/processed/gtx_a/16_새데이터_공급구조유지_250m격자.csv'
    base = pd.read_csv(base_path, encoding='utf-8-sig').set_index('셀 ID')
    stops = pd.read_csv(stop_path, dtype=str, encoding='utf-8-sig')
    assert len(base) == 126 and base.index.is_unique
    assert set(base.index) == set(stops['셀 ID'].astype(int))
    data = base[['nearest_station', 'board_2024', 'board_2025']].copy()
    inputs = [base_path, stop_path]
    # 기존 그림 생성 셀의 정류장 매핑·승차시각 집계 방식을 그대로 재사용한다.
    for year, date, filename in [
        (2024, '20241017', 'gtx_a_transport_card_20241017_raw_with_coords_api_filled.csv'),
        (2025, '20251106', 'gtx_a_transport_card_20251106_raw_with_coords.csv')]:
        raw_path = root / 'data/raw/gtx_a/transport_card' / filename
        inputs.append(raw_path)
        raw = pd.read_csv(raw_path, dtype=str, encoding='utf-8-sig',
                          usecols=['query_date', 'opr_ymd', '승차정류장ID', 'ride_dt', 'goff_ctpv_cd'])
        assert raw['query_date'].eq(date).all() and raw['opr_ymd'].eq(date).all()
        lookup = pd.DataFrame([(int(row['셀 ID']), stop_id)
                               for _, row in stops.iterrows()
                               for stop_id in re.findall(r'\d{6,}', row[f'{year}년 정류장 ID'])],
                              columns=['셀 ID', '승차정류장ID'])
        assert not lookup['승차정류장ID'].duplicated().any()
        selected = raw.merge(lookup, on='승차정류장ID', how='inner', validate='many_to_one')
        assert selected['goff_ctpv_cd'].eq('11').all()
        counts = selected.groupby('셀 ID').size().reindex(base.index, fill_value=0)
        np.testing.assert_array_equal(counts, base[f'board_{year}'])
        times = pd.to_datetime(selected['ride_dt'], format='%Y%m%d%H%M%S', errors='raise')
        am = selected.loc[times.dt.hour.ge(6) & times.dt.hour.lt(10)]
        data[f'morning_{year}'] = am.groupby('셀 ID').size().reindex(base.index, fill_value=0)
    derived_path = root / 'results/paper/tables/3_1_3_격자별_승차건수_변화량.csv'
    derived = pd.read_csv(derived_path, encoding='utf-8-sig').set_index('셀 ID').reindex(base.index)
    for col in ['board_2024', 'board_2025', 'morning_2024', 'morning_2025']:
        np.testing.assert_array_equal(data[col], derived[col])
    inputs.append(derived_path)

    # 원본 shapefile의 행 순서와 011의 중복 제거·ID 부여 순서를 그대로 복원한다.
    admin_path = root / 'data/raw/common/api_cache_gtx_a_routes/HangJeongDong_ver20260701.geojson'
    grid_path = next((root / 'data/raw/common/grid/빈격자(250m)').glob('*.shp'))
    crs = gpd.read_file(grid_path, rows=1).crs
    admin = gpd.read_file(admin_path).to_crs(crs)
    admin['sgg_code'] = admin['sgg'].astype(str).str.extract(r'([0-9]+)')[0].str.zfill(5)
    cities = admin.loc[admin['sgg_code'].str.startswith(('4128', '4148'))]
    boundary = cities.geometry.union_all()
    geometry = gpd.read_file(grid_path, bbox=boundary.bounds)
    geometry = geometry.loc[geometry.geometry.intersects(boundary)].copy()
    geometry['_key'] = geometry.geometry.apply(lambda g: g.wkb if g is not None else None)
    geometry = geometry.drop_duplicates('_key').drop(columns='_key').reset_index(drop=True)
    geometry['셀 ID'] = np.arange(1, len(geometry) + 1)
    mapped = geometry[['셀 ID', 'geometry']].merge(data.reset_index(), on='셀 ID',
                                                how='inner', validate='one_to_one')
    assert len(mapped) == 126
    centers = mapped.set_index('셀 ID').geometry.centroid.to_crs(4326).reindex(base.index)
    np.testing.assert_allclose(centers.x, base['중심점 경도'], atol=1e-6, rtol=0)
    np.testing.assert_allclose(centers.y, base['중심점 위도'], atol=1e-6, rtol=0)
    inputs.extend([admin_path, *sorted(grid_path.parent.glob(grid_path.stem + '.*'))])

    old_code = root / 'code/03_eda/kakao_period_compare.py'
    spec = importlib.util.spec_from_file_location('existing_figure06', old_code)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    lat, lon = original.STATIONS['운정중앙']
    station = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(crs).iloc[0]
    part = mapped.loc[mapped.nearest_station.eq('운정중앙')].copy().sort_values('셀 ID')
    part['하루전체_변화량'] = part.board_2025 - part.board_2024
    part['출근_변화량'] = part.morning_2025 - part.morning_2024
    part['day_sign'] = np.sign(part['하루전체_변화량']).astype(int)
    part['am_sign'] = np.sign(part['출근_변화량']).astype(int)
    part['different'] = part.day_sign.ne(part.am_sign)
    part['opposite'] = part.day_sign * part.am_sign == -1
    part['type_id'] = np.select([part.day_sign.eq(-1) & part.am_sign.eq(-1),
                                part.day_sign.eq(0) & part.am_sign.eq(0),
                                part.day_sign.eq(1) & part.am_sign.eq(1),
                                part['different'] & ~part['opposite'], part['opposite']],
                               [0, 1, 2, 3, 4], default=-1).astype(int)
    assert part.type_id.ge(0).all()
    part['type_name'] = part.type_id.map(dict(enumerate(TYPE_NAMES)))
    part['direction'] = part.day_sign.map(LABELS) + ' → ' + part.am_sign.map(LABELS)
    matrix = pd.crosstab(part.day_sign, part.am_sign).reindex(index=ORDER, columns=ORDER, fill_value=0)
    matrix.index = [LABELS[i] for i in ORDER]
    matrix.columns = [LABELS[i] for i in ORDER]
    matrix.index.name = '하루 전체'
    matrix.columns.name = '출근시간대'
    stats = {'전체 격자': len(part), '불일치': int(part['different'].sum()),
             '유지 여부 다름': int((part.type_id == 3).sum()),
             '감소·증가 방향 반대': int(part['opposite'].sum()),
             '종일 감소·출근 증가': int((part.day_sign.eq(-1) & part.am_sign.eq(1)).sum()),
             '종일 증가·출근 감소': int((part.day_sign.eq(1) & part.am_sign.eq(-1)).sum())}
    expected = {'전체 격자':63, '불일치':16, '유지 여부 다름':12, '감소·증가 방향 반대':4,
                '종일 감소·출근 증가':2, '종일 증가·출근 감소':2}
    verification = pd.DataFrame([{'검증 항목':k,'실제 집계':v,'확인 기준':expected[k],
                                  '검증': '일치' if v == expected[k] else '불일치'} for k,v in stats.items()])
    verification.to_csv(table_dir / '그림6_표본수_검증.csv', index=False, encoding='utf-8-sig')
    matrix.to_csv(table_dir / '그림6_시간대_교차집계.csv', encoding='utf-8-sig')
    count_table = pd.DataFrame([{'변화 유형':name,'격자 수':int(part.type_id.eq(i).sum())}
                               for i,name in enumerate(TYPE_NAMES)])
    count_table.to_csv(table_dir / '그림6_변화유형별_격자수.csv', index=False, encoding='utf-8-sig')
    part.drop(columns='geometry').to_csv(table_dir / '그림6_63개격자_검증자료.csv', index=False, encoding='utf-8-sig')
    part.loc[part['opposite']].drop(columns='geometry').to_csv(
        table_dir / '그림6_방향반대_4개격자.csv', index=False, encoding='utf-8-sig')
    assert verification['검증'].eq('일치').all(), '검증표의 불일치 원인을 확인하세요. 임의 보정은 하지 않습니다.'
    assert matrix.to_numpy().sum() == 63 and count_table['격자 수'].sum() == 63
    assert matrix.sum(axis=1).tolist() == [39,6,18] and matrix.sum(axis=0).tolist() == [38,10,15]

    x0,y0,x1,y1 = part.total_bounds
    px,py = max((x1-x0)*.07,300),max((y1-y0)*.07,300)
    extent = [x0-px,y0-py,x1+px,y1+py]
    core = [station.x-2100, station.y-1500, station.x+2100, station.y+1800]
    manifest = {'자료 기준': '2024-10-17 / 2025-11-06, 교통카드 행 수, 출근 06:00 이상 10:00 미만',
                'CRS': str(crs), '공통 전체 지도 범위':list(map(float,extent)),
                '공통 확대 지도 범위':list(map(float,core)), 'GTX역 좌표':{'위도':lat,'경도':lon},
                '검증':stats, '기존 생성 코드':str(old_code.relative_to(root)),
                '입력': [{'파일':str(p.relative_to(root)),'sha256':digest(p)} for p in inputs]}
    return part, matrix, count_table, verification, station, boundary, extent, core, manifest


def map_base(ax, data, boundary, extent):
    gpd.GeoSeries([boundary], crs=data.crs).boundary.plot(ax=ax,color='#C7C7C7',linewidth=.75,zorder=1)
    ax.set_xlim(extent[0],extent[2]);ax.set_ylim(extent[1],extent[3])
    ax.set_aspect('equal');ax.set_facecolor('white');ax.set_axis_off()


def station_marker(ax, station, small=False):
    ax.scatter([station.x],[station.y],marker='*',s=130 if small else 230,
               facecolor='#00865A',edgecolor='white',linewidth=1.2,zorder=12)


def type_map(ax, data, boundary, extent, station, summary=False, small=False):
    map_base(ax,data,boundary,extent)
    colors = ['#E8E8E8' if summary and i < 3 else TYPE_COLORS[i] for i in data.type_id]
    data.plot(ax=ax,color=colors,edgecolor='#6A6A6A' if small else '#555555',
              linewidth=.45 if small else .8,zorder=3)
    mismatch=data.loc[data['different']]
    mismatch.boundary.plot(ax=ax,color=[TYPE_COLORS[i] for i in mismatch.type_id],
                           linewidth=1.5 if small else 1.8,zorder=4)
    station_marker(ax,station,small)


def diagonal_map(ax, data, boundary, extent, station, small=False):
    map_base(ax,data,boundary,extent)
    shapes=[];colors=[]
    for _,r in data.iterrows():
        x0,y0,x1,y1=r.geometry.bounds
        ul=r.geometry.intersection(GeoPolygon([(x0,y0),(x0,y1),(x1,y1)]))
        lr=r.geometry.intersection(GeoPolygon([(x0,y0),(x1,y1),(x1,y0)]))
        shapes.extend([ul,lr]);colors.extend([BASE_COLORS[int(r.day_sign)],BASE_COLORS[int(r.am_sign)]])
        assert abs(ul.area + lr.area - r.geometry.area) < 1e-4
        assert ul.intersection(lr).area < 1e-4
    gpd.GeoSeries(shapes,crs=data.crs).plot(ax=ax,color=colors,edgecolor='none',zorder=3)
    data.boundary.plot(ax=ax,color='#555555',linewidth=.4 if small else .7,zorder=4)
    data.loc[data['different']].boundary.plot(ax=ax,color='#FFD200',linewidth=1.8 if small else 2.8,zorder=5)
    if not small:
        opposite=data.loc[data['opposite']]
        for _,r in opposite.iterrows():
            x0,y0,x1,y1=r.geometry.bounds
            ax.plot([x1,x1+150],[y1,y1+150],color='#222222',linewidth=.8,zorder=8)
            ax.scatter([x1+160],[y1+160],marker='D',s=43,facecolor='#171717',edgecolor='white',linewidth=.8,zorder=9)
    station_marker(ax,station,small)


def map_details(ax, extent):
    x0,y0,x1,y1=extent;w=x1-x0;h=y1-y0
    ax.annotate('N',xy=(x0+w*.075,y1-h*.05),xytext=(x0+w*.075,y1-h*.12),ha='center',va='center',
                fontsize=14,fontweight='bold',arrowprops={'arrowstyle':'-|>','color':'#333333','lw':1.3},zorder=14)
    sx,sy=x0+w*.07,y0+h*.045
    ax.plot([sx,sx+1000],[sy,sy],color='#333333',lw=2,zorder=14)
    ax.plot([sx,sx],[sy-70,sy+70],color='#333333',lw=1.4,zorder=14)
    ax.plot([sx+1000,sx+1000],[sy-70,sy+70],color='#333333',lw=1.4,zorder=14)
    ax.text(sx+500,sy+130,'1 km',ha='center',va='bottom',fontsize=11,color='#333333',zorder=14)


def core_inset(ax, data, boundary, core, station, diagonal=False):
    # 분석격자가 없는 공간에 역 주변 확대 지도를 배치해 전체 63개를 가리지 않는다.
    position = [.69, .51, .29, .29]
    x0, y0, x1, y1 = ax.get_xlim()[0], ax.get_ylim()[0], ax.get_xlim()[1], ax.get_ylim()[1]
    inset_footprint = box(x0+(x1-x0)*position[0], y0+(y1-y0)*position[1],
                          x0+(x1-x0)*(position[0]+position[2]),
                          y0+(y1-y0)*(position[1]+position[3]))
    assert not data.geometry.intersects(inset_footprint).any(), '확대 지도가 분석격자를 가립니다.'
    ins=ax.inset_axes(position)
    if diagonal:diagonal_map(ins,data,boundary,core,station,small=True)
    else:type_map(ins,data,boundary,core,station,small=True)
    ins.set_axis_on();ins.set_xticks([]);ins.set_yticks([])
    ins.patch.set_visible(True);ins.set_facecolor('white')
    for spine in ins.spines.values():spine.set_visible(True);spine.set_color('#999999');spine.set_linewidth(.8)
    ins.set_title('운정중앙역 주변 확대',fontsize=12,pad=6)
    ax.add_patch(Rectangle((core[0],core[1]),core[2]-core[0],core[3]-core[1],fill=False,
                           edgecolor='#858585',linestyle='--',linewidth=1,zorder=2))


def save(fig, directory, stem, dpi):
    png=directory / f'{stem}.png'
    fig.savefig(png,dpi=dpi,facecolor='white',bbox_inches='tight',pad_inches=.18)
    fig.savefig(directory / f'{stem}.pdf',facecolor='white',bbox_inches='tight',pad_inches=.18)
    plt.close(fig)
    return png


def alternative_1(data, counts, boundary, extent, core, station, directory, dpi):
    fig,ax=plt.subplots(figsize=(11.5,13.5))
    type_map(ax,data,boundary,extent,station);map_details(ax,extent)
    core_inset(ax,data,boundary,core,station)
    fig.text(.5,.965,'두 시간대의 변화 유형',ha='center',va='top',fontsize=22)
    fig.text(.5,.93,'전체 63개  ·  불일치 16개  ·  방향 반대 4개',ha='center',va='top',fontsize=15)
    handles=[Patch(facecolor=TYPE_COLORS[i],edgecolor='#666666',label=f'{name} ({int(counts.iloc[i]["격자 수"])}개)') for i,name in enumerate(TYPE_NAMES)]
    handles.append(Line2D([],[],marker='*',color='none',markerfacecolor='#00865A',markeredgecolor='white',markersize=16,label='GTX 운정중앙역'))
    fig.legend(handles=handles,loc='lower center',ncol=2,frameon=False,fontsize=13,
               bbox_to_anchor=(.5,.025),columnspacing=2.2,labelspacing=.9)
    fig.subplots_adjust(left=.035,right=.965,top=.90,bottom=.16)
    return save(fig,directory,'대안1_운정중앙_변화유형화_지도',dpi)


def alternative_2(data, boundary, extent, core, station, directory, dpi):
    fig,ax=plt.subplots(figsize=(11.5,13.5))
    diagonal_map(ax,data,boundary,extent,station);map_details(ax,extent)
    core_inset(ax,data,boundary,core,station,diagonal=True)
    fig.text(.5,.968,'대각선 분할 격자 지도',ha='center',va='top',fontsize=22)
    fig.text(.5,.932,'왼쪽 위: 하루 전체    /    오른쪽 아래: 출근시간대',ha='center',va='top',fontsize=15)
    handles=[Patch(facecolor=BASE_COLORS[i],edgecolor='#666666',label=LABELS[i]) for i in ORDER]
    handles.extend([Patch(facecolor='white',edgecolor='#FFD200',linewidth=2.8,label='불일치 16개'),
                    Line2D([],[],marker='D',color='none',markerfacecolor='#171717',markersize=9,label='방향 반대 4개'),
                    Line2D([],[],marker='*',color='none',markerfacecolor='#00865A',markersize=16,label='GTX 운정중앙역')])
    fig.legend(handles=handles,loc='lower center',ncol=3,frameon=False,fontsize=13,bbox_to_anchor=(.5,.04),labelspacing=1)
    fig.subplots_adjust(left=.035,right=.965,top=.90,bottom=.15)
    return save(fig,directory,'대안2_운정중앙_대각선분할_지도',dpi)


def sankey(ax, matrix):
    values=matrix.to_numpy();total=int(values.sum())
    unit=.74/total;gap=.065;left_top={};right_top={};left_height={};right_height={}
    for marginal,tops,heights in [(values.sum(1),left_top,left_height),(values.sum(0),right_top,right_height)]:
        y=.94
        for i,n in enumerate(marginal):
            tops[i]=y;heights[i]=int(n)*unit;y-=int(n)*unit+gap
    left_cursor=left_top.copy();right_cursor=right_top.copy();links=[]
    for i in range(3):
        for j in range(3):
            n=int(values[i,j])
            if not n:continue
            h=n*unit;yt0=left_cursor[i];yb0=yt0-h;yt1=right_cursor[j];yb1=yt1-h
            left_cursor[i]-=h;right_cursor[j]-=h
            typ=i if i==j else 4 if i in [0,2] and j in [0,2] else 3
            color=TYPE_COLORS[typ]
            path=MplPath([(0.16,yt0),(.41,yt0),(.60,yt1),(.84,yt1),(.84,yb1),(.60,yb1),(.41,yb0),(.16,yb0),(0.16,yt0)],
                         [MplPath.MOVETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4,MplPath.LINETO,MplPath.CURVE4,MplPath.CURVE4,MplPath.CURVE4,MplPath.CLOSEPOLY])
            ax.add_patch(PathPatch(path,facecolor=color,edgecolor='white',linewidth=.45,alpha=.86,zorder=2))
            links.append((i,j,n,(yt0+yb0)/2,(yt1+yb1)/2))
    # 작은 흐름의 레이블이 겹치지 않도록 위치를 나눈다. 9개 연결 모두 실제 집계값을 표시한다.
    t_values={(0,0):.48,(0,1):.27,(0,2):.28,(1,0):.72,(1,1):.50,(1,2):.31,
              (2,0):.69,(2,1):.73,(2,2):.50}
    for i,j,n,y0,y1 in links:
        t=t_values[i,j]
        x=(1-t)**3*.16+3*(1-t)**2*t*.41+3*(1-t)*t*t*.60+t**3*.84
        smooth=3*t*t-2*t*t*t;y=y0*(1-smooth)+y1*smooth
        ax.text(x,y,f'{n}개',ha='center',va='center',fontsize=13,zorder=6,
                bbox={'facecolor':'white','edgecolor':'none','alpha':.94,'pad':1.6})
    for i,sign in enumerate(ORDER):
        for x,top,height in [(.10,left_top[i],left_height[i]),(.84,right_top[i],right_height[i])]:
            ax.add_patch(Rectangle((x,top-height),.06,height,facecolor=BASE_COLORS[sign],edgecolor='#555555',lw=.8,zorder=5))
        ax.text(.078,left_top[i]-left_height[i]/2,f'{LABELS[sign]}\n{int(values.sum(1)[i])}개',ha='right',va='center',fontsize=14)
        ax.text(.922,right_top[i]-right_height[i]/2,f'{LABELS[sign]}\n{int(values.sum(0)[i])}개',ha='left',va='center',fontsize=14)
    ax.text(.13,1.01,'하루 전체',ha='center',va='bottom',fontsize=19)
    ax.text(.87,1.01,'출근시간대',ha='center',va='bottom',fontsize=19)
    ax.set_xlim(-.055,1.055);ax.set_ylim(-.005,1.075);ax.axis('off')
    assert len(links)==int((values>0).sum())
    return [{'하루 전체':LABELS[ORDER[i]],'출근시간대':LABELS[ORDER[j]],'격자 수':n} for i,j,n,_,_ in links]


def alternative_3(data, matrix, boundary, extent, station, directory, table_dir, dpi):
    fig=plt.figure(figsize=(17,11.5))
    left=fig.add_axes([.035,.155,.50,.715]);right=fig.add_axes([.565,.155,.405,.715])
    links=sankey(left,matrix)
    pd.DataFrame(links).to_csv(table_dir/'그림6_생키_연결별_격자수.csv',index=False,encoding='utf-8-sig')
    type_map(right,data,boundary,extent,station,summary=True)
    right.set_title('불일치 격자의 위치',fontsize=19,pad=15)
    map_details(right,extent)
    fig.text(.5,.97,'시간대별 변화 구분의 연결과 공간 분포',ha='center',va='top',fontsize=23)
    fig.text(.5,.92,'전체 63개  ·  불일치 16개  ·  방향 반대 4개',ha='center',va='top',fontsize=17)
    handles=[Patch(facecolor='#E8E8E8',edgecolor='#666666',label='두 시간대 구분이 같음 (47개)'),
             Patch(facecolor=TYPE_COLORS[3],edgecolor='#666666',label='유지 여부가 다름 (12개)'),
             Patch(facecolor=TYPE_COLORS[4],edgecolor='#666666',label='감소·증가 방향이 반대 (4개)'),
             Line2D([],[],marker='*',color='none',markerfacecolor='#00865A',markersize=16,label='GTX 운정중앙역')]
    fig.legend(handles=handles,loc='lower center',ncol=2,frameon=False,fontsize=14,
               bbox_to_anchor=(.5,.035),columnspacing=2.6,labelspacing=1)
    return save(fig,directory,'대안3_운정중앙_생키와_요약지도',dpi)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dpi',type=int,default=400);args=parser.parse_args()
    root=find_root();figures=root/'results/paper/figures/figure06_alternatives';tables=root/'results/paper/tables/figure06_alternatives'
    figures.mkdir(parents=True,exist_ok=True);tables.mkdir(parents=True,exist_ok=True)
    protected=[root/'code/03_eda/kakao_period_compare.py',root/'code/03_eda/논문용_사진.ipynb',
               root/'results/paper/figures/그림06_운정중앙_광역버스_시간대_통합지도.png',
               root/'results/paper/figures/그림06_운정중앙_광역버스_시간대_통합지도.pdf']
    before={str(p.relative_to(root)):digest(p) for p in protected}
    setup_font()
    data,matrix,counts,validation,station,boundary,extent,core,manifest=load_and_verify(root,tables)
    outputs=[alternative_1(data,counts,boundary,extent,core,station,figures,args.dpi),
             alternative_2(data,boundary,extent,core,station,figures,args.dpi),
             alternative_3(data,matrix,boundary,extent,station,figures,tables,args.dpi)]
    after={str(p.relative_to(root)):digest(p) for p in protected}
    assert before==after,'기존 파일의 변경을 감지했습니다.'
    manifest['기존 파일 수정 여부']='변경 없음';manifest['기존 파일 SHA256']=after
    manifest['PNG 해상도(dpi)']=args.dpi;manifest['출력 PNG']=[str(p.relative_to(root)) for p in outputs]
    (tables/'그림6_대안_생성기록.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(counts.to_string(index=False));print('\n교차 집계\n'+matrix.to_string());print('\n'+validation.to_string(index=False))
    print('\n기존 그림·코드 변경 없음. 세 대안 PNG/PDF 생성 완료.')

if __name__=='__main__':main()
