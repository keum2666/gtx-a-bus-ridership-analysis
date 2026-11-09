"""015 설명용 카카오 지도. 공개 정류장·격자 자료만 사용하며 지도 파일은 저장하지 않는다."""
from collections import Counter
import html
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import types
from urllib.parse import quote

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box

VIEW_ID = 'explanation_cases_015'
STOP_CASES = [
    (13084, '한울마을2단지', '4104705', '31684', '4104706', '31689', 99, 68.8),
    (10778, '새암공원', '4104784', '31628', '4104783', '31626', 2, 107.6),
]
RAIL_CASES = [(44, '마두1동행정복지센터', '백마', 443.4),
              (2477, '행신SK뷰아파트', '행신', 717.6),
              (10682, '서정마을입구', '강매', 493.8)]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize(values):
    return values.astype(str).str.replace('.0', '', regex=False).str.lstrip('0')


def _point_latlon(point):
    p = gpd.GeoSeries([point], crs=5179).to_crs(4326).iloc[0]
    return [float(p.y), float(p.x)]


def _bounds(geometries, padding):
    region = gpd.GeoSeries(geometries, crs=5179)
    x0, y0, x1, y1 = region.total_bounds
    extent = box(x0-padding, y0-padding, x1+padding, y1+padding)
    assert region.covered_by(extent).all(), '표시 범위에서 실제 지물이 빠졌습니다.'
    return [float(v) for v in gpd.GeoSeries([extent], crs=5179).to_crs(4326).total_bounds]


def _grid_paths(geometry):
    geo = gpd.GeoSeries([geometry], crs=5179).to_crs(4326).iloc[0].__geo_interface__
    return [geo['coordinates']] if geo['type'] == 'Polygon' else geo['coordinates']


def _cache_stops(root, old):
    """카드 ID와 GBIS nodeid를 혼동하지 않고, ARS로 공개 캐시의 좌표를 연결한다."""
    wanted = {ars for case in STOP_CASES for ars in (case[3], case[5])}
    candidates = {ars: Counter() for ars in wanted}
    for path in sorted((root / 'data/raw/common/api_cache_gtx_a_routes').glob('getRouteAcctoThrghSttnList_*.json')):
        cache = json.loads(path.read_text(encoding='utf-8'))
        records = cache.get('response', {}).get('body', {}).get('items', {})
        records = records.get('item', []) if isinstance(records, dict) else []
        records = [records] if isinstance(records, dict) else records
        for row in records:
            ars = str(row.get('nodeno', '')).replace('.0', '').lstrip('0')
            if ars in wanted:
                # 같은 ARS에 캐시가 여러 개이면 실제 최빈 좌표를 사용한다.
                candidates[ars][(float(row['gpslati']), float(row['gpslong']),
                                  str(row['nodenm']), str(row['nodeid']))] += 1
    result = {}
    for _, _, a, ars_a, b, ars_b, _, _ in STOP_CASES:
        for card_id, ars in [(a, ars_a), (b, ars_b)]:
            assert candidates[ars], f'공개 API 캐시에 ARS {ars}가 없습니다.'
            row = old[old.card_id.eq(card_id)]
            assert not row.empty and row.ars.eq(ars).all(), '카드 ID와 ARS 연결 불일치'
            lat, lon, name, node_id = candidates[ars].most_common(1)[0][0]
            assert node_id != card_id and 37 < lat < 38 and 126 < lon < 128
            point = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(5179).iloc[0]
            result[card_id] = {'id': card_id, 'ars': ars, 'name': name,
                               'position': [lat, lon], 'point': point}
    return result


