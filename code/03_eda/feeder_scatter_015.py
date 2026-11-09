"""015 산점도: 지정한 하차 정류장 두 곳의 26건 제외. 그림·분석표 파일 저장 없음."""
from pathlib import Path
import re
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REGIONS = ['운정중앙', '킨텍스', '대곡']
COLORS = {'운정중앙': '#C45A88', '킨텍스': '#888888', '대곡': '#8A6446'}
EXCLUDED_STOPS = {'4111411', '4111412'}


def load_corrected(root):
    root = Path(root)
    base = pd.read_csv(root / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv')
    reference = pd.read_csv(root / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv').set_index('셀 ID')
    cells = pd.read_csv(root / 'data/processed/gtx_a/16_새데이터_공급구조유지_250m격자.csv', dtype=str)
    normalize = lambda s: s.astype(str).str.replace('.0', '', regex=False).str.lstrip('0')
    stops_dir = root / 'data/processed/gtx_a/feeder_bus/stops'
    old = pd.read_csv(stops_dir / 'BusStop_20251106_파주고양서울일부.csv', dtype=str)
    new = pd.read_csv(stops_dir / '2025_신설정류장_좌표_GBIS.csv', dtype=str)
    names = pd.concat([pd.Series(new['정류장명'].values, index=normalize(new['정류장 ID'])),
                       pd.Series(old.sttn_nm.values, index=normalize(old.sttn_id))])
    names = names[~names.index.duplicated()]
    original_station_stops = set(names[names.str.contains('운정중앙역|킨텍스역|대곡역', na=False)].index)
    lookup = pd.DataFrame([(int(row['셀 ID']), sid.lstrip('0')) for _, row in cells.iterrows()
                           for sid in re.findall(r'\d{6,}', row['2025년 정류장 ID'])],
                          columns=['셀 ID', 'on'])
    assert not lookup['on'].duplicated().any()
    files = sorted(p for p in (root / 'data/raw/gtx_a/feeder_bus/transport_card').glob('경기_20251106_*.csv')
                   if p.stat().st_size > 10)
    assert files, '2025년 마을·시내버스 원자료를 찾을 수 없습니다.'
    raw = pd.concat([pd.read_csv(p, dtype=str, usecols=['opr_ymd', 'rte_id', 'ride_sttn_id', 'goff_sttn_id'])
                     for p in files], ignore_index=True)
    assert raw.opr_ymd.eq('20251106').all()
    raw['on'], raw['off'] = normalize(raw.ride_sttn_id), normalize(raw.goff_sttn_id)
    selected = raw.merge(lookup, on='on', how='inner', validate='many_to_one')
    selected = selected[selected['off'].isin(original_station_stops) &
                        ~selected['on'].isin(original_station_stops)].copy()
    data = base.set_index('셀 ID')[['nearest_station', 'board_2024', 'board_2025', 'change']].copy()
    data['기존 연계버스 승차건수'] = selected.groupby('셀 ID').size().reindex(data.index, fill_value=0)
    np.testing.assert_array_equal(data['기존 연계버스 승차건수'], reference.loc[data.index, 'GTX역행 2025'])
    np.testing.assert_array_equal(data.change, data.board_2025-data.board_2024)
    removed = selected[selected['off'].isin(EXCLUDED_STOPS)].copy()
    corrected = selected[~selected['off'].isin(EXCLUDED_STOPS)].copy()
    data['연계버스 승차건수'] = corrected.groupby('셀 ID').size().reindex(data.index, fill_value=0)
    assert len(data) == 126 and data.index.is_unique
    assert len(selected) == 1015 and len(removed) == 26 and len(corrected) == 989
    assert corrected.rte_id.nunique() == 21
    assert data['연계버스 승차건수'].gt(0).sum() == 41
    assert data.groupby('nearest_station').size().reindex(REGIONS).tolist() == [63, 26, 37]
    corrected['권역'] = corrected['셀 ID'].map(data.nearest_station)
    rows = []
    for region in [*REGIONS, '전체']:
        part = data if region == '전체' else data[data.nearest_station.eq(region)]
        records = corrected if region == '전체' else corrected[corrected['권역'].eq(region)]
        rho, p = spearmanr(part.change, part['연계버스 승차건수'], alternative='two-sided')
        rows.append({'권역': region, '분석 격자': len(part),
                     '승차가 있는 격자': int(part['연계버스 승차건수'].gt(0).sum()),
                     '승차건수': int(part['연계버스 승차건수'].sum()),
                     '노선 수': records.rte_id.nunique(), 'rho': float(rho), 'p': float(p)})
    stats = pd.DataFrame(rows).set_index('권역')
    assert stats.loc[REGIONS, '승차건수'].tolist() == [672, 109, 208]
    assert stats.loc[REGIONS, '승차가 있는 격자'].tolist() == [21, 8, 12]
    assert stats.loc[REGIONS, '노선 수'].tolist() == [9, 12, 4]
    removed['하차정류장'] = removed['off'].map(names)
    return data.sort_index(), stats, removed


def make_scatter(data, stats):
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.ticker import MaxNLocator
    font = 'DejaVu Sans'
    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc'), Path('C:/Windows/Fonts/malgunbd.ttf')]:
        if path.is_file():
            fm.fontManager.addfont(str(path)); font = fm.FontProperties(fname=str(path)).get_name(); break
    with plt.rc_context({'font.family': font, 'font.weight': 'bold', 'axes.labelweight': 'bold',
                          'axes.titleweight': 'bold', 'axes.unicode_minus': False}):
        fig, axes = plt.subplots(1, 3, figsize=(21, 8), sharey=True, facecolor='white')
        fig.subplots_adjust(left=.105, right=.98, bottom=.24, top=.75, wspace=.24)
        rng = np.random.default_rng(42)
        # 실제 값은 유지한다. 겹친 점을 보이게 하는 작은 위치 조정은 표시용 열에만 적용.
        shown = data.copy()
        shown['표시x'] = shown.change + rng.uniform(-.75, .75, len(shown))
        shown['표시y'] = np.abs(shown['연계버스 승차건수'] + rng.uniform(-.22, .22, len(shown)))
        ymax = max(80, int(np.ceil((shown['연계버스 승차건수'].max()+2)/20)*20))
        for ax, region in zip(axes, REGIONS):
            part = shown[shown.nearest_station.eq(region)]
            row = stats.loc[region]
            xmin, xmax = int(part.change.min()), int(part.change.max())
            # 모든 격자를 표시한다. 0건도 동일한 색의 점으로 유지한다.
            ax.scatter(part['표시x'], part['표시y'], s=105, color=COLORS[region],
                       alpha=.76, edgecolors='white', linewidths=.75, zorder=3)
            padding = max(1.2, (xmax-xmin)*.035)
            ax.set_xlim(xmin-padding, xmax+padding)
            ax.set_ylim(-1.8, ymax)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
            ax.set_yticks(np.arange(0, ymax+1, 20))
            ax.axvline(0, color='#BFBFBF', lw=.85, zorder=1)
            ax.axhline(0, color='#BFBFBF', lw=.85, zorder=1)
            ax.set_axisbelow(True); ax.grid(axis='y', color='#E4E4E4', lw=.8)
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines[['left', 'bottom']].set_linewidth(1.1)
            ax.tick_params(labelsize=20, pad=8, colors='#111')
            for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
                label.set_fontweight('bold')
            ptext = 'p < .001' if row['p'] < .001 else f'p = {row["p"]:.3f}'
            ax.set_title(f'{region}역 ({len(part)}개)\nρ = {row["rho"]:.3f} · {ptext}',
                         fontsize=25, pad=20, linespacing=1.45)
            ax.set_xlabel('광역버스 승차 변화량(건)', fontsize=21, labelpad=15)
            assert len(ax.collections[0].get_offsets()) == len(part)
            assert part['표시x'].between(*ax.get_xlim()).all()
            assert part['표시y'].between(*ax.get_ylim()).all()
        axes[0].set_ylabel('개통 후 GTX역 연계버스\n승차건수(건)', fontsize=23, labelpad=16)
        fig.suptitle('하루 전체 · 광역버스 승차 변화와 GTX역 연계버스 이용', fontsize=27, y=.97)
        fig.text(.5, .07, 'X축: 권역별 자료 범위 · Y축: 공통 범위 · 점 위치만 소폭 조정 · 0건 포함 126개 격자로 계산',
                 ha='center', fontsize=14, color='#444')
        assert sum(len(ax.collections[0].get_offsets()) for ax in axes) == 126
    return fig
