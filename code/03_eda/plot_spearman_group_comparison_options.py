"""하루 전체 순위상관·연계버스 승차 유무 비교. 이미지 파일을 저장하지 않는다."""
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr
from statsmodels.stats.multitest import multipletests


ROOT = Path(__file__).resolve().parents[2]
X, Y = 'Δ광역', 'GTX역행 2025'
REGIONS = ['운정중앙', '킨텍스', '대곡']
COLORS = {'전체': '#315D86', '운정중앙': '#C45A88',
          '킨텍스': '#888888', '대곡': '#8A6446'}
XLIM = (-200, 50)
YLIM = (-2.2, 100)
GROUP_LIMITS = (-225, 75)


def load_data(root=ROOT):
    root = Path(root)
    data = pd.read_csv(
        root / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv',
        encoding='utf-8-sig')
    base = pd.read_csv(root / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv',
                       encoding='utf-8-sig')
    assert len(data) == 126 and data['셀 ID'].is_unique
    assert data[[X, Y]].notna().all().all() and data[Y].ge(0).all()
    assert data[Y].eq(0).sum() == 83 and data[Y].gt(0).sum() == 43
    assert data[Y].sum() == 1015 and data[X].sum() == -1593
    np.testing.assert_array_equal(data[Y], data[Y].round())
    assert set(data['셀 ID']) == set(base['셀 ID'])
    pd.testing.assert_series_equal(
        data.set_index('셀 ID')['권역'].sort_index(),
        base.set_index('셀 ID')['nearest_station'].sort_index(), check_names=False)
    np.testing.assert_array_equal(
        data.set_index('셀 ID')[X].sort_index(),
        base.set_index('셀 ID')['change'].sort_index())
    data = data.sort_values('셀 ID').copy()
    rng = np.random.default_rng(42)
    data['표시x'] = data[X] + rng.uniform(-.85, .85, len(data))
    data['표시y'] = np.abs(data[Y] + rng.uniform(-.24, .24, len(data)))
    return data


def calculate_stats(data):
    correlations, groups, tests = [], [], []
    for region in ['전체', *REGIONS]:
        part = data if region == '전체' else data.loc[data['권역'].eq(region)]
        rho, p = spearmanr(part[X], part[Y])
        correlations.append({'권역': region, '격자수': len(part),
                             '0건 격자': int(part[Y].eq(0).sum()),
                             'rho': float(rho), 'p': float(p)})
        no = part.loc[part[Y].eq(0), X].to_numpy()
        yes = part.loc[part[Y].gt(0), X].to_numpy()
        result = mannwhitneyu(yes, no, alternative='two-sided',
                              method='asymptotic', use_continuity=True)
        tests.append({'권역': region, '0건 격자': len(no), '1건 이상 격자': len(yes),
                      'U': float(result.statistic), 'p': float(result.pvalue),
                      '순위양분상관': float(2 * result.statistic / (len(no) * len(yes)) - 1)})
        for name, array in [('0건', no), ('1건 이상', yes)]:
            groups.append({'권역': region, '집단': name, '격자수': len(array),
                           '평균': float(np.mean(array)), '중앙값': float(np.median(array)),
                           'Q1': float(np.quantile(array, .25)),
                           'Q3': float(np.quantile(array, .75))})
    adjusted = multipletests([t['p'] for t in tests[1:]], method='holm')[1]
    for test, p in zip(tests[1:], adjusted):
        test['권역별 Holm 보정 p'] = float(p)
    return pd.DataFrame(correlations), pd.DataFrame(groups), pd.DataFrame(tests)


def _style():
    family = 'DejaVu Sans'
    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/Library/Fonts/NanumGothicBold.ttf'),
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]:
        if path.exists():
            fm.fontManager.addfont(str(path))
            family = fm.FontProperties(fname=str(path)).get_name()
            break
    return plt.rc_context({'font.family': family, 'font.weight': 'bold',
                           'axes.labelweight': 'bold', 'axes.titleweight': 'bold',
                           'axes.unicode_minus': False})


def _ptext(p):
    return 'p < .001' if p < .001 else f'p = {p:.3f}'


def _region(region):
    return '전체' if region == '전체' else f'{region}역'


