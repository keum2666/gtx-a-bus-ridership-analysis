"""기말발표 원본의 테마·사진·서식을 보존하며 발표 흐름과 비교표를 수정한다.

전용 Artifact Tool 런타임이 제공되지 않는 환경의 OOXML 보존 편집이다.
원본은 읽기만 하며, 별도 수정본과 검사 기록을 UROP 안에 저장한다.
"""
from pathlib import Path
from copy import deepcopy
import csv
import hashlib
import io
import json
import posixpath
import re
import unicodedata
import uuid
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT.parent / '캡스1'
SOURCE = next(p for p in SOURCE_DIR.iterdir()
              if unicodedata.normalize('NFC', p.name) == '기말발표.pptx')
OUT = ROOT / 'references/presentations/기말발표_흐름수정본.pptx'
BUILD = ROOT / 'results/presentation/.final_flow_edit'
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def tag(prefix, name):
    return '{' + NS[prefix] + '}' + name


def text_of(el):
    return ''.join(t.text or '' for t in el.findall('.//a:t', NS))


def text_body(el):
    return el.find('p:txBody', NS) if el.tag == tag('p', 'sp') else el.find('a:txBody', NS)


def set_text(el, lines, size=None, bold=None, bullets=False, center=None):
    body = text_body(el)
    assert body is not None, el.tag
    if isinstance(lines, str):
        lines = lines.split('\n')
    old_para = body.find('a:p', NS)
    ppr = deepcopy(old_para.find('a:pPr', NS)) if old_para is not None else None
    rp = next(iter(body.findall('.//a:rPr', NS)), None)
    rp = deepcopy(rp) if rp is not None else ET.Element(tag('a', 'rPr'))
    if size is not None:
        rp.set('sz', str(round(size * 100)))
    if bold is not None:
        rp.set('b', '1' if bold else '0')
    for attr in ['dirty', 'err']:
        rp.attrib.pop(attr, None)
    if not rp.findall('a:latin', NS):
        for script in ['latin', 'ea', 'cs']:
            ET.SubElement(rp, tag('a', script), typeface='KoPubWorld돋움체 Medium')
    for p in list(body.findall('a:p', NS)):
        body.remove(p)
    for line in lines:
        p = ET.SubElement(body, tag('a', 'p'))
        pp = deepcopy(ppr) if ppr is not None else ET.Element(tag('a', 'pPr'))
        for item in list(pp):
            if item.tag.rsplit('}', 1)[-1].startswith('bu'):
                pp.remove(item)
        if bullets:
            pp.set('marL', '220000'); pp.set('indent', '-180000')
            ET.SubElement(pp, tag('a', 'buChar'), char='•')
        else:
            pp.set('marL', '0'); pp.set('indent', '0')
            ET.SubElement(pp, tag('a', 'buNone'))
        if center is not None:
            pp.set('algn', 'ctr' if center else 'l')
        # The source spacing is retained, except inherited numbered/bullet indents.
        p.append(pp)
        r = ET.SubElement(p, tag('a', 'r'))
        r.append(deepcopy(rp))
        ET.SubElement(r, tag('a', 't')).text = line
        end = ET.SubElement(p, tag('a', 'endParaRPr'))
        if size is not None:
            end.set('sz', str(round(size * 100)))


def locate(root, needle, kind='sp'):
    hits = [e for e in root.findall('.//p:' + kind, NS) if needle in text_of(e)]
    assert hits, needle
    return min(hits, key=lambda e: len(text_of(e)))


def title(root, value):
    shapes = [s for s in root.findall('.//p:sp', NS)
              if (s.find('p:nvSpPr/p:cNvPr', NS) is not None
                  and s.find('p:nvSpPr/p:cNvPr', NS).attrib.get('name', '').startswith('제목'))]
    assert len(shapes) == 1
    set_text(shapes[0], value, size=30, bold=True)
    for rp in shapes[0].findall('.//a:rPr', NS):
        for script in ['latin', 'ea', 'cs']:
            e = rp.find('a:' + script, NS)
            if e is not None:
                e.set('typeface', 'Gmarket Sans TTF Bold')


