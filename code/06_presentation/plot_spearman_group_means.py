"""순위상관 발표 보조 그림: 변화 구분별 연계버스 이용 평균(0건 포함)."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/presentation/figures'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'results/paper/no_feeder_regression/.matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


def main():
    d = pd.read_csv(ROOT / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    assert len(d) == 126 and d['셀 ID'].is_unique
    assert d['GTX역행 2025 출근'].notna().all()
    d['변화 구분'] = np.select([d['Δ광역 출근'] < 0, d['Δ광역 출근'] > 0], ['감소', '증가'], default='유지')
    regions, groups = ['운정중앙', '킨텍스', '대곡'], ['감소', '유지', '증가']
    stats = d.groupby(['권역', '변화 구분'])['GTX역행 2025 출근'].agg(격자수='size', 승차건수='sum', 격자당평균='mean')
    assert stats['격자수'].sum() == 126 and stats['승차건수'].sum() == 646
    stats.reset_index().to_csv(OUT / '순위상관_보조그림_변화구분별_연계버스_출근시간대.csv', index=False, encoding='utf-8-sig')
    path = Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    fm.fontManager.addfont(str(path))
    family = fm.FontProperties(fname=str(path)).get_name()
    colors = ['#D73027', '#BDBDBD', '#2166AC']
    with plt.rc_context({'font.family': family, 'font.weight': 'bold', 'axes.labelweight': 'bold',
                         'axes.titleweight': 'bold', 'axes.unicode_minus': False, 'pdf.fonttype': 42}):
        fig, axes = plt.subplots(1, 3, figsize=(16, 6.6), sharey=True)
        upper = stats['격자당평균'].max() * 1.30
        for ax, region in zip(axes, regions):
            a = stats.loc[region].reindex(groups)
            bars = ax.bar(range(3), a['격자당평균'], color=colors, width=.59, zorder=3)
            ax.bar_label(bars, labels=[f'{v:.1f}건' for v in a['격자당평균']], padding=11, fontsize=27, fontweight='bold', color='#111111')
            ax.set_xticks(range(3), [f'{g}\n({int(n)}개)' for g,n in zip(groups,a['격자수'])])
            ax.set_title(region+'역', fontsize=29, pad=26)
            ax.set_xlabel('광역버스 승차 변화', fontsize=23, labelpad=20)
            ax.set_ylim(0, upper)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.tick_params(axis='x', labelsize=24, pad=12)
            ax.tick_params(axis='y', labelsize=22, pad=9)
            for t in [*ax.get_xticklabels(), *ax.get_yticklabels()]: t.set_fontweight('bold')
            ax.spines[['top','right']].set_visible(False)
            ax.set_axisbelow(True)
            ax.grid(axis='y', color='#DDDDDD', lw=.8, alpha=.8)
        axes[0].set_ylabel('격자당 평균 연계버스\n승차건수(건)', fontsize=23, labelpad=17)
        fig.tight_layout(w_pad=3.0)
        stem = OUT / '순위상관_보조그림_광역버스변화별_연계버스_출근시간대'
        for ext in ['png','pdf']:
            fig.savefig(stem.with_suffix('.'+ext), dpi=300, facecolor='white', bbox_inches='tight', pad_inches=.18)
        plt.close(fig)
    print(stats.round(3).to_string())
    print(stem.with_suffix('.png'))


if __name__ == '__main__': main()
