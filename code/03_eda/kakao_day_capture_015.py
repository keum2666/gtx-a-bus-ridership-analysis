"""015의 실제 126개 격자, 하루 전체 광역버스 변화 카카오맵. 파일 저장 없음."""
import html
import errno
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
from urllib.parse import quote

import geopandas as gpd
import numpy as np
from shapely.geometry import box

ORDER = ['운정중앙', '킨텍스', '대곡']
VIEW_ID = 'day_capture_015'
COLORS = {-1: '#D73027', 0: '#EEEEEE', 1: '#2166AC'}
HIGHLIGHT_THRESHOLD = -40
HIGHLIGHT_COLOR = '#00E5FF'


def load_map_data(root):
    root = Path(root)
    path = root / 'code/03_eda/study_area_015.py'
    spec = importlib.util.spec_from_file_location('_day_capture_data_015', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    grid, stations, _, summary = module.load_data(root)
    return grid.to_crs(5179), stations.to_crs(5179), summary


def make_payload(grid, stations):
    assert len(grid) == 126 and grid['셀 ID'].is_unique
    np.testing.assert_array_equal(grid.change, grid.board_2025-grid.board_2024)
    assert grid.crs.to_epsg() == 5179
    geographic = grid.to_crs(4326)
    station_geo = stations.to_crs(4326).set_index('역명')
    payload = {}
    for name in ORDER:
        part = grid[grid.nearest_station.eq(name)]
        point = stations[stations['역명'].eq(name)].geometry.iloc[0]
        region = gpd.GeoSeries([*part.geometry, point], crs=grid.crs)
        x0,y0,x1,y1 = region.total_bounds
        px,py = max((x1-x0)*.07,300),max((y1-y0)*.07,300)
        full = [x0-px,y0-py,x1+px,y1+py]
        # 기존 011의 주요지역 확대 범위. 전체 보기는 모든 격자와 역을 포함한다.
        if name == '운정중앙': focus = [point.x-4200,point.y-2700,point.x+4200,point.y+3500]
        elif name == '대곡': focus = [point.x-2200,point.y-3700,point.x+3600,point.y+4000]
        else: focus = full
        bounds = {key:list(map(float,gpd.GeoSeries([box(*values)],crs=grid.crs).to_crs(4326).total_bounds))
                  for key,values in [('all',full),('focus',focus)]}
        assert region.covered_by(box(*full)).all()
        features = []
        for _,row in geographic[geographic.nearest_station.eq(name)].iterrows():
            geometry = row.geometry.__geo_interface__
            paths = [geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
            features.append({'id':int(row['셀 ID']), 'paths':paths,
                             'before':int(row.board_2024),'after':int(row.board_2025),
                             'change':int(row.change),'color':COLORS[int(np.sign(row.change))],
                             'highlight':bool(row.change <= HIGHLIGHT_THRESHOLD)})
        p = station_geo.loc[name].geometry
        payload[name] = {'station':name,'point':[p.y,p.x], 'bounds':bounds,
                         'features':features, 'count':len(features),
                         'highlightCount':sum(feature['highlight'] for feature in features),
                         'highlightThreshold':HIGHLIGHT_THRESHOLD}
    assert sum(len(p['features']) for p in payload.values()) == 126
    return payload


def make_page(item, key):
    template = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__NAME__역 하루 전체 광역버스 승차 변화</title>
<style>*{box-sizing:border-box}body{margin:0;color:#111;background:white;font-family:Arial,'Apple SD Gothic Neo',sans-serif;font-weight:700}
.head{padding:12px 16px 5px;font-size:23px}.toolbar{padding:6px 16px 10px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
button{font-size:15px;padding:6px 11px;cursor:pointer;background:white;border:1px solid #888;border-radius:4px;font-weight:700}
#frame{height:calc(100vh - 180px);min-height:480px;position:relative}#map{height:100%;width:100%;background:#eee}
#status{position:absolute;top:12px;left:12px;background:white;padding:8px 12px;z-index:20;font-size:14px}
.legend{padding:10px 16px;display:flex;flex-wrap:wrap;gap:14px 24px;align-items:center;font-size:17px}.item{display:inline-flex;gap:8px;align-items:center}
.highlight-swatch{display:inline-block;width:22px;height:23px;border:4px solid __HIGHLIGHT_COLOR__;box-shadow:0 0 0 2px #111;background:#D73027;margin:2px}
.swatch{width:19px;height:23px;border:1px solid #555;display:inline-block}.station-star{font-size:37px;color:#00865A;line-height:1;text-shadow:-1px -1px white,1px -1px white,-1px 1px white,1px 1px white}
.green{color:#00865A;font-size:25px}.info{padding:10px 13px;white-space:nowrap;font-size:14px;line-height:1.7;font-weight:700}
.note{padding:0 16px 10px;color:#444;font-size:13px}#view-label{font-size:14px;color:#444}
body.capture .head,body.capture .toolbar,body.capture .legend,body.capture .note{display:none}
body.capture #frame{height:100vh;min-height:0}
</style></head><body>
<div class="head">__NAME__역 권역 · 하루 전체 광역버스 승차 변화</div>
<div class="toolbar"><button onclick="chooseView('all')">전체 격자 보기</button><button onclick="chooseView('focus')">주요지역 확대</button>
<button onclick="toggleCapture()">지도만 보기 (C)</button><span id="view-label">전체 격자 · __COUNT__개 · 강조 __HIGHLIGHT_COUNT__개</span></div>
<div id="frame"><div id="map"></div><div id="status">카카오맵 불러오는 중…</div></div>
<div class="legend"><span class="item"><i class="swatch" style="background:#D73027"></i>감소</span><span class="item"><i class="swatch" style="background:#EEEEEE"></i>유지</span><span class="item"><i class="swatch" style="background:#2166AC"></i>증가</span><span class="item"><i class="highlight-swatch"></i>40건 이상 감소 (변화량 ≤ −40건)</span><span class="item"><i class="green">★</i>GTX-A역</span></div>
<div class="note">2025.11.06 − 2024.10.17 · 250 m 격자 · 지도 이동·확대 가능 · C로 제목·버튼·범례 숨기기/복원 · 카카오 출처 표시는 유지</div>
<script>
const data=__DATA__;let map=null,info=null;
function fail(msg){const s=document.getElementById('status');s.textContent=msg;s.style.display='block';s.style.color='#A22';}
function chooseView(view){if(!map)return;const b=data.bounds[view];map.setBounds(new kakao.maps.LatLngBounds(new kakao.maps.LatLng(b[1],b[0]),new kakao.maps.LatLng(b[3],b[2])),30,30,30,30);document.getElementById('view-label').textContent=(view==='all'?'전체 격자 · '+data.count+'개':'주요지역 확대 · 화면 밖에도 분석 격자 있음')+' · 권역 내 강조 '+data.highlightCount+'개';if(info)info.close();}
function toggleCapture(){if(!map)return;const center=map.getCenter(),level=map.getLevel();document.body.classList.toggle('capture');info.close();requestAnimationFrame(()=>{map.relayout();map.setLevel(level);map.setCenter(center);});}
window.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='c'&&!e.ctrlKey&&!e.metaKey&&!e.altKey)toggleCapture();});
function initMap(){
 if(!window.kakao||!kakao.maps){fail('카카오 지도 SDK 연결을 확인해 주세요.');return;}
 map=new kakao.maps.Map(document.getElementById('map'),{center:new kakao.maps.LatLng(data.point[0],data.point[1]),level:6,draggable:true});
 info=new kakao.maps.InfoWindow({removable:true});
 for(const cell of data.features)for(const rings of cell.paths){
  const path=rings.map(ring=>ring.map(p=>new kakao.maps.LatLng(p[1],p[0])));
  const polygon=new kakao.maps.Polygon({map,path,strokeColor:'#333333',strokeWeight:1,strokeOpacity:1,fillColor:cell.color,fillOpacity:.77,zIndex:4});
  const shapes=[polygon];
  if(cell.highlight){
   // 원본 경계에 검은 바깥선과 청록 안쪽선을 겹친다. 위치와 내부 색은 유지한다.
   shapes.push(new kakao.maps.Polygon({map,path,strokeColor:'#111111',strokeWeight:8,strokeOpacity:1,fillOpacity:0,zIndex:5}));
   shapes.push(new kakao.maps.Polygon({map,path,strokeColor:'__HIGHLIGHT_COLOR__',strokeWeight:4.5,strokeOpacity:1,fillOpacity:0,zIndex:6}));
  }
  for(const shape of shapes)kakao.maps.event.addListener(shape,'click',event=>{info.setContent('<div class="info"><b>격자 '+cell.id+'</b><br>2024년 '+cell.before+'건 → 2025년 '+cell.after+'건<br>변화량 '+(cell.change>0?'+':'')+cell.change+'건'+(cell.highlight?'<br>40건 이상 감소':'')+'</div>');info.setPosition(event.latLng);info.open(map);});
 }
 new kakao.maps.CustomOverlay({map,position:new kakao.maps.LatLng(data.point[0],data.point[1]),content:'<span class="station-star" title="GTX-A '+data.station+'역">★</span>',xAnchor:.5,yAnchor:.5,zIndex:8});
 kakao.maps.event.addListener(map,'tilesloaded',()=>{document.getElementById('status').style.display='none';});
 map.setZoomable(true);chooseView('all');
}
window.addEventListener('resize',()=>{if(map){const center=map.getCenter();map.relayout();map.setCenter(center);}});
</script>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false" onload="kakao.maps.load(initMap)" onerror="fail('카카오 SDK 연결 실패: JavaScript 키와 카카오 앱 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인에 '+location.origin+' 이 등록되어 있는지 확인해 주세요.')"></script>
</body></html>'''
    return (template.replace('__NAME__',html.escape(item['station']))
            .replace('__COUNT__',str(item['count']))
            .replace('__HIGHLIGHT_COUNT__',str(item['highlightCount']))
            .replace('__HIGHLIGHT_COLOR__',HIGHLIGHT_COLOR)
            .replace('__DATA__',json.dumps(item,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
            .replace('__KEY__',quote(key,safe='')))


def _start_available_server(backend, grid, coordinates, key):
    """다른 커널이 포트를 사용 중이면 다음 포트를 사용하며 프로세스를 종료하지 않는다."""
    original_port = backend.PORT
    candidates = list(dict.fromkeys([original_port, *range(8766, 8796)]))
    for port in candidates:
        backend.PORT = port
        try:
            backend.show_kakao_overlay(grid, coordinates, None, key, count_basis=True,
                                       view_id=VIEW_ID, display_maps=False, classification='direction')
        except RuntimeError as exc:
            cause = exc.__cause__
            if isinstance(cause, OSError) and cause.errno == errno.EADDRINUSE:
                continue
            backend.PORT = original_port
            raise
        if port != original_port:
            print(f'{original_port} 포트가 사용 중이어서 http://localhost:{port} 에 지도를 열었습니다.')
            print(f'지도가 비어 있으면 카카오 앱 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인에 http://localhost:{port} 을 추가해 주세요.')
        return port
    backend.PORT = original_port
    raise RuntimeError('8766~8795 포트가 모두 사용 중입니다. 기존 지도 커널의 서버 상태를 확인해 주세요.')


def show_maps(grid, stations, root, key):
    """기존 지도 서버를 재사용하거나 빈 포트에서 연다. 키·HTML·이미지를 파일에 쓰지 않는다."""
    from IPython.display import HTML, IFrame, display
    if not key.strip(): raise ValueError('카카오 JavaScript 키를 입력해 주세요.')
    backend = sys.modules.get('kakao_grid_overlay')
    if backend is None:
        path = Path(root)/'code/03_eda/kakao_grid_overlay.py'
        backend = types.ModuleType('kakao_grid_overlay'); backend.__file__ = str(path)
        exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),backend.__dict__)
        sys.modules['kakao_grid_overlay'] = backend
    geographic_stations = stations.to_crs(4326).set_index('역명')
    coordinates = {name:(geographic_stations.loc[name].geometry.y,geographic_stations.loc[name].geometry.x) for name in ORDER}
    _start_available_server(backend, grid, coordinates, key)
    payload = make_payload(grid, stations)
    backend._pages[VIEW_ID] = {name:make_page(item,key) for name,item in payload.items()}
    urls = {name:f'http://localhost:{backend.PORT}/map?station={quote(name)}&view={VIEW_ID}&v={time.time_ns()}' for name in ORDER}
    for name,url in urls.items():
        display(HTML(f'<p><b>{name}역 권역</b> · <a href="{html.escape(url)}" target="_blank" rel="noopener">새 탭에서 크게 열기 · 스크린샷</a></p>'))
        display(IFrame(url,width='100%',height=820))
    return urls