def position(el, x, y, width=None, height=None):
    if el.tag == tag('p', 'graphicFrame'):
        xf = el.find('p:xfrm', NS)
    elif el.tag == tag('p', 'grpSp'):
        xf = el.find('p:grpSpPr/a:xfrm', NS)
    else:
        xf = el.find('p:spPr/a:xfrm', NS)
    assert xf is not None, el.tag
    off = xf.find('a:off', NS); ext = xf.find('a:ext', NS)
    off.set('x', str(int(x))); off.set('y', str(int(y)))
    if width is not None: ext.set('cx', str(int(width)))
    if height is not None: ext.set('cy', str(int(height)))


def make_table(frame, rows, widths, row_height, size=18):
    tbl = frame.find('.//a:tbl', NS)
    originals = tbl.findall('a:tr', NS)
    assert originals
    templates = [deepcopy(originals[0]), deepcopy(originals[min(1, len(originals)-1)])]
    grid = tbl.find('a:tblGrid', NS)
    for c in list(grid): grid.remove(c)
    for w in widths: ET.SubElement(grid, tag('a', 'gridCol'), w=str(int(w)))
    for row in originals: tbl.remove(row)
    for i, values in enumerate(rows):
        tr = deepcopy(templates[0 if i == 0 else 1]); tr.set('h', str(row_height))
        cell_template = deepcopy(tr.findall('a:tc', NS)[0])
        for cell in list(tr):
            if cell.tag == tag('a', 'tc'): tr.remove(cell)
        # Row/column creation identifiers are dropped rather than duplicated.
        for ex in list(tr.findall('a:extLst', NS)): tr.remove(ex)
        for j, value in enumerate(values):
            cell = deepcopy(cell_template)
            cell.attrib.clear()
            set_text(cell, value, size=size, bold=(i == 0), center=True)
            cp = cell.find('a:tcPr', NS)
            if cp is None: cp = ET.SubElement(cell, tag('a', 'tcPr'))
            cp.set('anchor', 'ctr')
            for key in ['marL', 'marR']: cp.set(key, '50000')
            for key in ['marT', 'marB']: cp.set(key, '25000')
            tr.append(cell)
        tbl.append(tr)
    gd = frame.find('.//a:graphicData', NS)
    gd.set('uri', 'http://schemas.openxmlformats.org/drawingml/2006/table')


def serialize(root, original):
    declared = dict(value for _, value in ET.iterparse(io.BytesIO(original), events=['start-ns']))
    for prefix, uri in declared.items():
        if not re.fullmatch(r'ns\d+', prefix):
            ET.register_namespace(prefix, uri)
    raw = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    # mc:Ignorable may refer to an otherwise unused prefix. Keep its declaration.
    start = raw.find(b'<', raw.find(b'?>') + 2); end = raw.find(b'>', start)
    opening = raw[start:end]
    extras = []
    for prefix, uri in declared.items():
        attr = ('xmlns:' + prefix) if prefix else 'xmlns'
        if not re.search(rb'\s' + re.escape(attr.encode()) + rb'=', opening):
            extras.append(f' {attr}="{uri}"'.encode())
    if extras: raw = raw[:end] + b''.join(extras) + raw[end:]
    return raw


