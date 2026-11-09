"""그림 19 비교안: 전체·권역별 스피어만 상관계수. 기존 산점도는 유지한다."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/paper/no_feeder_regression'
os.environ.setdefault('MPLCONFIGDIR', str(OUT / '.matplotlib'))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_feeder_without_regression import load_data, font_config


def main():
    _, data, _ = load_data()
    summary = pd.read_csv(OUT / '3_4_순위상관_전체와권역별.csv')
    regions = ['전체', '운정중앙', '킨텍스', '대곡']
    periods = [('하루 전체', 'Δ광역', 'GTX역행 2025', '#167D8D', .15),
               ('출근시간대', 'Δ광역 출근', 'GTX역행 2025 출근', '#D47A25', -.15)]
    # 원자료로 재검산하며 연계버스 0건도 포함한다.
    for period, delta, feeder, _, _ in periods:
        for region in regions:
            part = data if region == '전체' else data[data['권역'].eq(region)]
            rho, p = spearmanr(part[delta], part[feeder])
            saved = summary.loc[summary['시간대'].eq(period) & summary['권역'].eq(region)].iloc[0]
            assert int(saved['N']) == len(part)
            np.testing.assert_allclose([rho, p], saved[['rho', 'p']].to_numpy(dtype=float), atol=1e-12)

    rc = {'font.family': font_config(), 'font.weight': 'bold',
          'axes.labelweight': 'bold', 'axes.unicode_minus': False,
          'pdf.fonttype': 42}
    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=(11.8, 6.5))
        ys = np.arange(len(regions))[::-1]
        ax.axhspan(2.55, 3.5, color='#F2F5F6', zorder=0)
        for y in ys:
            ax.axhline(y, color='#E7E7E7', lw=.8, zorder=0)
        ax.axvline(0, color='#656565', lw=1.3, zorder=1)
        for period, _, _, color, offset in periods:
            for idx, (region, y) in enumerate(zip(regions, ys)):
                row = summary.loc[summary['시간대'].eq(period) & summary['권역'].eq(region)].iloc[0]
                significant = row['p'] < .05
                ax.scatter(row['rho'], y + offset, s=155,
                           facecolors=color if significant else 'white',
                           edgecolors=color, linewidths=2.2, zorder=3,
                           label=period if idx == 0 else None)
                ax.annotate(f'{row["rho"]:.3f}'.replace('-', '−'),
                            (row['rho'], y + offset), xytext=(13, 0),
                            textcoords='offset points', va='center',
                            fontsize=15, fontweight='bold', color=color)
        labels = []
        for region in regions:
            n = len(data) if region == '전체' else int(data['권역'].eq(region).sum())
            labels.append(f'{region if region == "전체" else region + "역"}  ({n}개)')
        ax.set_yticks(ys, labels, fontsize=16, fontweight='bold')
        ax.set_ylim(-.5, 3.5)
        ax.set_xlim(-.60, .10)
        ticks = np.arange(-.6, .101, .1)
        ax.set_xticks(ticks, ['0' if abs(v) < 1e-8 else f'{v:.1f}'.replace('-', '−') for v in ticks])
        ax.set_xlabel('스피어만 순위상관계수(ρ)', fontsize=17, labelpad=15)
        ax.tick_params(axis='y', length=0, pad=16)
        ax.tick_params(axis='x', labelsize=14, pad=8)
        for label in ax.get_xticklabels():
            label.set_fontweight('bold')
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.spines['bottom'].set_color('#888888')
        ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.03),
                  ncol=2, frameon=False, fontsize=16, handletextpad=.6,
                  columnspacing=2.5)
        fig.subplots_adjust(left=.24, right=.97, bottom=.17, top=.87)
        for suffix in ['png', 'pdf']:
            path = OUT / f'그림19_비교안_전체권역별_순위상관계수.{suffix}'
            fig.savefig(path, dpi=300, facecolor='white', bbox_inches='tight', pad_inches=.2)
            print(path)
        plt.close(fig)


if __name__ == '__main__':
    main()
