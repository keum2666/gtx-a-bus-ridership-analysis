"""OSM의 실제 부지 경계·철도 노선 경로를 수집하여 카카오맵에 추가한다."""
from pathlib import Path
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CONTEXT_PATH = 'data/processed/gtx_a/map_context/주변시설_철도노선.geojson'


def collect_context(root, refresh=False):
    """인터넷 가능한 로컬 환경에서 최초 한 번 실행. 위치를 추정해서 만들지 않는다."""
    from shapely.geometry import LineString, Polygon, box, mapping
    root = Path(root); target = root/CONTEXT_PATH
    if target.exists() and not refresh:
        return supplement_exhibition_boundaries(root, json.loads(target.read_text()))
    # 세 권역의 실제 분석격자 전체를 포함한다.
    import pandas as pd
    base = pd.read_csv(root/'data/final/gtx_a/S1_126격자_건수기준_기초표.csv', encoding='utf-8-sig')
    west, east = base['중심점 경도'].min()-.015, base['중심점 경도'].max()+.015
    south, north = base['중심점 위도'].min()-.015, base['중심점 위도'].max()+.015
    bbox = f'{south},{west},{north},{east}'
    clip = box(west, south, east, north)
    queries = {
        'areas': f'''[out:json][timeout:75];(
way[landuse=residential][residential=apartments]({bbox});
way[landuse=residential][name~"아파트|[0-9]+단지"]({bbox});
way[name~"킨텍스|KINTEX|고양종합운동장",i]({bbox});
);out geom;''',
        'rail': f'''[out:json][timeout:75];(
relation[route~"^(train|subway)$"][name~"3호선|경의|서해"]({bbox});
);out geom({bbox});'''
    }
    raw = {}; endpoints = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
    for kind, query in queries.items():
        errors = []
        for endpoint in endpoints:
            try:
                url = endpoint+'?'+urllib.parse.urlencode({'data':query})
                req = urllib.request.Request(url, headers={'User-Agent':'UROP-research-map/1.0'})
                with urllib.request.urlopen(req, timeout=90) as response:
                    result = json.load(response)
                if result.get('remark'): raise RuntimeError(result['remark'])
                raw[kind] = result; break
            except Exception as exc:
                errors.append(str(exc))
        else:
            raise RuntimeError('OSM 실제 경계/경로 자료를 받지 못했습니다. 인터넷 연결 후 다시 실행하세요. '+str(errors))
    features = []; seen = set()
    def append(geom, props):
        if geom.is_empty: return
        if props['kind']=='facility':
            point=geom.representative_point();props['label_position']=[point.x,point.y]
        features.append({'type':'Feature','properties':props,'geometry':mapping(geom)})
    for element in raw['areas'].get('elements', []):
        tags = element.get('tags', {}); coords = [(p['lon'],p['lat']) for p in element.get('geometry',[]) if p]
        if len(coords)<4 or coords[0]!=coords[-1]: continue
        name = tags.get('name','')
        facility = any(word in name.upper() for word in ['킨텍스','KINTEX','고양종합운동장'])
        if not facility and tags.get('landuse')!='residential': continue
        geometry = Polygon(coords)
        if not geometry.is_valid: geometry=geometry.buffer(0)
        append(geometry.intersection(clip), {'kind':'facility' if facility else 'apartment',
               'name':name if facility else '', 'osm_id':f'way/{element["id"]}',
               'color':'#D49400' if facility else '#8A48AD'})
    for element in raw['rail'].get('elements', []):
        name = element.get('tags',{}).get('name','')
        if '3호선' in name: line, color = '3호선', '#EF7C1C'
        elif '경의' in name: line, color = '경의중앙선', '#65A98F'
        elif '서해' in name: line, color = '서해선', '#81A914'
        else: continue
        for member in element.get('members', []):
            if member.get('type')!='way' or member.get('role','').startswith('platform'): continue
            coords = member.get('geometry', []); segments=[]; segment=[]
            # bbox 밖의 null 좌표를 가로질러 직선으로 연결하지 않는다.
            for point in coords+[None]:
                if point and 'lon' in point: segment.append((point['lon'],point['lat']))
                else:
                    if len(segment)>1: segments.append(segment)
                    segment=[]
            for segment in segments:
                key=(line,member['ref'],tuple(segment))
                reverse=(line,member['ref'],tuple(reversed(segment)))
                if key in seen or reverse in seen: continue
                seen.add(key)
                append(LineString(segment).intersection(clip), {'kind':'rail','name':line,'color':color,
                       'osm_id':f'way/{member["ref"]}', 'relation_id':element['id']})
    from collections import Counter
    counts = Counter(f['properties']['kind'] for f in features)
    if not counts['rail']: raise RuntimeError('실제 철도 노선 경로가 조회되지 않아 저장하지 않았습니다.')
    result={'type':'FeatureCollection','source':'© OpenStreetMap contributors',
            'collected_at':datetime.now(timezone.utc).isoformat(),
            'note':'현재 OSM의 지도 해석용 자료이며 2024/2025년 시설 현황의 증거가 아님. 아파트명 미표시. 누락 가능.',
            'features':features}
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False))
    (target.parent/'overpass_queries.json').write_text(json.dumps(queries,ensure_ascii=False,indent=2))
    print('실제 경계·경로 수집:',dict(counts))
    print('철도:',sorted({f['properties']['name'] for f in features if f['properties']['kind']=='rail'}))
    return supplement_exhibition_boundaries(root, result)


