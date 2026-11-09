"""동일 113개 격자의 광역버스 회귀계수와 95% 신뢰구간 비교 그림."""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / 'results/paper/figures'
SOURCE = ROOT / 'results/analysis/regression/common_113'
VARIABLES = ['GTX역 보행시간', '20~50대 인구', '건축물 연면적',
             '주거지역 비율', 'GTX 경쟁 목적지 비율', '평균 버스 통행시간', 'IC 접근성']
PERIODS = ['하루 전체', '출근시간대']
COLORS = {'하루 전체': '#167D8D', '출근시간대': '#8153A0'}


def create_figure(show=True):
    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/Library/Fonts/NanumGothicBold.ttf'),
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]:
        if path.is_file():
            fm.fontManager.addfont(str(path))
            family = fm.FontProperties(fname=str(path)).get_name()
            break
    else:
        raise FileNotFoundError('한글 글꼴을 찾지 못했습니다.')
    coef = pd.read_csv(SOURCE / '광역버스_동일113격자_회귀계수.csv')
    coef = coef.loc[coef['모형'].isin([f'{p} 113개' for p in PERIODS])].copy()
    coef['시간대'] = coef['모형'].str.replace(' 113개', '', regex=False)
    coef = coef.set_index(['변수', '시간대'])
    stats = pd.read_csv(SOURCE / '광역버스_동일113격자_모형적합도.csv')
    assert stats.loc[stats['모형'].isin([f'{p} 113개' for p in PERIODS]), '격자 수'].eq(113).all()
    selected = coef.loc[VARIABLES]
    assert len(selected) == 14 and selected.index.is_unique
    assert (selected['95% CI 하한'] < selected['계수']).all()
    assert (selected['95% CI 상한'] > selected['계수']).all()
    np.testing.assert_array_equal(
        selected['p값'].lt(.05),
        selected['95% CI 하한'].gt(0) | selected['95% CI 상한'].lt(0))

    with plt.rc_context({'font.family': family, 'font.size': 13,
                         'font.weight': 'bold', 'axes.labelweight': 'bold',
                         'axes.titleweight': 'bold', 'axes.unicode_minus': False,
                         'pdf.fonttype': 42, 'savefig.dpi': 300}):
        fig, axes = plt.subplots(4, 2, figsize=(14.8, 11.7))
        for variable, ax in zip(VARIABLES, axes.flat):
            part = coef.loc[variable].reindex(PERIODS)
            lower = min(0, float(part['95% CI 하한'].min()))
            upper = max(0, float(part['95% CI 상한'].max()))
            span = upper - lower
            ax.set_xlim(lower - .11 * span, upper + .11 * span)
            ax.axvline(0, color='#606060', lw=1.1, ls=(0, (4, 3)), zorder=1)
            for period, y in zip(PERIODS, [.73, .10]):
                row = part.loc[period]
                value = float(row['계수'])
                errors = np.array([[value - row['95% CI 하한']],
                                   [row['95% CI 상한'] - value]])
                significant = row['p값'] < .05
                ax.errorbar(value, y, xerr=errors, fmt='o', markersize=8.5,
                            color=COLORS[period], ecolor=COLORS[period],
                            markerfacecolor=COLORS[period] if significant else 'white',
                            markeredgewidth=1.9, elinewidth=2.1, capsize=5, capthick=1.7,
                            zorder=3)
                decimals = 4 if variable == '20~50대 인구' else 3
                ax.annotate(f'{value:+.{decimals}f}', (value, y), xytext=(0, 12),
                            textcoords='offset points', ha='center', va='bottom',
                            fontsize=13.5, fontweight='bold', color=COLORS[period])
            ax.set_title(variable, fontsize=18, loc='left', pad=15, color='#161616')
            ax.set_yticks([.73, .10], PERIODS)
            ax.set_ylim(-.25, 1.18)
            ax.tick_params(axis='y', length=0, labelsize=13.5, pad=8)
            ax.tick_params(axis='x', labelsize=11.5, length=4, colors='#333333')
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
            formatter = ScalarFormatter(useOffset=False)
            formatter.set_scientific(False)
            ax.xaxis.set_major_formatter(formatter)
            ax.set_axisbelow(True)
            ax.grid(axis='x', color='#E6E6E6', linewidth=.8)
            ax.spines[['top', 'left', 'right']].set_visible(False)
            ax.spines['bottom'].set_color('#777777')
            for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
                label.set_fontweight('bold')

        key = axes.flat[-1]
        key.axis('off')
        key.text(.02, .96, '그림 읽는 방법', transform=key.transAxes,
                 fontsize=18, va='top', fontweight='bold')
        handles = [
            Line2D([0], [0], marker='o', markersize=8, linestyle='none',
                   markerfacecolor='#454545', markeredgecolor='#454545', label='유의함 (p < .05)'),
            Line2D([0], [0], marker='o', markersize=8, linestyle='none',
                   markerfacecolor='white', markeredgewidth=1.7, markeredgecolor='#454545',
                   label='유의하지 않음 (p ≥ .05)'),
            Line2D([0], [0], color='#454545', linewidth=2, marker='|', markersize=11,
                   label='가로선: 95% 신뢰구간'),
        ]
        key.legend(handles=handles, frameon=False, loc='upper left',
                   bbox_to_anchor=(0, .77), fontsize=12.5, labelspacing=.8,
                   borderaxespad=0)
        key.text(.02, -.02, '변수별 가로축 범위가 다름', transform=key.transAxes,
                 fontsize=12, color='#505050', va='top')
        fig.subplots_adjust(left=.11, right=.97, top=.96, bottom=.065,
                            hspace=.86, wspace=.44)
        fig.supxlabel('회귀계수', fontsize=15, fontweight='bold', y=.015)
        FIGURES.mkdir(parents=True, exist_ok=True)
        stem = FIGURES / '그림15_광역버스_시간대별_회귀계수_비교'
        for suffix in ['.png', '.pdf']:
            fig.savefig(stem.with_suffix(suffix), dpi=300, facecolor='white',
                        bbox_inches='tight', pad_inches=.18)
        if show:
            plt.show()
        else:
            plt.close(fig)
    print('저장:', stem.with_suffix('.png'))
    return stem.with_suffix('.png')


if __name__ == '__main__':
    create_figure()
