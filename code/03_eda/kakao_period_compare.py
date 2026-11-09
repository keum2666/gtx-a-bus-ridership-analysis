"""종일·출근시간대 변화 구분을 같은 범위에서 비교하는 논문용 지도.

JavaScript 키는 환경변수 또는 실행 시 입력으로만 사용한다.
python code/03_eda/kakao_period_compare.py --port 8765
"""
from pathlib import Path
import argparse
import getpass
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

ORDER = ['운정중앙', '킨텍스', '대곡']
PERIODS = ['하루 전체', '출근시간대']
COLORS = {-1: '#D73027', 0: '#EEEEEE', 1: '#2166AC'}
STATIONS = {'운정중앙': (37.716670, 126.728330), '킨텍스': (37.665000, 126.748060), '대곡': (37.631626, 126.811024)}


def prepare_comparison(map_grid, tables):
    import numpy as np
    import pandas as pd
    result = map_grid.copy()
    result['하루전체_변화량'] = result.board_2025 - result.board_2024
    result['출근_변화량'] = result.morning_2025 - result.morning_2024
    result['하루전체_구분'] = np.sign(result['하루전체_변화량']).astype(int)
    result['출근_구분'] = np.sign(result['출근_변화량']).astype(int)
    result['구분변경'] = result['하루전체_구분'].ne(result['출근_구분'])
    result['증감반전'] = result['하루전체_구분'] * result['출근_구분'] == -1
    labels = {-1: '감소', 0: '유지', 1: '증가'}
    result['전환'] = result['하루전체_구분'].map(labels) + ' → ' + result['출근_구분'].map(labels)
    for prefix, col in [('board', '하루전체_구분'), ('morning', '출근_구분')]:
        result[f'{prefix}_compare_color'] = result[col].map(COLORS)
    changed = result.loc[result['구분변경']].drop(columns='geometry')
    changed.to_csv(tables / '3_1_3_시간대별_변화구분이_다른_격자.csv', index=False, encoding='utf-8-sig')
    summary = result.groupby('nearest_station').agg(격자수=('셀 ID', 'size'), 구분변경=('구분변경', 'sum'), 증감반전=('증감반전', 'sum')).reindex(ORDER)
    summary.loc['전체'] = summary.sum()
    summary['유지포함변경'] = summary['구분변경'] - summary['증감반전']
    summary.to_csv(tables / '3_1_3_시간대비교_요약.csv', encoding='utf-8-sig')
    transitions = pd.crosstab(result['하루전체_구분'].map(labels), result['출근_구분'].map(labels)).reindex(index=['감소','유지','증가'], columns=['감소','유지','증가'], fill_value=0)
    transitions.to_csv(tables / '3_1_3_시간대별_변화구분_교차표.csv', encoding='utf-8-sig')
    assert len(result) == 126 and result['셀 ID'].is_unique
    assert int(result['구분변경'].sum()) == 27 and int(result['증감반전'].sum()) == 8
    return result, summary