def nearby_residential_context(context, region, distance_m=350):
    """해당 권역의 분석격자 350m 이내에 있는 주거단지 경계만 선택한다."""
    import geopandas as gpd
    candidates=[f for f in context['features'] if f['properties'].get('kind')=='apartment']
    if not candidates:
        return {'type':'FeatureCollection','features':[]}
    areas=gpd.GeoDataFrame.from_features(candidates,crs=4326).to_crs(region.crs)
    areas=areas.loc[~areas.geometry.is_empty & areas.geometry.notna()].copy()
    areas.geometry=areas.geometry.apply(lambda g:g if g.is_valid else g.buffer(0))
    footprint=region.geometry.union_all() if hasattr(region.geometry,'union_all') else region.geometry.unary_union
    areas=areas.loc[areas.geometry.distance(footprint).le(distance_m)]
    if areas.empty:
        return {'type':'FeatureCollection','features':[]}
    # 맞닿거나 중복된 주거구역의 내부 경계선을 없애 시각적 혼잡을 줄인다.
    merged=areas.geometry.union_all() if hasattr(areas.geometry,'union_all') else areas.geometry.unary_union
    result=gpd.GeoDataFrame({'kind':['apartment']},geometry=[merged],crs=region.crs).to_crs(4326)
    return json.loads(result.to_json())


