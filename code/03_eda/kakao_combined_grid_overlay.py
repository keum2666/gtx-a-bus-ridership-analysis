"""011의 종일·출근시간대 통합 카카오맵. 원자료를 재집계하고 기존 지도 서버를 공유한다."""
from pathlib import Path
import html
import importlib.util
import json
import sys
import time
import types
from urllib.parse import quote

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box
from IPython.display import HTML, IFrame, display

ORDER = ['운정중앙', '킨텍스', '대곡']
COLORS = {-1:'#D73027', 0:'#EEEEEE', 1:'#2166AC'}
VIEW_ID = 'combined_day_morning_count'


def load_combined_grid(root):
    """앞선 노트북 셀 실행 없이 종일·출근 건수를 같은 126개 격자에 연결한다."""
    import re
    root = Path(root)
    base = pd.read_csv(root/'data/final/gtx_a/S1_126격자_건수기준_기초표.csv', encoding='utf-8-sig').set_index('셀 ID')
    stops = pd.read_csv(root/'data/processed/gtx_a/16_새데이터_공급구조유지_250m격자.csv', dtype=str, encoding='utf-8-sig')
    assert len(base)==126 and base.index.is_unique
    assert set(base.index)==set(stops['셀 ID'].astype(int))
    counts = base[['nearest_station','board_2024','board_2025']].copy()
    for year,date,filename in [
        (2024,'20241017','gtx_a_transport_card_20241017_raw_with_coords_api_filled.csv'),
        (2025,'20251106','gtx_a_transport_card_20251106_raw_with_coords.csv')]:
        raw = pd.read_csv(root/'data/raw/gtx_a/transport_card'/filename, dtype=str, encoding='utf-8-sig',
                          usecols=['query_date','opr_ymd','승차정류장ID','ride_dt','goff_ctpv_cd'])
        assert raw['query_date'].eq(date).all() and raw['opr_ymd'].eq(date).all()
        lookup = pd.DataFrame([(int(row['셀 ID']),sid) for _,row in stops.iterrows()
                               for sid in re.findall(r'\d{6,}',row[f'{year}년 정류장 ID'])],
                              columns=['셀 ID','승차정류장ID'])
        assert not lookup['승차정류장ID'].duplicated().any()
        selected = raw.merge(lookup,on='승차정류장ID',how='inner',validate='many_to_one')
        assert selected['goff_ctpv_cd'].eq('11').all()
        np.testing.assert_array_equal(selected.groupby('셀 ID').size().reindex(base.index,fill_value=0),base[f'board_{year}'])
        times = pd.to_datetime(selected['ride_dt'],format='%Y%m%d%H%M%S',errors='raise')
        morning = selected.loc[times.dt.hour.ge(6)&times.dt.hour.lt(10)]
        counts[f'morning_{year}'] = morning.groupby('셀 ID').size().reindex(base.index,fill_value=0)
    reference = pd.read_csv(root/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv',encoding='utf-8-sig').set_index('셀 ID')
    np.testing.assert_array_equal(counts.morning_2025-counts.morning_2024,reference.loc[base.index,'Δ광역 출근'])
    grid_path = next((root/'data/raw/common/grid/빈격자(250m)').glob('*.shp'))
    crs = gpd.read_file(grid_path,rows=1).crs
    admin = gpd.read_file(root/'data/raw/common/api_cache_gtx_a_routes/HangJeongDong_ver20260701.geojson').to_crs(crs)
    admin['sgg_code'] = admin['sgg'].astype(str).str.extract(r'([0-9]+)')[0].str.zfill(5)
    city = admin.loc[admin['sgg_code'].str.startswith(('4128','4148'))]
    boundary = city.geometry.union_all() if hasattr(city.geometry,'union_all') else city.geometry.unary_union
    geometry = gpd.read_file(grid_path,bbox=boundary.bounds)
    geometry = geometry.loc[geometry.geometry.intersects(boundary)].copy()
    geometry['_key'] = geometry.geometry.apply(lambda g:g.wkb if g is not None else None)
    geometry = geometry.drop_duplicates('_key').drop(columns='_key').reset_index(drop=True)
    geometry['셀 ID'] = np.arange(1,len(geometry)+1)
    result = geometry[['셀 ID','geometry']].merge(counts.reset_index(),on='셀 ID',how='inner',validate='one_to_one')
    assert len(result)==126 and result['셀 ID'].is_unique
    centers = result.set_index('셀 ID').geometry.centroid.to_crs(4326).reindex(base.index)
    np.testing.assert_allclose(centers.x,base['중심점 경도'],atol=1e-6,rtol=0)
    np.testing.assert_allclose(centers.y,base['중심점 위도'],atol=1e-6,rtol=0)
    result['change'] = result.board_2025-result.board_2024
    result['morning_change'] = result.morning_2025-result.morning_2024
    result['day_sign'] = np.sign(result.change).astype(int)
    result['am_sign'] = np.sign(result.morning_change).astype(int)
    result['different'] = result.day_sign.ne(result.am_sign)
    result['opposite'] = result.day_sign*result.am_sign == -1
    summary = result.groupby('nearest_station').agg(
        격자수=('셀 ID','size'), 변화구분불일치=('different','sum'), 감소증가방향반대=('opposite','sum'))
    summary = summary.reindex(ORDER)
    summary.loc['전체'] = summary.sum()
    return result,summary


def _paths(geometry):
    if geometry.geom_type=='Polygon':
        return [geometry.__geo_interface__['coordinates']]
    if geometry.geom_type=='MultiPolygon':
        return list(geometry.__geo_interface__['coordinates'])
    raise ValueError(f'다각형 경계가 필요합니다: {geometry.geom_type}')


def _static_module(root):
    path=Path(root)/'code/03_eda/kakao_period_compare.py'
    spec=importlib.util.spec_from_file_location('_static_combined_style',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def make_combined_payload(data,root):
    """정적 지도와 같은 투영좌표계에서 격자를 반으로 나눈 다음 지도 좌표로 변환한다."""
    if data.crs is None or not data.crs.is_projected:
        raise ValueError('미터 단위 투영좌표계의 격자가 필요합니다.')
    original=_static_module(root)
    payload={}
    for station in ORDER:
        part=data.loc[data.nearest_station.eq(station)].copy()
        lat,lon=original.STATIONS[station]
        point=gpd.GeoSeries(gpd.points_from_xy([lon],[lat]),crs=4326).to_crs(data.crs).iloc[0]
        x0,y0,x1,y1=part.total_bounds
        px,py=max((x1-x0)*.07,300),max((y1-y0)*.07,300)
        full=[x0-px,y0-py,x1+px,y1+py]
        if station=='운정중앙':main=[point.x-4200,point.y-2700,point.x+4200,point.y+3500]
        elif station=='대곡':main=[point.x-2200,point.y-3700,point.x+3600,point.y+4000]
        else:main=full
        bounds={name:list(map(float,gpd.GeoSeries([box(*b)],crs=data.crs).to_crs(4326).total_bounds))
                for name,b in [('main',main),('all',full)]}
        features=[]
        for _,row in part.iterrows():
            left,bottom,right,top=row.geometry.bounds;middle=(left+right)/2
            halves=[row.geometry.intersection(box(left,bottom,middle,top)),
                    row.geometry.intersection(box(middle,bottom,right,top))]
            assert abs(sum(g.area for g in halves)-row.geometry.area)<1e-4
            assert halves[0].intersection(halves[1]).area<1e-4
            # 두 절반이 실제 격자를 빈틈이나 중복 없이 구성하는지 확인한다.
            assert halves[0].union(halves[1]).symmetric_difference(row.geometry).area<1e-4
            converted=gpd.GeoSeries([*halves,row.geometry],crs=data.crs).to_crs(4326)
            features.append({'id':int(row['셀 ID']),'left':_paths(converted.iloc[0]),
                'right':_paths(converted.iloc[1]),'outline':_paths(converted.iloc[2]),
                'colors':[COLORS[int(row.day_sign)],COLORS[int(row.am_sign)]],
                'different':bool(row['different']),
                'before':[int(row.board_2024),int(row.morning_2024)],
                'after':[int(row.board_2025),int(row.morning_2025)],
                'change':[int(row.change),int(row.morning_change)]})
        payload[station]={'station':station,'point':[lat,lon],'bounds':bounds,
            'hasOverview':station in ['운정중앙','대곡'],'overviewBottom':station=='대곡',
            'defaultView':'main' if station in ['운정중앙','대곡'] else 'all','features':features}
    return payload


def combined_page(item,app_key):
    if not app_key:raise ValueError('카카오 JavaScript 키를 입력해 주세요.')
    template=r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__STATION__ 하루 전체·출근시간대 통합 지도</title>
<style>*{box-sizing:border-box}body{font-family:Arial,'Apple SD Gothic Neo',sans-serif;margin:0;background:white;color:#111;font-weight:700}.head{padding:12px 14px 7px;font-size:21px}.intro{padding:0 14px 10px;font-size:16px}#frame{height:570px;position:relative}#map{height:100%;width:100%;background:#eee}.legend{display:flex;flex-wrap:wrap;gap:12px 22px;padding:12px 14px;font-size:16px}.item{display:inline-flex;align-items:center;gap:7px}.swatch{display:inline-block;width:22px;height:20px;border:1px solid #555}.difference-shadow{display:inline-block;width:22px;height:20px;border:1px solid #444;background:white;box-shadow:6px 8px 6px rgba(0,0,0,.48)}.green{color:#00865A;font-size:24px;line-height:20px}.station-star{font-size:34px;color:#00865A;line-height:1;text-shadow:-1px -1px white,1px -1px white,-1px 1px white,1px 1px white}.station-star.small{font-size:20px}#status{position:absolute;left:10px;top:10px;z-index:20;background:white;padding:7px 12px;font-size:14px}.error{color:#B2182B}.info{padding:10px 13px;white-space:nowrap;font-size:13px;line-height:1.6}.info table{border-collapse:collapse;text-align:right}.info th,.info td{padding:2px 8px}.info th:first-child{text-align:left}@media(max-width:650px){.head{font-size:18px}.intro,.legend{font-size:14px}}
</style></head><body>
<div class="head">__STATION__역 권역 · 광역버스 승차 변화</div>
<div class="intro">격자 왼쪽: 하루 전체　/　격자 오른쪽: 출근시간대</div>

<div id="frame"><div id="map"></div><div id="status">카카오맵을 불러오는 중입니다.</div></div>
<div class="legend"><span class="item"><i class="swatch" style="background:#D73027"></i>감소</span><span class="item"><i class="swatch" style="background:#EEEEEE"></i>유지</span><span class="item"><i class="swatch" style="background:#2166AC"></i>증가</span><span class="item"><i class="difference-shadow"></i>그림자: 하루 전체·출근시간대 변화 구분이 다름</span><span class="item"><i class="green">★</i>GTX역</span></div>
<script>
const data=__DATA__;
let mainMap=null,info=null;
function fail(message){const s=document.getElementById('status');s.textContent=message;s.className='error';s.style.display='block';}
function latlngs(rings){return rings.map(ring=>ring.map(p=>new kakao.maps.LatLng(p[1],p[0])));}
function boundsFor(view){const b=data.bounds[view];return new kakao.maps.LatLngBounds(new kakao.maps.LatLng(b[1],b[0]),new kakao.maps.LatLng(b[3],b[2]));}
function chooseView(view){if(mainMap)mainMap.setBounds(boundsFor(view),25,25,25,25);}
function showInfo(cell,event){const signed=v=>(v>0?'+':'')+v;info.setContent('<div class="info"><b>격자 '+cell.id+'</b><table><tr><th></th><th>2024년</th><th>2025년</th><th>변화량</th></tr><tr><th>하루 전체</th><td>'+cell.before[0]+'건</td><td>'+cell.after[0]+'건</td><td>'+signed(cell.change[0])+'건</td></tr><tr><th>출근시간대</th><td>'+cell.before[1]+'건</td><td>'+cell.after[1]+'건</td><td>'+signed(cell.change[1])+'건</td></tr></table></div>');info.setPosition(event.latLng);info.open(mainMap);}
function drawCells(map,clickable,small){
 const cellShadows=[];
 function shiftedShadowPath(rings,dx,dy){
  const projection=map.getProjection();
  return rings.map(ring=>ring.map(coordinate=>{
   const point=projection.containerPointFromCoords(coordinate);
   return projection.coordsFromContainerPoint(new kakao.maps.Point(point.x+dx,point.y+dy));
  }));
 }
 function updateCellShadows(){
  for(const item of cellShadows)item.shape.setPath(shiftedShadowPath(item.path,item.dx,item.dy));
 }
 for(const cell of data.features){
  if(cell.different){
   // 격자는 실제 위치에 두고 그림자만 화면상 오른쪽 아래로 이동한다.
   for(const polygon of cell.outline){
    const path=latlngs(polygon);
    for(const layer of [{dx:10,dy:14,width:8,opacity:.10},{dx:8,dy:11,width:5,opacity:.16},{dx:6,dy:8,width:2,opacity:.32}]){
     const shape=new kakao.maps.Polygon({map,path:shiftedShadowPath(path,layer.dx,layer.dy),
      strokeColor:'#111111',strokeWeight:layer.width,strokeOpacity:layer.opacity,
      fillColor:'#111111',fillOpacity:layer.opacity,zIndex:1});
     cellShadows.push({shape,path,dx:layer.dx,dy:layer.dy});
    }
   }
  }
  for(const half of ['left','right'])for(const polygon of cell[half]){
   const shape=new kakao.maps.Polygon({map,path:latlngs(polygon),strokeWeight:0,strokeOpacity:0,fillColor:cell.colors[half==='left'?0:1],fillOpacity:cell.different ? .96 : .80,zIndex:2});
   if(clickable)kakao.maps.event.addListener(shape,'click',event=>showInfo(cell,event));
  }
  for(const polygon of cell.outline){
   const border=new kakao.maps.Polygon({map,path:latlngs(polygon),strokeWeight:small ? .5 : 1,strokeColor:'#333333',strokeOpacity:1,fillOpacity:0,zIndex:3});
   if(clickable)kakao.maps.event.addListener(border,'click',event=>showInfo(cell,event));
  }

 }
 kakao.maps.event.addListener(map,'zoom_changed',updateCellShadows);
 kakao.maps.event.addListener(map,'idle',updateCellShadows);
 requestAnimationFrame(updateCellShadows);
 new kakao.maps.CustomOverlay({map,position:new kakao.maps.LatLng(data.point[0],data.point[1]),content:'<span class="station-star'+(small?' small':'')+'" title="GTX '+data.station+'역">★</span>',xAnchor:.5,yAnchor:.5,zIndex:7});
}
function initCombinedMap(){
 if(!window.kakao||!kakao.maps){fail('카카오 지도 SDK를 불러오지 못했습니다. 키와 등록 도메인을 확인해 주세요.');return;}
 mainMap=new kakao.maps.Map(document.getElementById('map'),{center:new kakao.maps.LatLng(data.point[0],data.point[1]),level:6,draggable:true});
 info=new kakao.maps.InfoWindow({removable:true});
 kakao.maps.event.addListener(mainMap,'tilesloaded',()=>{document.getElementById('status').style.display='none';});
 drawCells(mainMap,true,false);
 mainMap.setDraggable(true);mainMap.setZoomable(true);
 chooseView(data.defaultView);
}
window.addEventListener('resize',()=>{if(mainMap)mainMap.relayout();});
</script>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false" onload="kakao.maps.load(initCombinedMap)" onerror="fail('카카오 지도 SDK 연결 실패: JavaScript 키·카카오맵 사용 설정·등록 도메인을 확인해 주세요.')"></script>
</body></html>'''
    data=json.dumps(item,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    return template.replace('__STATION__',html.escape(item['station'])).replace('__DATA__',data).replace('__KEY__',quote(app_key,safe=''))


def capture_combined_page(page):
    page=page.replace('#frame{height:570px;', '#frame{height:calc(100vh - 205px);min-height:500px;')
    page=page.replace('</style>', '''
body.capture .head,body.capture .intro,body.capture .legend,body.capture .context-legend,body.capture .capture-button{display:none}
body.capture #frame{height:100vh;min-height:0}
.capture-button{position:fixed;right:12px;bottom:8px;z-index:30;background:white;border:1px solid #555;border-radius:4px;padding:7px 12px;font-size:14px;cursor:pointer}
</style>''')
    page=page.replace('<script>\nconst data=', '''<button class="capture-button" onclick="toggleCapture()">지도만 보기 (C) · 다시 C로 복원</button>
<script>
function toggleCapture(){
 const center=mainMap?mainMap.getCenter():null;
 document.body.classList.toggle('capture');
 if(info)info.close();
 requestAnimationFrame(()=>{if(mainMap){mainMap.relayout();mainMap.setCenter(center);}});
}
window.addEventListener('keydown',event=>{if(event.key.toLowerCase()==='c'&&!event.ctrlKey&&!event.metaKey)toggleCapture();});
const data=''')
    return page


def show_combined_kakao(data,root,app_key,display_maps=True,include_context=True):
    """기존 011의 localhost:8765 서버에 통합 보기를 추가해 앞선 지도를 유지한다."""
    root=Path(root)
    payload=make_combined_payload(data,root)
    backend=sys.modules.get('kakao_grid_overlay')
    if backend is None:
        path=root/'code/03_eda/kakao_grid_overlay.py'
        backend=types.ModuleType('kakao_grid_overlay');backend.__file__=str(path)
        exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),backend.__dict__)
        sys.modules['kakao_grid_overlay']=backend
    # 기존 서버 생성·재사용 절차를 그대로 사용한다. 숨겨진 종일 페이지도 기존 기준을 유지한다.
    legacy=data.copy()
    edges=tuple(legacy.change.quantile([.25,.5,.75]))
    legacy['변화량 사분위 코드']=np.searchsorted(edges,legacy.change.to_numpy(),side='left')
    backend.show_kakao_overlay(legacy,_static_module(root).STATIONS,edges,app_key,
                              count_basis=True,view_id='count',display_maps=False)
    pages={station:capture_combined_page(combined_page(payload[station],app_key)) for station in ORDER}
    if include_context:
        path=root/'code/03_eda/kakao_map_context.py'
        spec=importlib.util.spec_from_file_location('_combined_map_context',path)
        annotation=importlib.util.module_from_spec(spec);spec.loader.exec_module(annotation)
        cache=root/annotation.CONTEXT_PATH
        # 저장된 실제 경계·철도 자료를 그대로 재사용한다.
        context=json.loads(cache.read_text()) if cache.exists() else annotation.collect_context(root)
        pages={station:annotation.add_context_page(page,
            annotation.select_map_context(context,data.loc[data.nearest_station.eq(station)]))
            for station,page in pages.items()}
    backend._pages[VIEW_ID]=pages
    urls={station:f'http://localhost:{backend.PORT}/map?station={quote(station)}&view={VIEW_ID}&v={time.time_ns()}' for station in ORDER}
    if display_maps:
        for station,url in urls.items():
            display(HTML(f'<p><b>{station}역 통합 지도</b> · <a href="{html.escape(url)}" target="_blank" rel="noopener">새 탭에서 크게 보기·캡처</a></p>'))
            display(IFrame(src=url,width='100%',height=850))
    return urls