def rank_scatter_figure(data, correlations):
    """권역 안에서 작은 값부터 평균순위를 부여한다. 표시 위치를 옮기지 않는다."""
    with _style():
        fig, axes = plt.subplots(1, 3, figsize=(21, 7.6),
                                 sharex=True, sharey=True, facecolor='white')
        fig.subplots_adjust(left=.08, right=.98, bottom=.25, top=.73, wspace=.23)
        for ax, region in zip(axes, REGIONS):
            part = data.loc[data['권역'].eq(region)]
            ranks = part[[X, Y]].rank(method='average', ascending=True)
            stat = correlations.set_index('권역').loc[region]
            # 평균순위의 피어슨 상관과 원자료의 스피어만 상관은 일치해야 한다.
            np.testing.assert_allclose(ranks[X].corr(ranks[Y]), stat['rho'], atol=1e-12)
            ax.scatter(ranks[X], ranks[Y], s=110, color=COLORS[region],
                       alpha=.78, edgecolors='white', linewidths=.7, zorder=3)
            assert len(ax.collections[0].get_offsets()) == len(part)
            ax.set_xlim(0, 65)
            ax.set_ylim(0, 65)
            ax.set_xticks(np.arange(0, 61, 10))
            ax.set_yticks(np.arange(0, 61, 10))
            ax.set_axisbelow(True)
            ax.grid(color='#E5E5E5', linewidth=.8)
            ax.spines[['top', 'right']].set_visible(False)
            ax.tick_params(labelsize=20, pad=9, colors='#111111')
            ax.set_title(f'{_region(region)} ({len(part)}개)\n'
                         f'ρ = {stat["rho"]:.3f} · {_ptext(stat["p"])}',
                         fontsize=25, pad=20, linespacing=1.45)
            ax.set_xlabel('광역버스 승차 변화량 순위', fontsize=21, labelpad=15)
        axes[0].set_ylabel('개통 후 GTX역 연계버스\n승차건수 순위', fontsize=23, labelpad=16)
        fig.suptitle('하루 전체 · 권역별 순위 산점도', fontsize=27, y=.97)
        fig.text(.5, .045, '권역별로 작은 값부터 순위 부여 · 같은 값은 평균순위 · 0건 포함 · 표시 위치 조정 없음',
                 ha='center', fontsize=14, color='#444444')
    return fig


def _draw_count_scatter(ax, part, region, stat):
    """X=광역버스 변화량(권역별 최소~최대), Y=연계버스 건수(공통 범위)."""
    from matplotlib.ticker import MaxNLocator
    minimum, maximum = int(part[X].min()), int(part[X].max())
    color = COLORS[region]
    for zero in [True, False]:
        selected = part.loc[part[Y].eq(0) == zero]
        shown_x = np.clip(selected['표시x'], minimum, maximum)
        ax.scatter(shown_x, selected['표시y'], s=90 if zero else 115,
                   facecolors='none' if zero else color,
                   edgecolors=color if zero else 'white', alpha=.80,
                   linewidths=1.2 if zero else .8, zorder=3, clip_on=False)
    ax.set_xlim(minimum, maximum)
    ax.set_ylim(YLIM)
    gap = (maximum - minimum) * .10
    ticks = MaxNLocator(nbins=4, integer=True).tick_values(minimum, maximum)
    interior = [v for v in ticks if minimum + gap <= v <= maximum - gap]
    ax.set_xticks([minimum, *interior, maximum])
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.minorticks_off()
    ax.axvline(0, color='#BBBBBB', linewidth=.9, zorder=0)
    ax.axhline(0, color='#BBBBBB', linewidth=.9, zorder=0)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#DDDDDD', linewidth=.8)
    ax.spines[['top', 'right']].set_visible(False)
    ax.spines[['left', 'bottom']].set_linewidth(1.2)
    ax.tick_params(labelsize=20, pad=9, colors='#111111')
    for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        label.set_fontweight('bold')
    ax.set_title(f'{_region(region)} ({int(stat["격자수"])}개)\n'
                 f'ρ = {stat["rho"]:.3f} · {_ptext(stat["p"])}',
                 fontsize=25, fontweight='bold', pad=20, linespacing=1.45)
    ax.set_xlabel('광역버스 승차 변화량(건)', fontsize=21,
                  fontweight='bold', labelpad=15)
    assert ax.get_xlim() == (minimum, maximum)
    assert ax.get_ylim() == YLIM
    assert sum(len(c.get_offsets()) for c in ax.collections) == len(part)
    assert part[Y].between(*YLIM).all()


