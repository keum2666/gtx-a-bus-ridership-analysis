# -*- coding: utf-8 -*-
"""현 원고를 보존하고 연계버스 회귀 제외 버전을 만든다.

기초통계·순위상관 결과는 analyze_feeder_without_regression.py로 재현한다.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'references/GTX-A_연구보고서_원고.md'
TARGET = ROOT / 'references/GTX-A_연구보고서_원고_연계버스회귀제외.md'
RESULTS = ROOT / 'results/paper/no_feeder_regression'


def main():
    original = SOURCE.read_text()
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    text = original
    changes = []

    def replace_once(old, new, reason):
        nonlocal text
        assert text.count(old) == 1, (reason, text.count(old))
        text = text.replace(old, new, 1)
        changes.append(reason)

    def replace_paragraph(prefix, replacement, reason):
        nonlocal text
        pattern = r'(?m)^ *' + re.escape(prefix) + r'[^\n]*(?:\n(?!\n)[^\n]+)*'
        matches = list(re.finditer(pattern, text))
        assert len(matches) == 1, (reason, len(matches))
        match = matches[0]
        text = text[:match.start()] + replacement + text[match.end():]
        changes.append(reason)

    # The abstract stays one paragraph and focuses the regression claim on broad buses.
    start = text.index('## 요약\n') + len('## 요약\n')
    end = text.index('\n키워드:', start)
    abstract = '''
GTX-A 개통으로 기존 광역버스뿐 아니라 GTX를 이용하여 서울로 이동하는 경로도 선택할 수 있게 되었다. 본 연구는 이러한 변화 속에서 서울로 직접 향하는 광역버스의 승차 변화와 GTX역 연계버스 이용을 함께 살펴보았다. 운정중앙역·킨텍스역·대곡역 권역을 대상으로 국토교통부 지역별 교통카드이용 합성데이터(2024년 10월 17일, 2025년 11월 6일)를 승차건수로 집계하고, 광역버스 노선·정류장 구성이 유지된 250m 격자 126개를 선정하였다. 하루 전체와 출근시간대의 기초통계 및 순위상관분석은 전체 126개 격자를 대상으로 하였으며, 광역버스 승차 변화량의 회귀분석은 두 시간대 모두 동일한 113개 격자를 대상으로 수행하였다. 분석 결과, 광역버스 승차건수는 하루 전체에서 22.4%, 출근시간대에서 26.2% 감소하였다. 광역버스 회귀분석에서는 두 시간대 모두 GTX역까지의 보행시간이 짧고 GTX 경쟁 목적지 비율이 높은 지역일수록 승차 변화량이 낮게 나타났다. GTX역 연계버스는 개통 후 하루 전체 1,015건, 출근시간대 646건이 관측되었으며, 출근시간대 이용의 75.5%가 운정중앙역 권역에서 나타났다. 같은 격자의 광역버스 승차 변화량과 연계버스 승차건수를 연결한 결과, 하루 전체와 출근시간대 모두 유의한 음의 순위상관관계가 나타났다(각각 ρ = −0.359, ρ = −0.290, 모두 p < .001). 권역별로는 운정중앙역과 대곡역에서 두 시간대 모두 유의한 음의 관계가 확인되었다. 이는 광역버스 승차가 더 크게 감소하거나 증가폭이 작은 지역에서 개통 후 GTX역 연계버스 이용이 많은 경향을 의미하며, 기존 광역버스 통행의 일부가 GTX 연계통행으로 전환되었을 가능성을 살펴볼 간접 근거가 된다.
'''
    text = text[:start] + abstract + text[end:]
    changes.append('요약: 연계버스 회귀 결과 삭제, 광역버스 회귀 113개·기초통계와 순위상관 126개 명시')
    replace_once('키워드: GTX-A, 광역버스, 연계버스, 교통카드 합성데이터, 250m 격자, 환승 연계, 다중회귀분석',
                 '키워드: GTX-A, 광역버스, 연계버스, 교통카드 합성데이터, 250m 격자, 다중회귀분석, 순위상관분석',
                 '키워드: 핵심 분석인 순위상관분석 반영')

    replace_paragraph('한편, 광역버스 승차 변화만으로는 GTX-A 개통 이후',
        '한편, 광역버스 승차 변화만으로는 GTX-A 개통 이후 이용자의 이동 경로가 어떻게 달라졌는지 알기 어렵다. 이에 GTX역으로 향하는 마을·시내버스 이용을 함께 살펴볼 필요가 있다. 이러한 버스는 역에서 떨어진 지역과 GTX역을 연결하는 수단으로 활용될 수 있다. 본 연구의 사전 인터뷰에서도 마을버스나 승용차를 이용하여 GTX역에 접근하는 사례가 확인되었다. 따라서 GTX역 연계버스가 어느 지역과 시간대에서 많이 이용되는지 파악하고, 광역버스 승차 변화와 같은 공간에서 연결해 살펴볼 필요가 있다.',
        '1.1: 연계버스 요인 분석 예고를 이용 분포와 두 지표의 관계로 수정')
    replace_paragraph('본 연구는 GTX-A 북부 구간의 운정중앙역·킨텍스역·대곡역 권역을 대상으로,',
        '본 연구는 GTX-A 북부 구간의 운정중앙역·킨텍스역·대곡역 권역을 대상으로, 개통 전후 광역버스 승차 변화와 개통 후 GTX역 연계버스 이용 특성을 분석하고 두 지표 사이의 공간적 관계를 살펴보는 것을 목적으로 한다. 하루 전체와 출근시간대를 구분하여 광역버스 승차 변화의 관련 요인과 연계버스 이용 분포를 파악하고, 권역별 접근·환승 여건을 함께 검토하고자 한다. 구체적인 연구 목적은 다음과 같다.',
        '1.2 도입: 관련 요인 분석 대상을 광역버스로 명확히 한정')
    replace_paragraph('둘째, GTX역 연계버스 이용 특성과 관련 요인을 분석한다.',
        '둘째, GTX역 연계버스 이용 특성을 분석한다. 개통 후 연계버스의 전체 및 권역별·시간대별 이용 규모와 격자별 분포를 파악한다. 또한 GTX역까지의 보행시간 구간별 이용 수준을 비교하여 역으로 향하는 버스 이용이 어느 지역에서 많이 나타나는지 살펴본다.',
        '1.2 둘째: 연계버스 회귀 목적 삭제, 기초통계와 보행시간 구간별 비교 유지')
    replace_paragraph('셋째, 광역버스 승차 변화와 GTX역 연계버스 이용 사이의 공간적 관계를 분석한다.',
        '셋째, 광역버스 승차 변화와 GTX역 연계버스 이용 사이의 공간적 관계를 분석한다. 같은 격자의 두 지표를 연결하여 광역버스 변화량이 낮은 지역에서 개통 후 연계버스 이용이 많은 경향이 나타나는지 확인하고, 하루 전체와 출근시간대 및 권역별로 비교한다. 이를 통해 기존 광역버스 통행의 일부가 GTX 연계통행으로 전환되었을 가능성을 간접적으로 살펴보고자 한다.',
        '1.2 셋째: 동일 격자의 관계와 간접 근거에 초점')
    replace_paragraph('검토한 선행연구는 역 접근성과 통행거리가 교통수단 선택과 관련됨을 보여주고,',
        '검토한 선행연구는 역 접근성과 통행거리가 교통수단 선택과 관련됨을 보여주고, GTX 도입에 따른 대중교통 접근성 변화를 평가하였다. 본 연구는 이러한 논의를 바탕으로 개통 후 GTX역으로 향하는 마을·시내버스 승차기록을 분석하여, 접근교통이 어느 지역과 시간대에서 많이 이용되는지 살펴본다. GTX역까지의 보행시간 구간별 이용을 비교하고, 연계버스 승차건수를 광역버스 승차 변화량과 같은 공간에서 연결한다. 이를 통해 역 접근성에 관한 논의를 실제 역 접근교통 이용과 기존 광역버스 변화의 관계로 이어가고자 한다.',
        '1.4.2: 연계버스의 인구·토지이용·기존 철도역 변수 검증 예고 삭제')
    replace_paragraph('본 연구는 교통카드 합성데이터와 지역·교통 특성 자료를 활용하여',
        '본 연구는 교통카드 합성데이터와 지역·교통 특성 자료를 활용하여 GTX-A 북부 구간 개통 전후 광역버스 승차 변화와 GTX역 연계버스 이용의 공간적 관계를 분석하였다. 연구 절차는 (1) 데이터 수집, (2) 데이터 전처리 및 분석격자·변수 구축, (3) 광역버스 승차 변화의 기초통계 및 다중회귀분석, (4) GTX역 연계버스 이용의 기초통계 및 시각화, (5) 같은 공간에서 두 지표의 순위상관분석, (6) 권역별 이용 특성 및 접근·환승 여건 비교로 구성하였다.',
        '2장 도입: 광역버스 회귀 → 연계버스 기초통계 → 두 지표 관계로 절차 수정')
    replace_once('| 기존 철도역 위치                          | 국토교통부                           | 반경 1km 내 기존 철도역 수 산출                        |\n', '',
                 '표 1: 제외한 연계버스 회귀에만 사용하던 철도역 수 자료 행 삭제')

    replace_paragraph('시간대와 버스 유형에 따른 결과를 같은 지역에서 비교하기 위해,',
        '두 시간대의 광역버스 회귀분석 결과를 같은 지역에서 비교하기 위해, 하루 전체와 출근시간대 모형에 동일한 113개 격자를 사용하였다. 해당 격자는 운정중앙역 권역 55개, 킨텍스역 권역 26개, 대곡역 권역 32개이다. 따라서 광역버스 회귀분석 결과는 GTX-A 개통 전 출근시간대 광역버스 승차가 관측된 지역의 특성으로 해석하였다.',
        '2.2.3: 버스 유형 간 공통 표본 설명 삭제, 광역버스 두 시간대의 공통 113개 유지')
    replace_once('| GTX역 연계버스 승차건수 회귀분석               | 하루 전체·출근시간대 |   113개 |\n', '',
                 '표 8: 연계버스 회귀 표본 행 삭제')
    replace_paragraph('이와 같은 방법으로 추출한 기록은 승차정류장 좌표를 기준으로 250m 격자에 배정하였다.',
        '이와 같은 방법으로 추출한 기록은 승차정류장 좌표를 기준으로 250m 격자에 배정하였다. 이후 격자별 GTX역 연계버스 승차건수를 산출하였다. 승차건수는 광역버스 분석과 동일하게 합성 이용인원 값을 합산하지 않고 교통카드 기록 한 행을 1건으로 집계하였다. 분석 대상 격자에 해당 기록이 없는 경우에는 승차건수를 0건으로 처리하였다. 구축한 전체 126개 격자의 자료는 권역별·시간대별·보행시간 구간별 기초통계와 광역버스 승차 변화량과의 순위상관분석에 활용하였다.',
        '2.2.4: 연계버스 회귀 113개 설명 삭제, 전체 126개 기초통계·순위상관으로 정리')
    replace_paragraph('본 연구는 광역버스 승차 변화와 GTX역 연계버스 이용의 관련 요인을 분석하기 위해',
        '본 연구는 광역버스 승차 변화와 관련된 요인을 분석하기 위해 GTX역 접근성, 인구·토지이용 및 교통 특성 변수를 구축하였다. 각 변수는 최종 선정된 126개 분석격자의 식별번호를 기준으로 결합하였다. 교통카드 기록에서 산출하는 GTX 경쟁 목적지 비율과 평균 버스 통행시간은 하루 전체와 출근시간대에 맞춰 각각 계산하였다. 변수별 정의와 산출 기준은 <표 12>와 같다.',
        '2.2.5 도입: 변수 구축 목적을 광역버스 회귀로 수정')
    table_start = text.index('| 변수                 | 정의 및 산출 기준')
    table_end = text.index('\n\nGTX역 보행시간은', table_start)
    new_table = '''| 변수 | 정의 및 산출 기준 | 단위·변환 |
| --- | --- | --- |
| GTX역 보행시간 | 격자 중심점에서 가장 가까운 GTX역까지의 도보 경로 소요시간 | 분, ln(1+x) |
| 20~50대 인구 | 격자별 20~50대 인구(2024년 10월) | 명 |
| 건축물 연면적 | 격자별 건축물 연면적의 합 | 천㎡, ln(1+x) |
| 주거지역 비율 | 격자별 주거지역 면적의 비율 | % |
| GTX 경쟁 목적지 비율 | GTX-A 개통 전 광역버스 하차기록 중 서울역·연신내역 반경 1km 이내 하차기록 비율 | % |
| 평균 버스 통행시간 | 격자별 서울행 광역버스 평균 통행시간 | 분 |
| IC 접근성 | 격자별 최근접 고속도로 IC까지의 도로거리 | km |

표 12 광역버스 회귀분석에 사용한 지역·교통 특성 변수'''
    text = text[:table_start] + new_table + text[table_end:]
    changes.append('표 12: 적용 모형 열과 연계버스 전용 변수 2개 삭제, 광역버스 독립변수 7개 유지')
    replace_paragraph('인구는 국토정보플랫폼의 연령별 격자 자료에서',
        '인구는 국토정보플랫폼의 연령별 격자 자료에서 20대·30대·40대·50대 인구를 합산하여 구축하였다. 분석격자 중심점이 포함된 원자료 격자의 인구 값을 연결하였으며, 고양시와 파주시 경계에서 인구가 구분되어 제공되는 경우에는 두 지역의 값을 합산하였다. GTX-A 개통 전 지역 특성을 반영하기 위해 2024년 10월 자료를 사용하였다.',
        '인구 설명: 연계버스 회귀에만 쓰던 2025년 인구 설명 삭제')
    replace_paragraph('기존 철도역 수는 국토교통부 철도역 위치자료를 활용하여', '',
        '변수 설명: 연계버스 회귀 전용 기존 철도역 수 산출 문단 삭제')
    replace_paragraph('GTX역 연계버스 모형에는 권역별 특성을 고려하기 위해', '',
        '변수 설명: 운정중앙 권역 더미 문단 삭제')
    replace_paragraph('GTX역 보행시간은 OpenRouteService의 도보 경로정보를 이용하여',
        'GTX역 보행시간은 OpenRouteService의 도보 경로정보를 이용하여 산출하였다. 격자 중심점에서 가장 가까운 GTX역까지의 보행 가능한 경로를 기준으로 소요시간을 계산하여 GTX역 접근성을 나타내는 지표로 활용하였다. 이 값은 연계버스의 보행시간 구간별 이용 비교에도 사용하였다.',
        '보행시간 설명: 연계버스 기초통계에서도 사용하는 범위 유지')
    replace_paragraph('마지막으로 <그림 1>에 제시한 GTX역 보행시간과 건축물 연면적의 원자료 분포에서',
        '마지막으로 <그림 1>에 제시한 GTX역 보행시간과 건축물 연면적의 원자료 분포에서 치우침을 줄이기 위해 자연로그 변환(ln(1+x))을 적용하였다. 건축물 연면적은 천㎡ 단위로 환산한 후 로그 변환하였다. 인구, 주거지역 비율, GTX 경쟁 목적지 비율, 평균 버스 통행시간 및 IC 접근성은 원 단위를 유지하였다. 이와 같이 구축한 변수는 하루 전체와 출근시간대의 광역버스 승차 변화량 모형에 적용하였다.',
        '변수 변환 설명: 기존 철도역 수·더미 및 연계버스 모형 언급 삭제')
    # Only remove extra blank lines left by deleted paragraphs in this section.
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    replace_paragraph('본 연구에서는 분석 목적에 따라 두 개의 회귀모형을 구성하였다.',
        '본 연구에서는 GTX-A 개통 전후 광역버스 승차건수 변화량을 종속변수로 설정하여, 승차 변화와 관련된 지역·교통 특성을 분석하였다. 하루 전체와 출근시간대의 모형을 각각 추정하고, 독립변수의 계수 방향과 통계적 유의성을 검토하였다.',
        '2.3.2: 연계버스 회귀모형 설명 삭제, 광역버스 두 시간대 모형만 설명')
    replace_paragraph('변수 변환은 앞서 설명한 기준을 적용하였으며, 두 버스의',
        '변수 변환은 앞서 설명한 기준을 적용하였으며, 두 시간대의 광역버스 모형은 동일한 113개 격자를 대상으로 추정하고 상수항을 포함하였다. 분석 결과는 회귀계수와 p값, 결정계수 및 수정된 결정계수를 기준으로 검토하였으며, 통계적 유의성은 유의수준 5%를 기준으로 판단하였다. 구체적인 독립변수와 가설, 시간대별 추정 결과는 3장에서 제시한다.',
        '2.3.2 표본 설명: 두 버스 공통 표본에서 광역버스 시간대별 동일 표본으로 수정')

    # Preserve the newly aligned 3.3.1 and all original broad-bus results verbatim.
    start = text.index('#### 3.3.2 ')
    end = text.index('## 4. ', start)
    sections = [RESULTS / '3_3_2_본문.md', RESULTS / '3_3_3_본문.md', RESULTS / '3_4_본문.md']
    text = text[:start] + '\n\n'.join(p.read_text().strip() for p in sections) + '\n\n' + text[end:]
    changes.append('3장: 연계버스 회귀 절 삭제, 기초통계 3.3.2~3.3.3 작성, 순위상관을 3.4로 옮겨 전체·권역별 결과 작성')

    # Regenerate the complete contents list from the edited body's actual headings.
    body_start = text.index('## 1. ')
    body = text[body_start:]
    entries = []
    for m in re.finditer(r'^(#{2,4}) (.+)$', body, flags=re.M):
        depth = len(m.group(1)) - 2
        entries.append('  ' * depth + '- ' + m.group(2))
    toc_start = text.index('## 목차\n')
    text = text[:toc_start] + '## 목차\n\n' + '\n'.join(entries) + '\n\n' + body
    changes.append('목차: 실제 본문과 일치하도록 재작성, 기존 3.5 → 3.4 및 하위 절 번호 정리')
    assert '연계버스 모형' not in text
    assert '연계버스 회귀분석' not in text
    assert '두 버스의 회귀분석' not in text
    assert '공통 113개' not in text
    assert '2025년 10월 자료' not in text
    assert '운정중앙 권역 더미' not in text
    assert '기존 철도역 수' not in text
    assert not re.search(r'(?m)^#{2,4} 3\.5', text)
    assert '### 3.4 광역버스 승차 변화와 GTX역 연계버스 이용의 관계' in text
    assert text.count('#### 3.3.1 ') == 1
    # The original source file and all broad-bus results remain byte-for-byte intact.
    def original_block(s, start, end):
        return s[s.index(start):s.index(end, s.index(start))]
    assert original_block(text, '## 3. 분석 결과', '### 3.3 ') == original_block(original, '## 3. 분석 결과', '### 3.3 ')
    assert original_block(text, '#### 3.3.1 ', '#### 3.3.2 ') == original_block(original, '#### 3.3.1 ', '#### 3.3.2 ')
    assert text[text.index('## 4. '):] == original[original.index('## 4. '):]
    TARGET.write_text(text)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'manuscript_changes.json').write_text(json.dumps({
        'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': digest,
        'target': str(TARGET.relative_to(ROOT)), 'source_unchanged': True,
        'changes': changes,
    }, ensure_ascii=False, indent=2))
    print(TARGET)
    print('Original unchanged; broad-bus results and aligned section 3.3.1 preserved verbatim.')
    for change in changes:
        print('-', change)


if __name__ == '__main__':
    main()
