"""실제 126개 격자의 출근시간대 승차 변화량을 캡처하는 카카오맵."""
import html
import importlib.util
import sys
import time
from pathlib import Path
from urllib.parse import quote

import numpy as np
from IPython.display import HTML, IFrame, display

VIEW_ID = 'morning_change_capture'
# 두 시점의 승차건수 차이(건). 모든 권역에 동일한 구간을 적용한다.
BINS = [-40, -20, 0, 1, 20, 40]
COLORS = ['#A50F15', '#DE2D26', '#FB6A4A', '#EEEEEE', '#6BAED6', '#3182BD', '#08519C']
LABELS = ['−40건 미만', '−40~−21건', '−20~−1건', '0건', '+1~+19건', '+20~+39건', '+40건 이상']


def load_helpers(root):
    path = Path(root) / 'code/03_eda/kakao_combined_grid_overlay.py'
    spec = importlib.util.spec_from_file_location('_morning_capture_helpers', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def morning_page(item, app_key, helpers):
    """기존 지도 틀과 실제 격자 경계를 재사용하되 출근시간대만 표시한다."""
    item = dict(item)
    item['features'] = [dict(feature) for feature in item['features']]
    for feature in item['features']:
        change = feature['change'][1]
        color = COLORS[int(np.searchsorted(BINS, change, side='right'))]
        feature['colors'] = [color, color]
        feature['different'] = False
    page = helpers.combined_page(item, app_key)
    page = page.replace('하루 전체·출근시간대 통합 지도', '출근시간대 승차 변화량')
    page = page.replace('역 권역 · 광역버스 승차 변화</div>', '역 · 출근시간대 광역버스 승차 변화량</div>')
    page = page.replace('격자 왼쪽: 하루 전체　/　격자 오른쪽: 출근시간대',
                        '06:00 이상 10:00 미만 · GTX-A 개통 후 − 개통 전 · 지도를 움직이거나 확대하여 캡처하세요.')
    start = page.index('<div class="legend">')
    end = page.index('</div>', start) + len('</div>')
    legend = '<div class="legend">' + ''.join(
        f'<span class="item"><i class="swatch" style="background:{color}"></i>{label}</span>'
        for color, label in zip(COLORS, LABELS)
    ) + '<span class="item"><i class="green">★</i>GTX역</span></div>'
    page = page[:start] + legend + page[end:]
    begin = page.index('function showInfo(')
    finish = page.index('\nfunction drawCells', begin)
    info = '''function showInfo(cell,event){
 const signed=v=>(v>0?'+':'')+v;
 info.setContent('<div class="info"><b>격자 '+cell.id+'</b><table><tr><th>출근시간대</th><th>승차건수</th></tr><tr><th>GTX-A 개통 전</th><td>'+cell.before[1]+'건</td></tr><tr><th>GTX-A 개통 후</th><td>'+cell.after[1]+'건</td></tr><tr><th>변화량</th><td>'+signed(cell.change[1])+'건</td></tr></table></div>');
 info.setPosition(event.latLng);info.open(mainMap);
}'''
    page = page[:begin] + info + page[finish:]
    page = page.replace('#frame{height:570px;', '#frame{height:calc(100vh - 155px);min-height:500px;')
    # 캡처 모드에서는 지도만 화면에 채운다. 다시 C를 누르면 원래 화면으로 돌아간다.
    page = page.replace('</style>', '''
body.capture .head,body.capture .intro,body.capture .legend,body.capture .capture-button{display:none}
body.capture #frame{height:100vh;min-height:0}
.capture-button{position:fixed;right:12px;bottom:8px;z-index:30;background:white;border:1px solid #555;border-radius:4px;padding:7px 12px;font-size:14px;cursor:pointer}
</style>''')
    page = page.replace('<script>\nconst data=', '''<button class="capture-button" onclick="toggleCapture()">지도만 보기 (C) · 다시 C로 복원</button>
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


def show_morning_capture(data, root, app_key, display_maps=True, context=None):
    helpers = load_helpers(root)
    # 기존 노트북의 localhost 서버를 공유하여 다른 지도 링크도 유지한다.
    helpers.show_combined_kakao(data, root, app_key, display_maps=False, include_context=False)
    backend = sys.modules['kakao_grid_overlay']
    payload = helpers.make_combined_payload(data, root)
    pages = {station: morning_page(payload[station], app_key, helpers) for station in helpers.ORDER}
    if context is not None:
        path = Path(root)/'code/03_eda/kakao_map_context.py'
        spec = importlib.util.spec_from_file_location('_morning_map_context', path)
        annotation = importlib.util.module_from_spec(spec); spec.loader.exec_module(annotation)
        pages = {station: annotation.add_context_page(
            page, annotation.select_map_context(context, data.loc[data.nearest_station.eq(station)]))
            for station, page in pages.items()}
    backend._pages[VIEW_ID] = pages
    urls = {station: f'http://localhost:{backend.PORT}/map?station={quote(station)}&view={VIEW_ID}&v={time.time_ns()}'
            for station in helpers.ORDER}
    if display_maps:
        for station, url in urls.items():
            display(HTML(f'<p><b>{station}역 출근시간대</b> · <a href="{html.escape(url)}" target="_blank" rel="noopener">새 탭에서 크게 열기·캡처</a></p>'))
            display(IFrame(src=url, width='100%', height=780))
    return urls
