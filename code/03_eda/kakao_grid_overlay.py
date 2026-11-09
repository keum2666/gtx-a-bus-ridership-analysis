"""011 노트북에서 쓰는 카카오맵 격자 오버레이(로컬 서버, 파일 저장 없음)."""

import html
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from IPython.display import IFrame, display


PORT = 8765
STATION_ORDER = ("운정중앙", "킨텍스", "대곡")
COLORS = ("#67000D", "#CB181D", "#FB6A4A", "#FEE0D2")
DIRECTION_COLORS = {"감소": "#D73027", "유지": "#EEEEEE", "증가": "#2166AC"}
_server = None
_thread = None
_pages = {}


def _polygon_paths(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError(f"격자가 다각형이 아닙니다: {geometry['type']}")


def _page(station, features, station_point, edges, app_key, count_basis=False, time_label="",
          classification="quartile"):
    unit = "건" if count_basis else "명"
    metric = "승차건수" if count_basis else "승차인원"
    payload = json.dumps(features, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    point = json.dumps(station_point)
    if classification == "direction":
        legend = "".join(
            f'<span><i style="background:{color}"></i>{label}</span>'
            for label, color in DIRECTION_COLORS.items()
        )
        thresholds = f"변화량 = 2025년 {metric} − 2024년 {metric} · 감소·유지·증가 구분"
    elif count_basis:
        # 변화량은 정수 건수이므로 사분위 실수 경계를 겹치지 않는 정수 구간으로 표시한다.
        legend_items = []
        for idx, color in enumerate(COLORS):
            lower = None if idx == 0 else math.floor(edges[idx - 1]) + 1
            upper = min(math.floor(edges[idx]), -1) if idx < 3 else -1
            if lower is not None and lower > upper:
                continue  # 증가·동일 색상으로 대체되어 사용하지 않는 감소 구간은 생략
            if lower is None:
                label = f"{upper:,}건 이하"
            elif lower == upper:
                label = f"{lower:,}건"
            else:
                label = f"{lower:,}건 이상 {upper:,}건 이하"
            legend_items.append(f'<span><i style="background:{color}"></i>{label}</span>')
        legend_items += [
            '<span><i style="background:#EEEEEE"></i>0건 (동일)</span>',
            '<span><i style="background:#2166AC"></i>+1건 이상 (증가)</span>',
        ]
        legend = "".join(legend_items)
        thresholds = "변화량 = 2025년 승차건수 − 2024년 승차건수 · 세 권역에 동일한 범례 적용"
    else:
        labels = [f"{edges[0]:g}명 이하",
                  f"{edges[0]:g}명 초과 {edges[1]:g}명 이하",
                  f"{edges[1]:g}명 초과 {edges[2]:g}명 이하",
                  f"{edges[2]:g}명 초과"]
        legend = "".join(f'<span><i style="background:{color}"></i>{label}</span>'
                         for color, label in zip(COLORS, labels))
        thresholds = "변화량 = 2025년 승차인원 − 2024년 승차인원 · 세 권역에 동일한 범례 적용"
    sdk = "https://dapi.kakao.com/v2/maps/sdk.js?appkey=" + quote(app_key, safe="") + "&autoload=false"
    time_heading = f" · {html.escape(time_label)}" if time_label else ""
    if time_label:
        thresholds += f" · 승차시각 {html.escape(time_label)}"
    legend_class = "legend direction" if classification == "direction" else "legend"
    color_note = (" 감소는 빨강, 유지는 회색, 증가는 파랑입니다."
                  if classification == "direction" else
                  " 감소 격자는 전체 126개 공통 사분위 색상, 증가 격자는 파랑, 동일 격자는 회색입니다."
                  if count_basis else "")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {{ font-family: sans-serif; margin: 0; color: #222; }}
.head {{ padding: 10px 14px; font-weight: 700; font-size: 17px; }}
#map {{ height: 490px; width: 100%; background: #eee; }}
.legend {{ padding: 8px 14px; display:flex; flex-wrap:wrap; gap: 14px; font-size: 13px; }}
.legend span {{ display:inline-flex; align-items:center; gap:5px; }}
.legend i {{ width:15px; height:15px; border:1px solid #555; display:inline-block; }}
.legend.direction {{ flex-direction:column; gap:0; font-size:16px; font-weight:700; }}
.legend.direction span {{ gap:12px; }}
.legend.direction i {{ width:20px; height:32px; border:0; }}
.note {{ padding: 0 14px 10px; font-size: 12px; color:#444; }}
.error {{ padding: 20px; color:#9b1c1c; }}
</style></head><body>
<div class="head">{html.escape(station)} 권역 · 광역버스 {metric} 변화량{time_heading}</div>
<div id="map"></div>
<div class="{legend_class}">{legend}</div>
<div class="note">{thresholds} · 격자를 클릭하면 {metric}와 변화량을 볼 수 있습니다.{color_note}</div>
<script>
const features = {payload};
const stationPoint = {point};
function error(message) {{ document.getElementById('map').innerHTML = '<div class="error">' + message + '</div>'; }}
function initMap() {{
  if (!window.kakao || !kakao.maps) {{ error('카카오 지도 SDK를 불러오지 못했습니다. 키·도메인·지도 사용 설정을 확인하세요.'); return; }}
  const map = new kakao.maps.Map(document.getElementById('map'), {{
    center: new kakao.maps.LatLng(stationPoint[0], stationPoint[1]), level: 6
  }});
  const bounds = new kakao.maps.LatLngBounds();
  const info = new kakao.maps.InfoWindow({{removable: true}});
  for (const cell of features) {{
    for (const polygonRings of cell.paths) {{
      const path = polygonRings.map(ring => ring.map(xy => {{
        const ll = new kakao.maps.LatLng(xy[1], xy[0]); bounds.extend(ll); return ll;
      }}));
      const polygon = new kakao.maps.Polygon({{
        map, path, strokeWeight: 1,
        strokeColor: '#222222',
        strokeOpacity: 1, fillColor: cell.color, fillOpacity: 0.76
      }});
      kakao.maps.event.addListener(polygon, 'click', function(event) {{
        const change = cell.change > 0 ? '+' + cell.change : String(cell.change);
        const content = '<div style="padding:8px 11px;line-height:1.5;white-space:nowrap">'
          + '<b>격자 ' + cell.id + '</b><br>2024년 ' + cell.before + '{unit} → 2025년 '
          + cell.after + '{unit}<br>변화량 ' + change + '{unit}</div>';
        info.setContent(content); info.setPosition(event.latLng); info.open(map);
      }});
    }}
  }}
  const stationMarker = new kakao.maps.Marker({{
    map, position: new kakao.maps.LatLng(stationPoint[0], stationPoint[1])
  }});
  kakao.maps.event.addListener(stationMarker, 'click', function() {{
    info.setContent('<div style="padding:7px 10px">GTX-A {html.escape(station)}역</div>');
    info.setPosition(stationMarker.getPosition()); info.open(map);
  }});
  if (features.length) map.setBounds(bounds, 45, 45, 45, 45);
}}
</script>
<script src="{sdk}" onload="kakao.maps.load(initMap)" onerror="error('카카오 지도 SDK 연결 실패')"></script>
</body></html>"""


def show_kakao_overlay(plot_grid, station_coords, quartile_edges, app_key, count_basis=False,
                       view_id=None, time_label="", display_maps=True, classification="quartile"):
    """126개 실제 경계를 표시한다. view_id로 종일·출근 지도를 함께 유지한다."""
    global _server, _thread
    if len(plot_grid) != 126 or plot_grid["셀 ID"].nunique() != 126:
        raise ValueError("고유한 126개 분석 격자가 필요합니다.")
    if not app_key:
        raise ValueError("카카오 JavaScript 키가 필요합니다.")
    if classification not in ("quartile", "direction"):
        raise ValueError("classification은 quartile 또는 direction이어야 합니다.")
    if view_id is None:
        view_id = "count" if count_basis else "person"
    if not isinstance(view_id, str) or not view_id:
        raise ValueError("view_id는 비어 있지 않은 문자열이어야 합니다.")

    before_col, after_col, change_col = (
        ("board_2024", "board_2025", "change") if count_basis
        else ("board_2024_all", "board_2025_all", "change_all")
    )
    geo = plot_grid.to_crs("EPSG:4326")
    pages = {}
    for station in STATION_ORDER:
        part = geo[geo["nearest_station"].astype(str) == station].copy()
        if part.empty:
            raise ValueError(f"{station} 격자가 없습니다.")
        features = []
        for _, row in part.iterrows():
            if classification == "direction":
                label = "감소" if row[change_col] < 0 else "증가" if row[change_col] > 0 else "유지"
                color = DIRECTION_COLORS[label]
            else:
                code = int(row["변화량 사분위 코드"])
                if code not in range(4):
                    raise ValueError(f"사분위 코드 오류: 셀 {row['셀 ID']}")
                color = ("#2166AC" if row[change_col] > 0 else "#EEEEEE" if row[change_col] == 0 else COLORS[code]) if count_basis else COLORS[code]
            features.append({
                "id": int(row["셀 ID"]),
                "paths": _polygon_paths(row.geometry.__geo_interface__),
                "color": color,
                "before": int(row[before_col]),
                "after": int(row[after_col]),
                "change": int(row[change_col]),
            })
        pages[station] = _page(station, features, station_coords[station], quartile_edges,
                               app_key, count_basis=count_basis, time_label=time_label,
                               classification=classification)

    # 같은 포트에서 여러 시간대의 페이지를 보관한다. 종일 iframe도 유지한다.
    _pages[view_id] = pages

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            name = parse_qs(parsed.query).get("station", [""])[0]
            requested_view = parse_qs(parsed.query).get("view", ["count"])[0]
            selected_pages = _pages.get(requested_view, {})
            if parsed.path != "/map" or name not in selected_pages:
                self.send_error(404)
                return
            body = selected_pages[name].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    if _server is None:
        try:
            _server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        except PermissionError as exc:
            raise RuntimeError("이 실행 환경에서 localhost 서버를 열 수 없습니다. 로컬 Jupyter에서 실행하세요.") from exc
        except OSError as exc:
            raise RuntimeError(f"localhost:{PORT} 포트가 사용 중입니다. 이전 실행 서버를 종료하세요.") from exc
        _thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _thread.start()
    if display_maps:
        for station in STATION_ORDER:
            url = (f"http://localhost:{PORT}/map?station={quote(station)}"
                   f"&view={quote(view_id)}&v={time.time_ns()}")
            display(IFrame(src=url, width="100%", height=675 if classification == "direction" else 585))
        print("격자 126개 오버레이 준비 완료. 지도가 비어 있으면 카카오 JavaScript 키와 등록 도메인(http://localhost:8765)을 확인하세요.")