def add_context_page(page, context):
    """주거단지는 연보라색, 주요 시설과 실제 철도 경로는 카테고리별 색상으로 표시한다. 이름표는 추가하지 않는다."""
    data=json.dumps(context,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    script=r'''
const contextData=__CONTEXT__;
function drawMapContext(){
 for(const f of contextData.features){
  const p=f.properties,g=f.geometry;
  if(p.kind==='rail'){
   const lines=g.type==='LineString'?[g.coordinates]:g.type==='MultiLineString'?g.coordinates:[];
   for(const coords of lines){
    const path=coords.map(c=>new kakao.maps.LatLng(c[1],c[0]));
    new kakao.maps.Polyline({map:mainMap,path,strokeColor:'#FFFFFF',strokeWeight:5,strokeOpacity:.9,zIndex:1});
    new kakao.maps.Polyline({map:mainMap,path,strokeColor:p.color,strokeWeight:3,strokeOpacity:.95,zIndex:1});
   }
   continue;
  }
  const facility=p.kind==='facility';
  const color=facility?(p.category==='stadium'?'#168B83':'#B6A000'):'#C5AFE2';
  const polygons=g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:[];
  for(const polygon of polygons){
   new kakao.maps.Polygon({map:mainMap,path:latlngs(polygon),strokeColor:facility?color:'#B3A0C9',
     strokeWeight:facility?2.4:.8,strokeOpacity:facility ? .95 : .45,
     fillColor:color,fillOpacity:facility ? .22 : .32,zIndex:facility?1:0});
  }
 }
}
'''.replace('__CONTEXT__',data)
    page=page.replace('function initCombinedMap(){',script+'\nfunction initCombinedMap(){')
    page=page.replace('drawCells(mainMap,true,false);','drawMapContext();\n drawCells(mainMap,true,false);')
    legend='''<div class="context-legend" style="padding:0 14px 10px;font-size:14px;color:#555;line-height:1.8">
<span style="background:rgba(197,175,226,.32);padding:1px 6px">주거단지</span>　
<span style="color:#9C8A00">▱ 킨텍스 전시장</span>　<span style="color:#168B83">▱ 종합운동장</span>　
<span style="color:#EF7C1C">━ 3호선</span>　<span style="color:#65A98F">━ 경의중앙선</span>　<span style="color:#81A914">━ 서해선</span>
<span style="font-size:10px">　© OpenStreetMap contributors</span></div>'''
    page=page.replace('<script>\nfunction toggleCapture()',legend+'<script>\nfunction toggleCapture()')
    page=page.replace('body.capture .head,','body.capture .context-legend,body.capture .head,')
    return page


def supplement_exhibition_boundaries(root, context):
    """이름에 '킨텍스'가 없는 제1·2전시장과 부지 relation도 검색한다."""
    if context.get('facility_query_version') == 3:
        return context
    print('킨텍스 제1·2전시장 경계 추가 확인 중…')
    from shapely.geometry import Polygon, LineString, mapping
    from shapely.ops import polygonize, unary_union
    query='''[out:json][timeout:40];(
way[~"^name(:.*)?$"~"킨텍스|KINTEX|한국국제전시|전시관|전시장|Exhibition",i](37.645,126.725,37.695,126.785);
relation[type=multipolygon][~"^name(:.*)?$"~"킨텍스|KINTEX|한국국제전시|전시관|전시장|Exhibition",i](37.645,126.725,37.695,126.785);
);out geom;'''
    errors=[]
    for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
        try:
            req=urllib.request.Request(endpoint+'?'+urllib.parse.urlencode({'data':query}),headers={'User-Agent':'UROP-research-map/1.0'})
            with urllib.request.urlopen(req,timeout=50) as r: raw=json.load(r)
            if raw.get('remark'): raise RuntimeError(raw['remark'])
            break
        except Exception as exc: errors.append(str(exc))
    else:
        print('전시장 경계 추가 조회 실패. 기존 자료로 지도를 표시합니다. 다음 실행 때 다시 조회합니다.')
        return context
    raw_path=Path(root)/CONTEXT_PATH
    (raw_path.parent/'시설추가조회_원자료.json').write_text(json.dumps(raw,ensure_ascii=False))
    known={f['properties'].get('osm_id') for f in context['features']}
    for element in raw.get('elements',[]):
        tags=element.get('tags',{})
        names=[v for k,v in tags.items() if k=='name' or k.startswith('name:')]
        name=next((v for v in names if facility_category(v)), '')
        if not name: continue
        source=f'{element["type"]}/{element["id"]}'
        if source in known: continue
        if element['type']=='way':
            coords=[(p['lon'],p['lat']) for p in element.get('geometry',[]) if p]
            if len(coords)<4 or coords[0]!=coords[-1]: continue
            geom=Polygon(coords)
        else:
            outer=[]; inner=[]
            for member in element.get('members',[]):
                coords=[(p['lon'],p['lat']) for p in member.get('geometry',[]) if p]
                if len(coords)>1:
                    (inner if member.get('role')=='inner' else outer).append(LineString(coords))
            if not outer: continue
            geom=unary_union(list(polygonize(unary_union(outer))))
            if inner: geom=geom.difference(unary_union(list(polygonize(unary_union(inner)))))
        if not geom.is_valid: geom=geom.buffer(0)
        if geom.is_empty: continue
        context['features'].append({'type':'Feature','properties':{'kind':'facility','name':name,'osm_id':source},'geometry':mapping(geom)})
    exhibitions=[f for f in context['features'] if f['properties'].get('kind')=='facility'
                 and facility_category(f['properties'].get('name',''))=='exhibition']
    if exhibitions:
        context['facility_query_version']=3
        print('전시장 경계 확인:', [f['properties']['name'] for f in exhibitions])
    else:
        context.pop('facility_query_version',None)
        print('킨텍스 전시장 경계가 아직 확인되지 않았습니다. 운동장 등 확인된 시설만 표시합니다.')
    (Path(root)/CONTEXT_PATH).write_text(json.dumps(context,ensure_ascii=False))
    return context


def facility_category(name):
    import re
    name=name.strip(); english=name.lower()
    if '고양종합운동장' in name or 'goyang stadium' in english or 'goyang sports complex' in english:
        return 'stadium'
    if any(word in name for word in ['아파트','주차장','오피스','사옥','공원','프라자','IC','제3']): return None
    if any(word in english for word in ['apartment','parking','office','hotel',' iii',' 3']): return None
    if name.upper() in ['킨텍스','KINTEX']: return 'exhibition'
    if re.search(r'(제?\s*[12ⅠⅡ].*전시|전시.*[12ⅠⅡ])',name): return 'exhibition'
    if '한국국제전시' in name: return 'exhibition'
    if 'kintex' in english and re.search(r'exhibition|center|hall|\bii?\b|\b[12]\b',english): return 'exhibition'
    return None


def select_map_context(context, region, distance_m=350):
    """가까운 주거단지와 주요 시설만, 철도는 화면 주변 실제 경로만 사용한다."""
    import geopandas as gpd
    from shapely.geometry import shape,box
    housing_context={'type':'FeatureCollection','features':[]}
    extra=[]
    for feature in context['features']:
        props=feature['properties'];kind=props.get('kind');name=props.get('name','')
        if kind=='apartment' or (kind=='facility' and '아파트' in name):
            f={'type':'Feature','geometry':feature['geometry'],'properties':{'kind':'apartment'}}
            housing_context['features'].append(f)
        elif kind=='rail': extra.append(feature)
        elif kind=='facility':
            category=facility_category(name)
            if category:
                f={'type':'Feature','geometry':feature['geometry'],'properties':dict(props,category=category)}
                extra.append(f)
    local=nearby_residential_context(housing_context,region,distance_m)
    bounds=region.total_bounds; area=box(bounds[0]-1500,bounds[1]-1500,bounds[2]+1500,bounds[3]+1500)
    if extra:
        geoms=gpd.GeoSeries([shape(f['geometry']) for f in extra],crs=4326).to_crs(region.crs)
        local['features'].extend(f for f,geom in zip(extra,geoms) if geom.intersects(area))
    return local