def correlation_figures(data, stats):
    """X축은 권역별 광역버스 변화량 최소~최대, Y축은 공통 연계버스 건수 범위로 출력한다."""
    with _style():
        fig, axes = plt.subplots(1, 3, figsize=(21, 8.0), sharey=True)
        fig.subplots_adjust(left=.075, right=.98, bottom=.27, top=.75, wspace=.23)
        for ax, region in zip(axes, REGIONS):
            part = data.loc[data['권역'].eq(region)]
            stat = stats.set_index('권역').loc[region]
            _draw_count_scatter(ax, part, region, stat)
        axes[0].set_ylabel('개통 후 GTX역 연계버스\n승차건수(건)', fontsize=23,
                           fontweight='bold', labelpad=16)
        fig.suptitle('하루 전체 · 광역버스 승차 변화와 GTX역 연계버스 이용',
                     fontsize=26, fontweight='bold', y=.975)
        fig.text(.5, .045, 'X축: 권역별 최솟값~최댓값 · Y축: 공통 범위 · 지터는 표시 위치에만 적용 · 126개 원자료로 순위상관 계산',
                 ha='center', fontsize=14, fontweight='bold', color='#444444')
    return [('권역별 지터', fig)]


def group_figures(data, group_stats, tests):
    """세 권역 박스플롯을 한 장으로 출력한다. 지터 그래프와 글꼴·글자 크기를 맞춘다."""
    with _style():
        fig, axes = plt.subplots(1, 3, figsize=(21, 8.0), sharey=True)
        fig.subplots_adjust(left=.075, right=.98, bottom=.30, top=.75, wspace=.23)
        for ax, region in zip(axes, REGIONS):
            part = data.loc[data['권역'].eq(region)]
            arrays = [part.loc[part[Y].eq(0), X].to_numpy(),
                      part.loc[part[Y].gt(0), X].to_numpy()]
            test = tests.set_index('권역').loc[region]
            color = COLORS[region]
            boxes = ax.boxplot(
                arrays, positions=[0, 1], widths=.48, whis=(0, 100),
                patch_artist=True, showfliers=False,
                medianprops={'color': '#111111', 'linewidth': 3},
                whiskerprops={'color': '#555555', 'linewidth': 2},
                capprops={'color': '#555555', 'linewidth': 2})
            for i, box in enumerate(boxes['boxes']):
                box.set_facecolor('#DDDDDD' if i == 0 else mcolors.to_rgba(color, .65))
                box.set_edgecolor('#777777' if i == 0 else color)
                box.set_linewidth(2)
            ax.axhline(0, color='#AAAAAA', linewidth=1)
            ax.set_axisbelow(True)
            ax.grid(axis='y', color='#DDDDDD', linewidth=.8)
            ax.set_ylim(GROUP_LIMITS)
            ax.set_yticks([-200, -150, -100, -50, 0, 50])
            ax.set_xlim(-.55, 1.55)
            ax.set_xticks([0, 1], [f'승차 X\n{len(arrays[0])}개 격자',
                                   f'승차 O\n{len(arrays[1])}개 격자'])
            ax.set_xlabel('GTX역 연계버스 승차 여부', fontsize=21,
                          fontweight='bold', labelpad=16)
            ax.tick_params(axis='both', labelsize=20, pad=9, colors='#111111')
            for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
                label.set_fontweight('bold')
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines[['left', 'bottom']].set_linewidth(1.2)
            ax.set_title(f'{_region(region)} ({len(part)}개)\n' + _ptext(test['p']),
                         fontsize=25, fontweight='bold', pad=20, linespacing=1.45)
        axes[0].set_ylabel('광역버스 승차 변화량(건)', fontsize=23,
                           fontweight='bold', labelpad=16)
        fig.suptitle('하루 전체 · 연계버스 승차 유무에 따른 광역버스 승차 변화',
                     fontsize=26, fontweight='bold', y=.975)
        fig.text(.5, .075, 'Mann–Whitney U 양측 검정 · p값은 보정 전',
                 ha='center', fontsize=14, fontweight='bold', color='#444444')
        fig.text(.5, .035, '상자: 가운데 50% · 검은 선: 중앙값 · 수염: 최소~최대',
                 ha='center', fontsize=14, fontweight='bold', color='#444444')
    return [('권역별 박스플롯', fig)]