def main():
    BUILD.mkdir(parents=True, exist_ok=True); OUT.parent.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    with zipfile.ZipFile(SOURCE) as z:
        content = {n: z.read(n) for n in z.namelist()}
        infos = z.infolist()
    roots = {n: ET.fromstring(content[f'ppt/slides/slide{n}.xml']) for n in range(1, 26)}
    changed = set()
    notes = {}
    def edit(n): changed.add(n); return roots[n]

    # Cover and the source's readily checkable arithmetic typo.
    cover = edit(1)
    for t in cover.findall('.//a:t', NS):
        if t.text: t.text = t.text.replace('중간발표', '기말발표')
    for t in edit(7).findall('.//a:t', NS):
        if t.text: t.text = t.text.replace('-5,189', '-5,009')

    # Dataset and analysis sample explanations.
    r = edit(10)
    title(r, '3.1 분석 자료와 승차건수 집계 기준')
    sp = locate(r, '실제 교통카드 이용 패턴')
    set_text(sp, ['국토교통부 지역별 교통카드이용 합성데이터 활용',
                  '개통 전 2024.10.17 / 개통 후 2025.11.06 (모두 목요일)',
                  '합성 이용인원 값의 시점별 차이를 고려하여 기록 1행을 승차 1건으로 집계'], size=18, bullets=True)
    notes[10] = '주요 자료는 국토교통부 지역별 교통카드이용 합성데이터입니다. 원천 자료의 실제 승객 수와 동일한 자료는 아닙니다. 2025년 10월 자료의 합성값 이상을 제공기관에 확인한 뒤 11월 6일로 기준일을 변경했습니다. 두 시점의 합성 이용인원 값 분포도 달라 기록 한 행을 승차 1건으로 집계했습니다.'
    title(edit(11), '3.2 노선·정류장 구성이 유지된 분석격자 선정')
    title(edit(12), '3.3 권역별 광역버스 승차 변화와 출근시간대')
    notes[12] = '노선·정류장 구성이 유지된 126개 격자에서 비교했습니다. 출근시간대에는 전체 812건, 26.2% 감소했습니다. 운정중앙과 킨텍스는 감소했지만 대곡은 39건 증가했습니다. 대곡은 하루 전체에서는 감소해 시간대에 따라 방향이 달랐습니다. 또한 하루 전체 순감소량의 51%가 출근시간대에서 발생했습니다. 이러한 이용 집중과 변화 특성을 바탕으로 출근시간대 분석을 진행했습니다.'
    title(edit(13), '3.4 광역버스 승차 변화 관련 독립변수')

    r = edit(14); title(r, '3.5 독립변수 구축 방법')
    for t in r.findall('.//a:t', NS):
        if t.text:
            t.text = t.text.replace('OSR', 'ORS').replace('승객 비율', '기록 비율').replace('승객 중', '기록 중').replace('이용객의 평균', '기록의 평균')

    r = edit(15); title(r, '3.6 보행시간·건축물 연면적의 로그 변환')
    tree = r.find('p:cSld/p:spTree', NS)
    for sp in list(tree):
        if '10.29 cm' in text_of(sp): tree.remove(sp)

    r = edit(16); title(r, '3.7 종속변수와 독립변수의 가설')
    for t in r.findall('.//a:t', NS):
        if t.text:
            t.text = t.text.replace('후보 8개', '7개').replace('승차인원 증가', '승차 변화량 증가').replace('승차인원 감소', '승차 변화량 감소')
    sp = locate(r, '격자별 서울행 광역버스 승차건수 변화량')
    set_text(sp, ['출근시간대 승차 변화량 = GTX-A 개통 후 − 개통 전 승차건수',
                  '기초통계·순위상관: 126개 / 회귀분석: 113개 격자',
                  '개통 전 출근시간대 기록이 없어 목적지 비율·통행시간을 계산할 수 없는 13개 격자 제외'], size=18, bullets=True)
    position(sp, 489088, 1730000, 11150000, 1200000)
    hypothesis_rows = r.findall('.//a:tbl/a:tr', NS)
    if len(hypothesis_rows) == 8:
        for tr, sign in zip(hypothesis_rows[1:], ['+', '−', '−', '−', '−', '−', '−']):
            cells = tr.findall('a:tc', NS)
            set_text(cells[-1], '값이 클수록 승차 변화량 ' + ('증가 (+)' if sign == '+' else '감소 (−)'), size=18, center=True)
    notes[16] = '종속변수는 출근시간대 광역버스 승차 변화량입니다. 음수는 감소, 양수는 증가입니다. 기초통계와 순위상관은 전체 126개 격자이고, 회귀는 개통 전 출근시간대 기록이 없는 13개 격자를 제외한 113개입니다. 이 13개 격자에서는 기존 목적지 비율과 평균 버스 통행시간을 계산할 수 없었습니다. 독립변수는 7개입니다.'

    # Keep both regression slides as requested; correct the day table to the stated common 113 sample.
    coeff = list(csv.DictReader((ROOT / 'results/analysis/regression/common_113/광역버스_동일113격자_회귀계수.csv').open(encoding='utf-8-sig')))
    labels = ['GTX역 보행시간', '20~50대 인구', '건축물 연면적', '주거지역 비율(%)',
              'GTX 경쟁 목적지 비율(%)', '평균 버스 통행시간(분)', 'IC 도로거리(km)']
    keys = ['GTX역 보행시간', '20~50대 인구', '건축물 연면적', '주거지역 비율',
            'GTX 경쟁 목적지 비율', '평균 버스 통행시간', 'IC 접근성']
    for n in [17, 18]:
        r = edit(n)
        for frame in r.findall('.//p:graphicFrame', NS):
            table = frame.find('.//a:tbl', NS)
            if table is None: continue
            current = table.findall('a:tr', NS)
            if len(current) != 8: continue
            morning = n == 18 or any('13.879' in text_of(c) for c in current)
            model = '출근시간대 113개' if morning else '하루 전체 113개'
            for tr, label, key in zip(current[1:], labels, keys):
                row = next(q for q in coeff if q['모형'] == model and q['변수'] == key)
                vals = [label, f'{float(row["계수"]):.3f}'.replace('-', '−'),
                        '< .001' if float(row['p값']) < .001 else f'{float(row["p값"]):.3f}']
                for cell, value in zip(tr.findall('a:tc', NS), vals): set_text(cell, value, size=17, center=True)

    r = edit(19); title(r, '3.8 출근시간대 회귀분석 결과 해석')
    tree = r.find('p:cSld/p:spTree', NS)
    for sp in list(tree):
        if '├' in text_of(sp): tree.remove(sp)
    frame = r.find('.//p:graphicFrame', NS)
    rows = [['변수', '승차 변화량과의 관계', '가능한 해석'],
            ['GTX역 보행시간', '길수록 변화량 높음 (+)', '역이 멀면 광역버스 이용을 유지할 가능성'],
            ['GTX 경쟁 목적지 비율', '높을수록 변화량 낮음 (−)', '목적지가 겹치면 GTX를 대안으로 선택할 가능성'],
            ['IC 도로거리', '길수록 변화량 낮음 (−)', '고속도로 진입 부담이 광역버스 이용과 관련될 가능성'],
            ['주거지역 비율', '높을수록 변화량 높음 (+)', '감소폭이 작거나 증가폭이 큼 (가설은 지지되지 않음)']]
    make_table(frame, rows, [2750000, 3450000, 4800000], 490000, size=17)
    position(frame, 650000, 1900000, 11000000, 2450000)
    sp = locate(r, 'GTX 이용과 관련된 여건')
    set_text(sp, ['GTX역 보행시간·경쟁 목적지 비율과 IC 도로거리·주거지역 비율이 모두 유의',
                  '이 중 GTX 이용 여건과 관련된 결과를 더 살펴보기 위해, 역 연계버스 이용과의 관계 확인'], size=20, bullets=True)
    position(sp, 600000, 4780000, 11000000, 1380000)
    notes[19] = '회귀에서는 네 변수가 유의했습니다. 보행시간과 경쟁 목적지 비율은 GTX 이용 여건이고, IC 도로거리와 주거지역 비율은 기존 교통·지역 여건입니다. 주거지역 비율은 예상과 반대여서 가설이 지지되지 않았습니다. 이 가운데 GTX 이용 여건과 승차 변화량의 관계는 GTX 개통과 관련된 통행 변화 가능성을 시사합니다. 이를 더 살펴보기 위해 GTX역으로 향하는 버스 이용도 같은 공간에서 연결해 확인하겠습니다.'

    r = edit(20)
    set_text(locate(r, '광역버스 승차 변화와'), '4. 광역버스 승차 변화와\nGTX역 연계버스 이용의 관계', size=40, bold=True)
    notes[20] = '다음은 광역버스 승차 변화와 GTX역 접근통행의 관계입니다. 먼저 연계버스가 어느 권역에서 얼마나 이용되는지 확인하고, 운정중앙역과 대곡역의 이용 결과 및 현장 여건을 비교하겠습니다. 이후 같은 격자에서 두 지표가 관련되는지 순위상관분석으로 살펴보겠습니다.'

    r = edit(21); title(r, '4.1 GTX역 연계버스 이용 현황')
    header = locate(r, '격자별 GTX역 연계버스 승차 건수')
    set_text(header, '개통 후 출근시간대(06~10시) · 126개 격자', size=21, bold=True)
    # Use the existing header area for an operational definition; preserve the original charts.
    body_template = deepcopy(locate(roots[19], 'GTX역 보행시간·경쟁 목적지 비율과'))
    set_text(body_template, '분석격자에서 승차하여 GTX역 정류장에서 하차한 마을·시내버스 기록', size=17)
    position(body_template, 650000, 1740000, 11000000, 330000)
    ids = [int(e.attrib['id']) for e in r.findall('.//p:cNvPr', NS)]
    for k, e in enumerate(body_template.findall('.//p:cNvPr', NS), max(ids)+1): e.set('id', str(k)); e.set('name', '연계버스 집계 기준')
    for e in body_template.iter():
        if e.tag.rsplit('}',1)[-1] == 'creationId' and 'id' in e.attrib: e.set('id', '{'+str(uuid.uuid4()).upper()+'}')
    r.find('p:cSld/p:spTree', NS).append(body_template)
    frame = r.find('.//p:graphicFrame', NS)
    position(frame, 4123192, 2150000, 5063681, 1580000)
    for tr in frame.findall('.//a:tr', NS): tr.set('h', '316000')
    notes[21] = '연계버스는 2025년 11월 6일 출근시간대에 분석격자에서 승차해 GTX역 정류장에서 하차한 마을·시내버스 기록입니다. GTX역 정류장에서 승차한 기록은 제외했습니다. 총 646건이며 운정중앙 488건, 킨텍스 41건, 대곡 117건입니다. 운정중앙 비중은 75.5%입니다. 권역별 격자 수가 다르므로 다음 장에서는 격자당 규모와 이용 격자 비율도 함께 비교하겠습니다.'

    r = edit(22); title(r, '4.2 운정중앙역·대곡역의 이용 결과와 환승 여건')
    header = locate(r, '서로 다른 환승 환경')
    set_text(header, '출근시간대 이용 결과와 기존 철도·버스 연결 여건', size=21, bold=True)
    frame = r.find('.//p:graphicFrame', NS)
    rows = [['비교 항목', '운정중앙역 권역', '대곡역 권역'],
            ['광역버스 승차 변화', '−456건 (−35.0%)', '+39건 (+8.9%)'],
            ['격자당 평균 연계버스 승차', '7.7건', '3.2건'],
            ['연계버스 이용 격자 비율', '21/63개 (33.3%)', '12/37개 (32.4%)'],
            ['기존 철도 이용 여건', '철도 접근성이 낮았던 지역에 신설', '기존 3개 철도노선에 GTX 추가'],
            ['답사에서 확인한 버스 연결', '역 내 버스 환승센터', '도로 정류장에서 역 출입구로 이동']]
    make_table(frame, rows, [3300000,3850000,3850000], 390000, size=16)
    position(frame, 650000, 1820000, 11000000, 2340000)
    pics = r.findall('p:cSld/p:spTree/p:pic', NS)
    assert len(pics) == 3
    for i, pic in enumerate(pics):
        ex = pic.find('p:spPr/a:xfrm/a:ext', NS)
        ratio = int(ex.attrib['cx']) / int(ex.attrib['cy'])
        h = 1680000; w = int(h * ratio)
        position(pic, 650000 + i * 3660000 + (3400000-w)//2, 4380000, w, h)
    notes[22] = '운정중앙은 출근시간대 광역버스가 감소했고 대곡은 증가했습니다. 연계버스는 격자당 평균으로도 운정중앙이 많았습니다. 반면 이용이 관측된 격자 비율은 두 권역이 약 33%로 비슷했습니다. 따라서 운정중앙의 총이용이 많은 것을 단순히 격자 수가 많기 때문이라고만 보기는 어렵습니다. 현장에서는 운정중앙의 역 내 환승센터와 임시주차장, 대곡의 도로 정류장에서 역까지 이동하는 동선을 확인했습니다. 대곡은 기존 철도를 이용하려는 통행도 포함될 수 있습니다. 시설 차이가 승차 변화를 일으켰다고 단정하기보다는 서로 다른 이용 결과를 이해할 배경으로 보았습니다. 그렇다면 같은 권역 안에서도 광역버스 변화량과 연계버스 이용이 관련되는지 다음으로 확인하겠습니다.'

    r = edit(23); title(r, '4.3 광역버스 승차 변화와 연계버스 이용의 순위상관')
    header = locate(r, '광역버스 승차 건수 변화량')
    set_text(header, '출근시간대 광역버스 변화량과 개통 후 연계버스 승차건수', size=20, bold=True)
    frame = r.find('.//p:graphicFrame', NS)
    rows = [['권역', '격자 수', '스피어만 ρ', 'p값'],
            ['전체', '126개', '−0.290', '< .001'],
            ['운정중앙역', '63개', '−0.399', '.001'],
            ['킨텍스역', '26개', '−0.151', '.462'],
            ['대곡역', '37개', '−0.327', '.048']]
    make_table(frame, rows, [3600000,2000000,2500000,2500000], 430000, size=18)
    position(frame, 800000, 2150000, 10600000, 2150000)
    sp = locate(r, '광역버스 승차 변화량 낮음')
    set_text(sp, ['광역버스 변화량이 낮을수록 개통 후 연계버스 이용이 많은 경향',
                  '변화량이 낮음: 감소폭이 크거나 증가폭이 작음',
                  'GTX 연계통행으로의 전환 가능성을 살펴볼 간접 근거'], size=20, bullets=True)
    position(sp, 650000, 4600000, 11000000, 1450000)
    notes[23] = '같은 126개 격자의 출근시간대 두 지표를 연결한 결과 전체 상관계수는 마이너스 0.290으로 유의했습니다. 연계버스가 0건인 격자도 포함했습니다. 음의 관계는 광역버스 변화량이 낮은 곳에서 연계버스 이용이 많고, 반대로 변화량이 높은 곳에서 연계버스 이용이 적은 경향을 의미합니다. 여기서 낮은 변화량은 감소폭이 크거나 증가폭이 작다는 뜻입니다. 운정중앙과 대곡에서는 유의했고 킨텍스는 유의하지 않았습니다. 대곡은 권역 전체 승차가 증가했지만 격자별 관계는 음의 방향이었습니다. 이 결과는 실제 이용자의 GTX 전환을 직접 확인한 결과는 아니며, 역 접근성 등 공통 지역 특성이 함께 반영됐을 수도 있습니다.'

    r = edit(24); title(r, '5. 결론 및 정책적 시사점')
    tree = r.find('p:cSld/p:spTree', NS)
    heading_template = deepcopy(locate(r, '지역·교통 여건을 반영한', kind='grpSp'))
    body_template = deepcopy(locate(r, 'GTX역까지 보행시간'))
    for el in list(tree):
        if el.tag in [tag('p','nvGrpSpPr'),tag('p','grpSpPr')]: continue
        nv = el.find('.//p:cNvPr', NS)
        name = nv.attrib.get('name','') if nv is not None else ''
        if name.startswith('제목') or '슬라이드 번호' in name or name == '직사각형 72': continue
        tree.remove(el)
    blocks = [
        ('지역·교통 여건을 반영한 광역버스 운영 검토',
         ['GTX역 보행시간·서울 목적지·IC 도로거리·주거지역 비율을 함께 고려',
          '지역별 실제 승차 변화를 바탕으로 노선 유지·조정 여부 검토']),
        ('광역버스와 GTX역 연계버스를 함께 고려한 교통계획',
         ['광역버스 변화량이 낮은 지역에서 개통 후 연계버스 이용이 많은 경향',
          'GTX 연계통행으로의 전환 가능성을 살펴볼 간접 근거로 활용']),
        ('GTX-B·C 개통 지역의 사전 검토에 활용',
         ['GTX-A에서 확인한 네 가지 관련 특성을 개통 예정 지역의 점검 항목으로 활용',
          '개통 전후 이용자료를 확보하여 지역별 광역버스·연계버스 운영 검토'])]
    next_id = max(int(n.attrib['id']) for n in r.findall('.//p:cNvPr',NS))+1
    for i, (heading, lines) in enumerate(blocks):
        h=deepcopy(heading_template); b=deepcopy(body_template)
        target=locate(h, '지역·교통 여건을 반영한')
        set_text(target, heading, size=21, bold=True)
        position(h, 525435, 1200000+i*1750000)
        set_text(b, lines, size=18, bold=False, bullets=True)
        position(b, 602634, 1680000+i*1750000, 10950000, 1120000)
        for obj in [h,b]:
            for nv in obj.findall('.//p:cNvPr',NS): nv.set('id',str(next_id)); next_id+=1
            for el in obj.iter():
                if el.tag.rsplit('}',1)[-1]=='creationId' and 'id' in el.attrib: el.set('id','{'+str(uuid.uuid4()).upper()+'}')
            tree.append(obj)
    notes[24] = '결론은 세 가지입니다. 첫째, 광역버스 승차 변화는 GTX역 보행시간과 기존 서울 목적지뿐 아니라 IC 도로거리, 주거지역 비율과도 관련됐습니다. 지역별 실제 변화를 바탕으로 노선을 검토할 필요가 있습니다. 둘째, 광역버스 변화량이 낮은 지역에서 GTX역 연계버스 이용이 많은 공간적 관계를 확인했습니다. 이는 GTX 연계통행으로의 전환 가능성을 살펴볼 간접 근거입니다. 셋째, 이러한 관련 특성은 GTX-B·C 지역의 사전 점검 항목으로 활용할 수 있습니다. A의 계수를 그대로 적용해 수요를 확정 예측한다는 의미는 아니며, 개통 전후 자료를 확보해 각 지역에 맞게 검토하는 기반으로 활용하고자 합니다.'

    # Update spoken transitions without adding the explicitly rejected research-question slide.
    notes[8] = '두 명의 인터뷰에서는 GTX를 주로 이용하게 된 사례와 기존 철도 이용을 유지한 사례가 모두 나타났습니다. GTX역까지는 마을버스나 가족 차량으로 접근하기도 했고, 목적지에 따라 광역버스를 계속 이용하기도 했습니다. 이를 참고하여 지역·교통 특성과 광역버스 승차 변화의 관계를 분석하고, GTX역으로 향하는 연계버스 이용도 함께 살펴보았습니다.'
    for n in sorted(changed):
        part=f'ppt/slides/slide{n}.xml'; content[part]=serialize(roots[n],content[part])
    for n, value in notes.items():
        part=f'ppt/notesSlides/notesSlide{n}.xml'
        if part not in content: continue
        root=ET.fromstring(content[part])
        candidates=[]
        for sp in root.findall('.//p:sp',NS):
            ph=sp.find('p:nvSpPr/p:nvPr/p:ph',NS)
            if ph is not None and ph.attrib.get('type')=='body': candidates.append(sp)
        if candidates:
            set_text(candidates[0],value,size=14)
            content[part]=serialize(root,content[part])
    if OUT.exists():
        output=OUT.with_name(OUT.stem+'_'+uuid.uuid4().hex[:6]+OUT.suffix)
    else: output=OUT
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for info in infos: z.writestr(info,content[info.filename])
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for name in z.namelist():
            if name.endswith(('.xml','.rels')): ET.fromstring(z.read(name))
        assert len(ET.fromstring(z.read('ppt/presentation.xml')).findall('p:sldIdLst/p:sldId',NS))==25
        for n in range(1,26):
            root=ET.fromstring(z.read(f'ppt/slides/slide{n}.xml'))
            ids=[e.attrib['id'] for e in root.findall('.//p:cNvPr',NS)]
            assert len(ids)==len(set(ids)),(n,'duplicate shape ids')
            for gd in root.findall('.//a:graphicData',NS):
                if gd.find('a:tbl',NS) is not None:
                    assert gd.attrib['uri']=='http://schemas.openxmlformats.org/drawingml/2006/table'
    report={'source':str(SOURCE),'source_sha256':source_hash,'output':str(output),
            'slide_count':25,'new_slides':0,'changed_slides':sorted(changed),
            'updated_notes':sorted(notes),'native_powerpoint_opened':False,
            'validation':'ZIP CRC, XML parsing, slide count, shape IDs, native table URI passed'}
    (BUILD/'edit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