def make_payload(data, stations, tables):
    import geopandas as gpd
    from shapely.geometry import box
    geo = data.to_crs(4326)
    payload = {}
    for station in ORDER:
        part = data.loc[data.nearest_station.eq(station)]
        st = stations.loc[stations['역명'].eq(station)].geometry.iloc[0]
        full = part.total_bounds
        pad_x = max((full[2]-full[0])*.07, 300)
        pad_y = max((full[3]-full[1])*.07, 300)
        full = [full[0]-pad_x, full[1]-pad_y, full[2]+pad_x, full[3]+pad_y]
        # 원거리 격자 때문에 주요 지역이 작아지는 권역은 확대 범위를 별도로 둔다.
        if station == '운정중앙':
            main = [st.x-4200, st.y-2700, st.x+4200, st.y+3500]
        elif station == '대곡':
            main = [st.x-2200, st.y-3700, st.x+3600, st.y+4000]
        else:
            main = full
        bounds = {}
        for name, values in [('main',main),('all',full)]:
            bounds[name] = list(gpd.GeoSeries([box(*values)], crs=data.crs).to_crs(4326).total_bounds)
        features = []
        for _, row in geo.loc[geo.nearest_station.eq(station)].iterrows():
            features.append({'id':int(row['셀 ID']), 'paths':row.geometry.__geo_interface__['coordinates'],
                'center':[row.geometry.centroid.y,row.geometry.centroid.x],
                'changed':bool(row['구분변경']), 'transition':row['전환'],
                'before':[int(row.board_2024),int(row.morning_2024)],
                'after':[int(row.board_2025),int(row.morning_2025)],
                'change':[int(row['하루전체_변화량']),int(row['출근_변화량'])],
                'color':[row.board_compare_color,row.morning_compare_color]})
        payload[station] = {'station':station,'point':STATIONS[station], 'bounds':bounds,
            'projected_bounds':{'main':main,'all':full},
            'changed_count':sum(f['changed'] for f in features), 'features':features,
            'main_count':int(part.geometry.intersects(box(*main)).sum())}
    (tables / '3_1_3_카카오_시간대비교.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return payload


def render_static(data, stations, background, outline, figures, tables, save):
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.patches import Patch, Rectangle
    payload = make_payload(data, stations, tables)
    handles = [Patch(facecolor=COLORS[-1],edgecolor='#333333',label='감소'),
               Patch(facecolor=COLORS[0],edgecolor='#333333',label='유지'),
               Patch(facecolor=COLORS[1],edgecolor='#333333',label='증가'),
               Patch(facecolor='white',edgecolor='#FFD400',linewidth=3,label='시간대별 변화 구분이 다른 격자')]

    def draw(ax, part, prefix, bounds, labels=True):
        x0,y0,x1,y1 = bounds
        background.cx[x0:x1,y0:y1].plot(ax=ax,facecolor='#F4F4F4',edgecolor='#D9D9D9',linewidth=.25,zorder=1)
        outline.boundary.plot(ax=ax,color='#999999',linewidth=.7,zorder=2)
        part.plot(ax=ax,color=part[f'{prefix}_compare_color'],edgecolor='#222222',linewidth=1.05,zorder=3)
        change = part.loc[part['구분변경']]
        change.boundary.plot(ax=ax,color='#FFD400',linewidth=3.8,zorder=4)
        if labels:
            for _,row in change.iterrows():
                p = row.geometry.representative_point()
                if not (x0 <= p.x <= x1 and y0 <= p.y <= y1): continue
                value = int(row['하루전체_변화량' if prefix=='board' else '출근_변화량'])
                ax.text(p.x,p.y,f'{value:+d}' if value else '0',ha='center',va='center',fontsize=11,fontweight='bold',zorder=7,
                        path_effects=[pe.withStroke(linewidth=2.4,foreground='white')])
        ax.set_xlim(x0,x1); ax.set_ylim(y0,y1); ax.set_aspect('equal'); ax.set_axis_off()

    for i,station in enumerate(ORDER):
        part=data.loc[data.nearest_station.eq(station)]
        for view in (['main','all'] if station=='운정중앙' else ['main']):
            bounds=payload[station]['projected_bounds'][view]
            fig,axes=plt.subplots(1,2,figsize=(15,7.4))
            for ax,period,prefix in zip(axes,PERIODS,['board','morning']):
                draw(ax,part,prefix,bounds)
                stations.loc[stations['역명'].eq(station)].plot(ax=ax,color='#00A651',marker='*',markersize=250,edgecolor='white',linewidth=1,zorder=6)
                ax.set_title(period,fontsize=22,fontweight='bold',pad=16)
                if station=='운정중앙' and view=='main':
                    inset=ax.inset_axes([.765,.65,.23,.34]);draw(inset,part,prefix,payload[station]['projected_bounds']['all'],False)
                    inset.add_patch(Rectangle((bounds[0],bounds[1]),bounds[2]-bounds[0],bounds[3]-bounds[1],fill=False,edgecolor='#111111',linewidth=1.3))
                    inset.set_title('권역 전체',fontsize=11,fontweight='bold')
            fig.legend(handles=handles,loc='lower center',ncol=4,frameon=False,fontsize=14,bbox_to_anchor=(.5,.035))
            fig.subplots_adjust(left=.015,right=.985,top=.91,bottom=.13,wspace=.06)
            stem=f'그림{6+i*3:02d}_{station}_광역버스_승차변화_격자지도_시간대비교'
            if view=='all':stem += '_전체범위'
            save(fig,stem)
    return payload


def render_combined(data, stations, background, outline, tables, save):
    """한 지도에서 각 격자의 왼쪽은 종일, 오른쪽은 출근시간대를 표시한다."""
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle
    from shapely.geometry import box

    payload = make_payload(data, stations, tables)
    handles = [Patch(facecolor=COLORS[-1], edgecolor='#333333', label='감소'),
               Patch(facecolor=COLORS[0], edgecolor='#333333', label='유지'),
               Patch(facecolor=COLORS[1], edgecolor='#333333', label='증가'),
               Patch(facecolor='white', edgecolor='#FFD400', linewidth=3,
                     label='두 시간대의 변화 구분이 다름')]

    def draw(ax, part, bounds, small=False):
        x0, y0, x1, y1 = bounds
        background.cx[x0:x1, y0:y1].plot(ax=ax, facecolor='#F4F4F4',
                                        edgecolor='#DDDDDD', linewidth=.25, zorder=1)
        outline.boundary.plot(ax=ax, color='#999999', linewidth=.7, zorder=2)
        halves, colors = [], []
        for _, row in part.iterrows():
            left, bottom, right, top = row.geometry.bounds
            middle = (left + right) / 2
            halves.extend([row.geometry.intersection(box(left, bottom, middle, top)),
                           row.geometry.intersection(box(middle, bottom, right, top))])
            colors.extend([row.board_compare_color, row.morning_compare_color])
        gpd.GeoSeries(halves, crs=part.crs).plot(ax=ax, color=colors,
                                               edgecolor='none', zorder=3)
        part.boundary.plot(ax=ax, color='#333333', linewidth=.55 if small else 1.1, zorder=4)
        different = part.loc[part['구분변경']]
        different.boundary.plot(ax=ax, color='#FFD400', linewidth=1.6 if small else 4, zorder=5)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect('equal')
        ax.set_axis_off()

    for station in ORDER:
        part = data.loc[data.nearest_station.eq(station)]
        bounds = payload[station]['projected_bounds']['main']
        fig, ax = plt.subplots(figsize=(12.5, 10))
        draw(ax, part, bounds)
        stations.loc[stations['역명'].eq(station)].plot(
            ax=ax, color='#00A651', marker='*', markersize=290,
            edgecolor='white', linewidth=1.1, zorder=7)
        fig.text(.5, .965, '격자 왼쪽: 하루 전체    /    격자 오른쪽: 출근시간대',
                 ha='center', va='top', fontsize=19, fontweight='bold')
        if station in ['운정중앙', '대곡']:
            # 대곡은 격자가 적은 왼쪽 아래에 전체 지도를 배치한다.
            inset_position = [.775, .655, .22, .34] if station == '운정중앙' else [.015, .025, .24, .34]
            inset = ax.inset_axes(inset_position)
            draw(inset, part, payload[station]['projected_bounds']['all'], small=True)
            inset.add_patch(Rectangle((bounds[0], bounds[1]), bounds[2]-bounds[0],
                                      bounds[3]-bounds[1], fill=False,
                                      edgecolor='#111111', linewidth=1.3))
            inset.set_title('권역 전체', fontsize=12, fontweight='bold')
        fig.legend(handles=handles, loc='lower center', ncol=4, frameon=False,
                   fontsize=14, bbox_to_anchor=(.5, .035))
        fig.subplots_adjust(left=.02, right=.98, top=.92, bottom=.12)
        number = 6 + ORDER.index(station) * 3
        save(fig, f'그림{number:02d}_{station}_광역버스_시간대_통합지도')


def page(item, app_key, view='main'):
    payload=json.dumps(item,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    template=r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>__STATION__ 시간대 비교 지도</title>
<style>*{box-sizing:border-box}body{margin:0;background:white;color:#111;font-family:Arial,'Apple SD Gothic Neo',sans-serif;font-weight:700}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px 12px 0;height:calc(100vh - 75px)}.panel{display:flex;flex-direction:column;min-width:0}.title{text-align:center;font-size:26px;padding:4px 0 12px}.map{flex:1;min-height:300px;background:#eee;border:1px solid #ddd}.legend{height:75px;display:flex;flex-wrap:wrap;justify-content:center;align-content:center;gap:10px 24px;font-size:17px}.item{display:flex;align-items:center;gap:8px}.swatch{width:23px;height:21px;border:1px solid #333}.yellow{background:white;border:4px solid #FFD400}.celltext{color:#111;font-size:14px;font-weight:900;text-shadow:-1px -1px white,1px -1px white,-1px 1px white,1px 1px white;white-space:nowrap;pointer-events:none}.station{background:white;border:2px solid #00A651;border-radius:5px;padding:3px 7px;font-size:16px;white-space:nowrap}.status{position:fixed;top:55px;left:18px;z-index:99;background:#fff;padding:6px}.error{color:#B2182B;padding:25px}</style></head><body>
<div class="pair"><section class="panel"><div class="title">하루 전체</div><div id="map0" class="map"></div></section><section class="panel"><div class="title">출근시간대</div><div id="map1" class="map"></div></section></div>
<div class="legend"><span class="item"><i class="swatch" style="background:#D73027"></i>감소</span><span class="item"><i class="swatch" style="background:#EEEEEE"></i>유지</span><span class="item"><i class="swatch" style="background:#2166AC"></i>증가</span><span class="item"><i class="swatch yellow"></i>시간대별 변화 구분이 다른 격자</span><span>숫자: 승차건수 변화량(건)</span></div>
<div id="status" class="status">지도 불러오는 중</div><script>
const data=__DATA__;const view='__VIEW__';
function fail(message){document.getElementById('status').innerText=message;document.getElementById('status').className='status error';}
function init(){if(!window.kakao||!kakao.maps){fail('카카오 지도 SDK 연결을 확인해 주세요');return;}
let ready=0;for(let panel=0;panel<2;panel++){
 const b=data.bounds[view];const map=new kakao.maps.Map(document.getElementById('map'+panel),{center:new kakao.maps.LatLng(data.point[0],data.point[1]),level:6,draggable:false,scrollwheel:false,disableDoubleClickZoom:true});
 for(const f of data.features){
 const paths=f.paths.map(ring=>ring.map(xy=>new kakao.maps.LatLng(xy[1],xy[0])));
 new kakao.maps.Polygon({map,path:paths,strokeWeight:f.changed?5:1,strokeColor:f.changed?'#FFD400':'#222222',strokeOpacity:1,fillColor:f.color[panel],fillOpacity:.78,zIndex:f.changed?4:2});
 if(f.changed){const v=f.change[panel];new kakao.maps.CustomOverlay({map,position:new kakao.maps.LatLng(f.center[0],f.center[1]),content:'<div class="celltext">'+(v>0?'+':'')+v+'</div>',xAnchor:.5,yAnchor:.5,zIndex:8});}
 }
 new kakao.maps.Marker({map,position:new kakao.maps.LatLng(data.point[0],data.point[1])});
 const bounds=new kakao.maps.LatLngBounds(new kakao.maps.LatLng(b[1],b[0]),new kakao.maps.LatLng(b[3],b[2]));map.setBounds(bounds,20,20,20,20);
 kakao.maps.event.addListener(map,'tilesloaded',function(){ready++;if(ready>=2)document.getElementById('status').style.display='none';});
 }
}
</script><script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false" onload="kakao.maps.load(init)" onerror="fail('카카오 지도 SDK 연결 실패')"></script></body></html>'''
    return template.replace('__STATION__',html.escape(item['station'])).replace('__DATA__',payload).replace('__KEY__',quote(app_key,safe='')).replace('__VIEW__',view if view in ['main','all'] else 'main')


def serve(root, app_key, port=8765):
    data=json.loads((root/'results/paper/tables/3_1_3_카카오_시간대비교.json').read_text())
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            u=urlparse(self.path);args=parse_qs(u.query)
            station=args.get('station',['운정중앙'])[0]
            if u.path!='/compare' or station not in data:
                self.send_error(404);return
            body=page(data[station],app_key,args.get('view',['main'])[0]).encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'시간대 비교 지도: http://localhost:{port}/compare',flush=True)
    server.serve_forever()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'config.py').is_file())
    key=os.getenv('KAKAO_JAVASCRIPT_KEY','').strip() or getpass.getpass('카카오 JavaScript 키: ').strip()
    serve(root,key,args.port)