def combined_figure(data, correlations, tests):
    """위 지터·아래 박스플롯을 권역별로 정렬한 2행 3열 통합 그림."""
    with _style():
        fig, axes = plt.subplots(2, 3, figsize=(21, 12.8),
                                 sharey='row', facecolor='white')
        fig.subplots_adjust(left=.075, right=.98, bottom=.20, top=.85,
                            hspace=.826, wspace=.23)
        fig.text(.075, .96, '순위상관분석', fontsize=25,
                 fontweight='bold', va='top', color='#111111')
        fig.text(.98, .96, '하루 전체', fontsize=23,
                 fontweight='bold', va='top', ha='right', color='#111111')
        fig.text(.075, .52, '연계버스 승차 유무 비교', fontsize=25,
                 fontweight='bold', va='top', color='#111111')
        for j, region in enumerate(REGIONS):
            part = data.loc[data['권역'].eq(region)]
            color = COLORS[region]
            stat = correlations.set_index('권역').loc[region]
            test = tests.set_index('권역').loc[region]
            ax = axes[0, j]
            _draw_count_scatter(ax, part, region, stat)

            ax = axes[1, j]
            arrays = [part.loc[part[Y].eq(0), X].to_numpy(),
                      part.loc[part[Y].gt(0), X].to_numpy()]
            boxes = ax.boxplot(
                arrays, positions=[0, 1], widths=.48, whis=(0, 100),
                patch_artist=True, showfliers=False,
                medianprops={'color': '#111111', 'linewidth': 3},
                whiskerprops={'color': '#555555', 'linewidth': 2},
                capprops={'color': '#555555', 'linewidth': 2})
            for i, box in enumerate(boxes['boxes']):
                box.set_facecolor('#DDDDDD' if i == 0 else mcolors.to_rgba(color, .65))
                box.set_edgecolor('#777777' if i == 0 else color)
                box.set_linewidth(2)
            ax.axhline(0, color='#AAAAAA', linewidth=1)
            ax.set_axisbelow(True)
            ax.grid(axis='y', color='#DDDDDD', linewidth=.8)
            ax.set_ylim(GROUP_LIMITS)
            ax.set_yticks([-200, -150, -100, -50, 0, 50])
            ax.set_xlim(-.55, 1.55)
            ax.set_xticks([0, 1], [f'승차 X\n{len(arrays[0])}개 격자',
                                   f'승차 O\n{len(arrays[1])}개 격자'])
            ax.set_xlabel('GTX역 연계버스 승차 여부', fontsize=21,
                          fontweight='bold', labelpad=15)
            ax.tick_params(axis='both', labelsize=20, pad=9, colors='#111111')
            for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
                label.set_fontweight('bold')
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines[['left', 'bottom']].set_linewidth(1.2)
            ax.set_title(_ptext(test['p']),
                         fontsize=25, fontweight='bold', pad=20, linespacing=1.45)
            assert not ax.collections and not ax.texts
        axes[0, 0].set_ylabel('개통 후 GTX역 연계버스\n승차건수(건)',
                              fontsize=23, fontweight='bold', labelpad=16)
        axes[1, 0].set_ylabel('광역버스 승차 변화량(건)',
                              fontsize=23, fontweight='bold', labelpad=16)
        fig.text(.5, .045,
                 '순위상관: X축은 권역별 변화량 최솟값~최댓값 · Y축은 공통 승차건수 범위 · 지터는 표시 위치에만 적용',
                 ha='center', fontsize=13, fontweight='bold', color='#444444')
        fig.text(.5, .015,
                 '박스플롯: 가운데 50% · 검은 선: 중앙값 · 수염: 최소~최대 · Mann–Whitney U 양측 검정 p값은 보정 전',
                 ha='center', fontsize=13, fontweight='bold', color='#444444')
    return fig


def outlier_filtered_correlation_figure(data):
    """비교용: 권역별 X의 1.5×IQR 이상치 제외 후 순위상관을 다시 계산한다."""
    kept, rows = [], []
    for region in REGIONS:
        part = data.loc[data['권역'].eq(region)].copy()
        q1, q3 = part[X].quantile([.25, .75])
        lower, upper = q1 - 1.5 * (q3-q1), q3 + 1.5 * (q3-q1)
        chosen = part.loc[part[X].between(lower, upper)].copy()
        rho, p = spearmanr(chosen[X], chosen[Y])
        rows.append({'권역': region, '원래 격자수': len(part), '제외 격자수': len(part)-len(chosen),
                     '격자수': len(chosen), 'X 최솟값': int(chosen[X].min()),
                     'X 최댓값': int(chosen[X].max()), 'IQR 하한': lower, 'IQR 상한': upper,
                     'rho': float(rho), 'p': float(p)})
        kept.append(chosen)
    table = pd.DataFrame(rows)
    selected = pd.concat(kept, ignore_index=True)
    fig = correlation_figures(selected, table)[0][1]
    fig._suptitle.set_text('하루 전체 · X축 이상치 제외 비교')
    fig.texts[-1].set_text('권역별 광역버스 변화량의 1.5×IQR 밖 격자 제외 · 남은 자료로 ρ·p 재계산 · Y축 공통')
    for ax, region in zip(fig.axes, REGIONS):
        row = table.set_index('권역').loc[region]
        ax.text(.5, -.37, f'제외 {int(row["제외 격자수"])}개 / 원래 {int(row["원래 격자수"])}개',
                transform=ax.transAxes, ha='center', fontproperties=ax.xaxis.label.get_fontproperties(),
                fontsize=15, fontweight='bold', color='#444444')
    return fig, table

