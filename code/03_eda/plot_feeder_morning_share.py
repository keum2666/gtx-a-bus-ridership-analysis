"""3.3.1: 개통 후 연계버스 하루 전체 승차 중 출근시간대의 비중."""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def create_figure(show=True):
    data = pd.read_csv(ROOT / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    base = pd.read_csv(ROOT / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv')
    assert len(data) == len(base) == 126
    assert data['셀 ID'].is_unique and base['셀 ID'].is_unique
    assert set(data['셀 ID']) == set(base['셀 ID'])
    counts = data[['GTX역행 2025', 'GTX역행 2025 출근']]
    assert counts.notna().all().all() and counts.ge(0).all().all()
    assert counts['GTX역행 2025 출근'].le(counts['GTX역행 2025']).all()
    np.testing.assert_array_equal(counts, counts.round())
    total = int(counts['GTX역행 2025'].sum())
    morning = int(counts['GTX역행 2025 출근'].sum())
    other = total - morning
    assert (total, morning, other) == (1015, 646, 369)

    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/Library/Fonts/NanumGothicBold.ttf'),
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]:
        if path.is_file():
            fm.fontManager.addfont(str(path))
            family = fm.FontProperties(fname=str(path)).get_name()
            break
    else:
        raise FileNotFoundError('한글 글꼴을 찾지 못했습니다.')

    def value_label(pct):
        return f'{pct:.1f}%\n{int(round(pct * total / 100)):,}건'

    with plt.rc_context({'font.family': family, 'font.weight': 'bold',
                         'pdf.fonttype': 42, 'axes.unicode_minus': False}):
        fig, ax = plt.subplots(figsize=(9.8, 6.3))
        _, _, labels = ax.pie(
            [morning, other], labels=['출근시간대\n(06:00~09:59)', '그 외 시간대'],
            colors=['#E9A23B', '#315A78'], startangle=90, counterclock=True,
            autopct=value_label, pctdistance=.60, labeldistance=1.10,
            wedgeprops={'edgecolor': 'white', 'linewidth': 3},
            textprops={'fontsize': 18, 'fontweight': 'bold', 'color': '#181818'})
        for i, label in enumerate(labels):
            label.set_fontsize(22)
            label.set_linespacing(1.5)
            label.set_color('#202020' if i == 0 else 'white')
        ax.set_aspect('equal')
        fig.tight_layout()
        stem = ROOT / 'results/paper/figures/그림16_GTX역_연계버스_출근시간대_비중'
        stem.parent.mkdir(parents=True, exist_ok=True)
        for extension in ['png', 'pdf']:
            fig.savefig(stem.with_suffix('.' + extension), dpi=300, facecolor='white',
                        bbox_inches='tight', pad_inches=.15)
        if show:
            plt.show()
        else:
            plt.close(fig)
    print(f'하루 전체 {total:,}건 / 출근 {morning:,}건 ({morning / total * 100:.1f}%)'
          f' / 그 외 {other:,}건 ({other / total * 100:.1f}%)')
    return stem.with_suffix('.png')


if __name__ == '__main__':
    create_figure(show=False)
