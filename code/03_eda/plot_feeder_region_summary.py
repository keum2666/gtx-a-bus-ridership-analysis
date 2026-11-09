"""3.3.1: GTX-A 개통 후 연계버스의 126개 격자 전체·권역별 이용 집계."""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
ORDER = ['운정중앙', '킨텍스', '대곡']


def create_figure(show=True):
    data = pd.read_csv(ROOT / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    base = pd.read_csv(ROOT / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv')
    assert len(data) == 126 and data['셀 ID'].is_unique
    assert set(data['셀 ID']) == set(base['셀 ID'])
    region = data.set_index('셀 ID')['권역'].sort_index()
    pd.testing.assert_series_equal(region, base.set_index('셀 ID')['nearest_station'].sort_index(),
                                   check_names=False)
    day, morning = 'GTX역행 2025', 'GTX역행 2025 출근'
    assert data[[day, morning]].notna().all().all()
    assert data[[day, morning]].ge(0).all().all()
    assert (data[morning] <= data[day]).all()
    np.testing.assert_array_equal(data[[day, morning]], data[[day, morning]].round())
    summary = data.groupby('권역').agg(
        격자수=('셀 ID', 'size'), 하루전체=(day, 'sum'), 출근시간대=(morning, 'sum')
    ).reindex(ORDER).astype(int)
    assert summary['격자수'].tolist() == [63, 26, 37]
    summary.loc['전체'] = summary.sum()
    assert summary.loc['전체', ['하루전체', '출근시간대']].tolist() == [1015, 646]
    summary['출근시간대 비율(%)'] = 100 * summary['출근시간대'] / summary['하루전체']
    summary['하루전체 권역비중(%)'] = 100 * summary['하루전체'] / summary.loc['전체', '하루전체']
    summary['출근시간대 권역비중(%)'] = 100 * summary['출근시간대'] / summary.loc['전체', '출근시간대']
    tables = ROOT / 'results/paper/tables'
    figures = ROOT / 'results/paper/figures'
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    summary.to_csv(tables / '3_3_1_연계버스_전체_권역별_이용.csv', encoding='utf-8-sig')

    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/Library/Fonts/NanumGothicBold.ttf'),
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]:
        if path.is_file():
            fm.fontManager.addfont(str(path))
            family = fm.FontProperties(fname=str(path)).get_name()
            break
    else:
        raise FileNotFoundError('한글 글꼴을 찾지 못했습니다.')
    with plt.rc_context({'font.family': family, 'font.weight': 'bold',
                         'axes.labelweight': 'bold', 'axes.titleweight': 'bold',
                         'axes.unicode_minus': False, 'pdf.fonttype': 42}):
        fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.8), sharey=True)
        limit = summary.loc[ORDER, ['하루전체', '출근시간대']].to_numpy().max() * 1.22
        for ax, (column, title, color) in zip(axes, [
                ('하루전체', '하루 전체', '#5476A3'),
                ('출근시간대', '출근시간대', '#9BCB4B')]):
            values = summary.loc[ORDER, column]
            bars = ax.bar(np.arange(3), values, width=.54, color=color, zorder=3)
            ax.bar_label(bars, labels=[f'{int(v):,}건' for v in values], padding=7,
                         fontsize=17, fontweight='bold', color='#111111')
            ax.set_title(title, fontsize=23, pad=20)
            ax.set_xticks(range(3), [f'{station}역' for station in ORDER])
            ax.set_ylim(0, limit)
            ax.set_ylabel('승차건수(건)', fontsize=16, labelpad=12)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
            ax.tick_params(axis='both', labelsize=15, pad=8)
            ax.set_axisbelow(True)
            ax.grid(axis='y', color='#DADADA', linewidth=.8, alpha=.75)
            ax.spines[['top', 'right']].set_visible(False)
            for text in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
                text.set_fontweight('bold')
        fig.tight_layout(w_pad=3)
        stem = figures / '그림15_권역별_GTX역_연계버스_승차건수_파랑연두'
        for ext in ['png', 'pdf']:
            fig.savefig(f'{stem}.{ext}', dpi=300, facecolor='white',
                        bbox_inches='tight', pad_inches=.15)
        if show:
            plt.show()
        else:
            plt.close(fig)
    print(summary.round(2).to_string())
    print('저장:', stem.with_suffix('.png'))
    return summary


if __name__ == '__main__':
    create_figure(show=False)