def load_explanation_data(root):
    """원자료 재집계 + 기존 126개 격자 전수 일치 확인. 원본 결과를 수정하지 않는다."""
    root = Path(root)
    day = _module('_explanation_day_015', root / 'code/03_eda/kakao_day_capture_015.py')
    grid, stations, _ = day.load_map_data(root)
    indexed = grid.set_index('셀 ID')
    reference = pd.read_csv(root / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv').set_index('셀 ID')
    cells = pd.read_csv(root / 'data/processed/gtx_a/16_새데이터_공급구조유지_250m격자.csv', dtype=str)
    stops_dir = root / 'data/processed/gtx_a/feeder_bus/stops'
    old = pd.read_csv(stops_dir / 'BusStop_20251106_파주고양서울일부.csv', dtype=str)
    new = pd.read_csv(stops_dir / '2025_신설정류장_좌표_GBIS.csv', dtype=str)
    old['card_id'], old['ars'] = _normalize(old.sttn_id), _normalize(old.sttn_ars_no)
    names = pd.concat([pd.Series(new['정류장명'].values, index=_normalize(new['정류장 ID'])),
                       pd.Series(old.sttn_nm.values, index=old.card_id)])
    names = names[~names.index.duplicated()]
    station_stops = set(names[names.str.contains('운정중앙역|킨텍스역|대곡역', na=False)].index)
    unjeong_stops = set(names[names.str.contains('운정중앙역', na=False)].index)
    lookup = pd.DataFrame([(int(row['셀 ID']), sid.lstrip('0')) for _, row in cells.iterrows()
                           for sid in re.findall(r'\d{6,}', row['2025년 정류장 ID'])],
                          columns=['셀 ID', 'on'])
    assert not lookup.on.duplicated().any()
    files = sorted(p for p in (root / 'data/raw/gtx_a/feeder_bus/transport_card').glob('경기_20251106_*.csv')
                   if p.stat().st_size > 10)
    assert files, '2025.11.06 교통카드 원자료를 찾을 수 없습니다.'
    raw = pd.concat([pd.read_csv(p, dtype=str, usecols=['opr_ymd', 'rte_id', 'ride_sttn_id', 'goff_sttn_id'])
                     for p in files], ignore_index=True)
    assert raw.opr_ymd.eq('20251106').all()
    raw['on'], raw['off'] = _normalize(raw.ride_sttn_id), _normalize(raw.goff_sttn_id)
    records = raw[raw.off.isin(station_stops) & ~raw.on.isin(station_stops)]
    selected = records.merge(lookup, on='on', how='inner', validate='many_to_one')
    counts = selected.groupby('셀 ID').size().reindex(indexed.index, fill_value=0)
    assert len(indexed) == 126 and int(counts.sum()) == 1015
    np.testing.assert_array_equal(counts, reference.loc[indexed.index, 'GTX역행 2025'])
    public_stops = _cache_stops(root, old)
    expected_values = {13084:(129,87,0,15.39), 10778:(436,374,0,31.3716666667),
                       44:(104,91,1,51.65), 2477:(50,34,4,36.3083333333),
                       10682:(11,5,0,45.3783333333)}

    def common(cell_id, title):
        row = indexed.loc[cell_id]
        before, after, feeder, walk = expected_values[cell_id]
        assert (int(row.board_2024), int(row.board_2025), int(counts.loc[cell_id])) == (before, after, feeder)
        assert abs(float(row.walk_min)-walk) < .001
        return {'id':cell_id, 'title':title, 'paths':_grid_paths(row.geometry),
                'center':_point_latlon(row.geometry.centroid), 'before':before,
                'after':after, 'change':after-before, 'feeder':feeder, 'walk':float(row.walk_min)}

    stop_cases = []
    for cell_id, title, a_id, _, b_id, _, expected_b, expected_distance in STOP_CASES:
        item = common(cell_id, title)
        geometry = indexed.loc[cell_id].geometry
        a, b = public_stops[a_id], public_stops[b_id]
        assert lookup.loc[lookup.on.eq(a_id), '셀 ID'].tolist() == [cell_id]
        assert b_id not in set(lookup.on)
        assert geometry.covers(a['point'])
        b_inside = geometry.covers(b['point'])
        assert b_inside == (cell_id == 10778)
        distance = a['point'].distance(b['point'])
        assert abs(distance-expected_distance) < .15
        b_boundary_distance = b['point'].distance(geometry)
        if cell_id == 13084:
            assert abs(b_boundary_distance-36.2) < .15
        item.update({'distance':round(distance,1), 'bInside':bool(b_inside),
                     'bBoundaryDistance':round(b_boundary_distance,1),
                     'bounds':{'focus':_bounds([geometry,a['point'],b['point']],75)}})
        for label, stop in [('a',a),('b',b)]:
            all_count = int(records.on.eq(stop['id']).sum())
            unjeong_count = int((records.on.eq(stop['id']) & records.off.isin(unjeong_stops)).sum())
            assert all_count == unjeong_count == (0 if label == 'a' else expected_b)
            item[label] = {k:v for k,v in stop.items() if k != 'point'}
            item[label]['count'] = unjeong_count
        item['explanation'] = ('B는 선택격자 밖의 인근 정류장입니다. 선택격자 경계에서 '
                               f'{item["bBoundaryDistance"]:.1f} m 떨어져 있습니다.' if not b_inside else
                               'B도 같은 선택격자 안에 있지만, 선정 광역버스 정류장 ID 목록에 없어 원래 연계 집계에서 제외됩니다.')
        stop_cases.append(item)

    railway = pd.read_csv(root / 'data/processed/gtx_a/feeder_bus/support/feature_expansion/S5_osm_철도역목록.csv')
    railway = gpd.GeoDataFrame(railway, geometry=gpd.points_from_xy(railway.x, railway.y), crs=5179)
    gtx = stations.loc[stations['역명'].eq('대곡')].geometry.iloc[0]
    rail_cases = []
    for cell_id, title, name, expected_distance in RAIL_CASES:
        item = common(cell_id, title)
        geometry = indexed.loc[cell_id].geometry
        center = geometry.centroid
        candidates = railway[railway.name.astype(str).str.replace('역','',regex=False).eq(name)].copy()
        assert not candidates.empty
        closest = candidates.loc[candidates.geometry.distance(center).idxmin()]
        distance = float(center.distance(closest.geometry))
        assert abs(distance-expected_distance) < .15
        item.update({'rail':{'name':name+'역','position':_point_latlon(closest.geometry)},
                     'gtx':{'name':'GTX-A 대곡역','position':_point_latlon(gtx)},
                     'distance':round(distance,1),
                     'bounds':{'focus':_bounds([geometry,closest.geometry],125),
                               'all':_bounds([geometry,closest.geometry,gtx],200)}})
        rail_cases.append(item)
    payload = {'stops':stop_cases, 'rail':rail_cases}
    validation = {'원래 연계 집계':int(counts.sum()), '전수 일치 격자':len(counts),
                  '정류장 사례':len(stop_cases), '철도역 사례':len(rail_cases),
                  '정류장 A↔B 직선거리(m)':[v['distance'] for v in stop_cases],
                  'B의 운정중앙역 하차기록(건)':[v['b']['count'] for v in stop_cases],
                  '격자 중심→기존역 직선거리(m)':[v['distance'] for v in rail_cases]}
    return grid, stations, payload, validation


def make_page(kind, items, key):
    if kind not in ('stops', 'rail'):
        raise ValueError('지도 종류는 stops 또는 rail입니다.')
    template = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>*{box-sizing:border-box}body{margin:0;background:white;color:#17202b;font-family:Arial,'Apple SD Gothic Neo',sans-serif;font-weight:700}
.head{padding:13px 18px 5px;font-size:24px}.toolbar{padding:7px 18px 10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
button{padding:8px 12px;background:white;border:1px solid #9aa6b3;border-radius:6px;font-size:15px;font-weight:700;cursor:pointer}button.active{background:#193c65;color:white;border-color:#193c65}
#frame{position:relative;height:calc(100vh - 170px);min-height:560px}#map{width:100%;height:100%;background:#eee}
#card{position:absolute;top:15px;right:15px;width:360px;max-width:43%;z-index:20;background:rgba(255,255,255,.97);border:1px solid #cbd3db;border-radius:9px;box-shadow:0 2px 8px #0002;padding:14px 16px;font-size:18px;line-height:1.5;pointer-events:none}
#card h2{font-size:22px;margin:0 0 10px}#card .metric{font-size:20px;margin:8px 0}#card .explain{margin-top:10px;padding-top:10px;border-top:1px solid #dde2e7;color:#25384b}#card .mini-legend{margin-top:10px;padding-top:9px;border-top:1px solid #dde2e7;font-size:16px;line-height:1.7}
#status{position:absolute;left:12px;top:12px;background:white;padding:9px 12px;z-index:30;font-size:14px;max-width:70%}
.legend{padding:10px 18px 5px;font-size:15px;display:flex;flex-wrap:wrap;gap:8px 20px}.note{padding:4px 18px 10px;font-size:12px;color:#53606d}
.grid-key{display:inline-block;width:18px;height:18px;border:3px solid #c13228;background:#fbe8e4;vertical-align:middle;margin-right:6px}
.dot{display:inline-block;width:17px;height:17px;border:2px solid white;box-shadow:0 0 0 1px #777;border-radius:50%;vertical-align:middle;margin-right:5px}.blue{background:#185da7}.orange{background:#bd4f0d}.green{color:#008458}
.pin{position:relative;width:22px;height:22px;border-radius:50%;border:3px solid white;box-shadow:0 1px 5px #0007;color:white;text-align:center;font:bold 13px/16px Arial}
.pin.blue{background:#185da7}.pin.orange{background:#bd4f0d}.pin.rail{background:#57469b}.pin.center{width:13px;height:13px;background:#555;border-width:2px}
.pin .label{position:absolute;background:white;border:2px solid currentColor;box-shadow:0 2px 4px #0002;border-radius:6px;padding:6px 9px;font-size:18px;line-height:1.45;white-space:nowrap;text-align:left;color:#17202b}
.pin .label.left{right:22px;bottom:14px}.pin .label.right{left:22px;top:14px}.pin .label small{font-size:15px;font-weight:700}
.star{position:relative;color:#008458;font-size:35px;line-height:1;text-shadow:-2px -2px white,2px -2px white,-2px 2px white,2px 2px white}.star span{position:absolute;left:35px;top:2px;white-space:nowrap;background:white;border:1px solid #008458;border-radius:4px;padding:4px 7px;font-size:15px;color:#006344}
#distance-label{position:absolute;left:20px;bottom:48px;z-index:20;background:white;border:1px solid #727b87;border-radius:5px;padding:8px 12px;font-size:19px;white-space:nowrap;pointer-events:none}
body.capture .head,body.capture .toolbar,body.capture .legend,body.capture .note{display:none}body.capture #frame{height:100vh;min-height:0}
@media(max-width:750px){#card{font-size:12px;width:255px;padding:9px;max-width:40%}#card h2{font-size:15px}#card .metric{font-size:13px}.pin .label{font-size:13px}}
</style></head><body>
<div class="head">__TITLE__</div><div class="toolbar" id="toolbar"><span id="case-buttons"></span>
<button onclick="fitView('focus')">선택격자 확대</button><button id="all-button" onclick="fitView('all')">대곡역까지 함께 보기</button>
<button onclick="toggleCapture()">지도만 보기 (C)</button></div>
<div id="frame"><div id="map"></div><div id="status">카카오맵 불러오는 중…</div><div id="card"></div><div id="distance-label"></div></div>
<div class="legend" id="legend"></div><div class="note">원래 126개 격자 · 연계 1,015건 기준 · 2025.11.06 하루 전체 교통카드 기록 · C로 바깥 제목·범례·버튼 숨기기/복원 · 카카오 출처 유지</div>
<script>
const kind=__KIND__,cases=__DATA__;let map=null,current=0,shapes=[],view='focus';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function fail(message){const el=document.getElementById('status');el.textContent=message;el.style.display='block';el.style.color='#a22';}
function ll(p){return new kakao.maps.LatLng(p[0],p[1]);}
function overlay(p,content,z=8){const o=new kakao.maps.CustomOverlay({map,position:ll(p),content,xAnchor:.5,yAnchor:.5,zIndex:z});shapes.push(o);}
function pin(p,css,label,side){overlay(p,'<div class="pin '+css+'"><div class="label '+side+'">'+label+'</div></div>',10);}
function fitView(next){if(!map)return;view=next;const b=cases[current].bounds[next]||cases[current].bounds.focus,width=document.getElementById('map').clientWidth||1200,cardWidth=document.getElementById('card').offsetWidth||360;const left=Math.min(205,width*.20),right=Math.min(cardWidth+200,width*.53);map.setBounds(new kakao.maps.LatLngBounds(new kakao.maps.LatLng(b[1],b[0]),new kakao.maps.LatLng(b[3],b[2])),70,right,90,left);}
function line(a,b,color){const shape=new kakao.maps.Polyline({map,path:[ll(a),ll(b)],strokeWeight:3,strokeColor:color,strokeOpacity:1,strokeStyle:'shortdash',zIndex:6});shapes.push(shape);}
function chooseCase(index){
 current=index;shapes.forEach(o=>o.setMap(null));shapes=[];const c=cases[index];
 document.querySelectorAll('[data-case]').forEach((b,i)=>b.classList.toggle('active',i===index));
 for(const rings of c.paths){shapes.push(new kakao.maps.Polygon({map,path:rings.map(r=>r.map(p=>new kakao.maps.LatLng(p[1],p[0]))),strokeWeight:4,strokeColor:'#c13228',strokeOpacity:1,fillColor:'#ef8479',fillOpacity:.14,zIndex:4}));}
 const common='<h2>'+esc(c.title)+'<br>선택격자 '+c.id+'</h2><div class="metric">광역 '+c.before+' → '+c.after+'건 ('+c.change+'건)<br>이 격자 GTX역행 '+c.feeder+'건</div><div>GTX역 보행시간 '+c.walk.toFixed(2)+'분</div>';
 if(kind==='stops'){
  line(c.a.position,c.b.position,'#626b78');
  pin(c.a.position,'blue','<b>A · 집계 포함 '+c.a.count+'건</b><br><small>ARS '+esc(c.a.ars)+'</small>','left');
  pin(c.b.position,'orange','<b>B · 비교 '+c.b.count+'건</b><br><small>ARS '+esc(c.b.ars)+'</small>','right');
  document.getElementById('distance-label').textContent='A↔B 직선 '+c.distance.toFixed(1)+' m';
  document.getElementById('card').innerHTML=common+'<div class="explain">'+(c.bInside?'<b>같은 선택격자 안의 B: '+c.b.count+'건</b><br>선정 정류장 ID에 없어 집계 제외':'<b>격자 밖 인근 B: '+c.b.count+'건</b><br>선택격자 경계에서 '+c.bBoundaryDistance.toFixed(1)+' m 밖')+'<br>A↔B 직선 '+c.distance.toFixed(1)+' m</div><div class="explain">집계 0건 ≠ 주변 이용 0건<br><small>건수: 운정중앙역 하차기록</small></div><div class="mini-legend"><i class="grid-key"></i>선택격자<br><i class="dot blue"></i>A 집계 포함 · <i class="dot orange"></i>B 집계 제외</div>';
 }else{
  line(c.center,c.rail.position,'#57469b');
  document.getElementById('distance-label').textContent='격자 중심 → '+c.rail.name+' 직선 '+c.distance.toFixed(1)+' m';
  pin(c.center,'center','<small>선택격자 '+c.id+' 중심</small>','left');
  pin(c.rail.position,'rail','<b>'+esc(c.rail.name)+'</b><br><small>격자 중심에서 직선 '+c.distance.toFixed(1)+' m</small>','right');
  overlay(c.gtx.position,'<div class="star">★<span>'+esc(c.gtx.name)+'</span></div>',11);
  document.getElementById('card').innerHTML=common+'<div class="explain"><b>'+esc(c.rail.name)+' 직선 '+c.distance.toFixed(1)+' m</b><br>격자 중심 → 기존 철도역</div><div class="explain">다른 철도역 접근 가능성<br><small>실제 이용·수단전환 확인 아님</small></div><div class="mini-legend"><i class="grid-key"></i>선택격자 · ● 기존역<br><span class="green">★ GTX-A 대곡역</span><br>점선: 직선거리 · 이동 경로 아님</div>';
 }
 fitView('focus');
}
function toggleCapture(){if(!map)return;const center=map.getCenter(),level=map.getLevel();document.body.classList.toggle('capture');requestAnimationFrame(()=>{map.relayout();map.setLevel(level);map.setCenter(center);});}
window.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='c'&&!e.ctrlKey&&!e.metaKey&&!e.altKey)toggleCapture();});
window.addEventListener('resize',()=>{if(map){const c=map.getCenter();map.relayout();map.setCenter(c);}});
function initMap(){
 if(!window.kakao||!kakao.maps){fail('카카오 SDK 연결을 확인해 주세요.');return;}
 map=new kakao.maps.Map(document.getElementById('map'),{center:ll(cases[0].center),level:3,draggable:true});
 document.getElementById('case-buttons').innerHTML=cases.map((c,i)=>'<button data-case="'+i+'" onclick="chooseCase('+i+')">'+c.id+' · '+esc(c.title)+'</button>').join(' ');
 document.getElementById('all-button').style.display=kind==='rail'?'inline-block':'none';
 document.getElementById('legend').innerHTML='<span><i class="grid-key"></i>선택한 실제 250 m 격자</span>'+(kind==='stops'?'<span><i class="dot blue"></i>A 집계 포함</span><span><i class="dot orange"></i>B 집계 제외 비교</span><span>점선: 정류장 사이 직선</span>':'<span>● 기존 철도역</span><span class="green">★ GTX-A 대곡역</span><span>점선: 격자 중심→기존역 직선</span>');
 kakao.maps.event.addListener(map,'tilesloaded',()=>{document.getElementById('status').style.display='none';});
 map.setZoomable(true);chooseCase(0);
}
</script>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false" onload="kakao.maps.load(initMap)" onerror="fail('카카오 SDK 연결 실패: 카카오 앱 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인에 '+location.origin+' 을 등록하고 키·인터넷 연결을 확인해 주세요.')"></script>
</body></html>'''
    title = '정류장 집계 범위에 따른 0건' if kind == 'stops' else '기존 철도역 접근 가능성 · 대곡권역'
    return (template.replace('__TITLE__',title).replace('__KIND__',json.dumps(kind))
            .replace('__DATA__',json.dumps(items, ensure_ascii=False, separators=(',',':')).replace('<','\\u003c'))
            .replace('__KEY__',quote(key,safe='')))


def show_explanation_maps(grid, stations, payload, root, key):
    """두 설명 지도를 한 키로 메모리 서버에 등록한다. 기존 지도 페이지는 보존한다."""
    from IPython.display import HTML, IFrame, display
    if not key.strip():
        raise ValueError('카카오 JavaScript 키를 입력해 주세요.')
    backend = sys.modules.get('kakao_grid_overlay')
    if backend is None:
        path = Path(root) / 'code/03_eda/kakao_grid_overlay.py'
        backend = types.ModuleType('kakao_grid_overlay')
        backend.__file__ = str(path)
        exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),backend.__dict__)
        sys.modules['kakao_grid_overlay'] = backend
    if getattr(backend, '_server', None) is not None:
        port = backend._server.server_address[1]
    else:
        day = _module('_explanation_server_015', Path(root) / 'code/03_eda/kakao_day_capture_015.py')
        geo = stations.to_crs(4326).set_index('역명')
        coords = {name:(geo.loc[name].geometry.y,geo.loc[name].geometry.x) for name in day.ORDER}
        sentinel = object()
        original = backend._pages.get(day.VIEW_ID, sentinel)
        try:
            port = day._start_available_server(backend,grid,coords,key)
        finally:
            # 서버를 시작하는 helper가 임시 생성한 day_capture 페이지를 보존/정리한다.
            if original is sentinel:
                backend._pages.pop(day.VIEW_ID,None)
            else:
                backend._pages[day.VIEW_ID] = original
    backend._pages[VIEW_ID] = {kind:make_page(kind,items,key) for kind,items in payload.items()}
    origin = f'http://localhost:{port}'
    print(f'카카오 앱 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인: {origin}')
    print('새 탭의 실제 location.origin이 위 주소와 일치하는지 확인하세요. C: 바깥 제목·범례·버튼 숨기기/복원.')
    urls = {kind:f'{origin}/map?station={kind}&view={VIEW_ID}&v={time.time_ns()}' for kind in payload}
    for kind,url in urls.items():
        title = '정류장 집계 범위에 따른 0건 · 2사례' if kind == 'stops' else '기존 철도역 접근 가능성 · 3사례'
        display(HTML(f'<p><b>{title}</b> · <a href="{html.escape(url)}" target="_blank" rel="noopener">새 탭에서 크게 열기 · 사례 버튼으로 전환 후 캡처</a></p>'))
        display(IFrame(url,width='100%',height=850))
    return urls
