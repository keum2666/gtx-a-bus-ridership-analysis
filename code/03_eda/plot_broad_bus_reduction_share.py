"""3.1.2: 종일 승차 순감소량 중 출근시간대가 차지하는 비중을 원그래프로 표시."""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def create_figure(show=True):
    base = pd.read_csv(ROOT / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv')
    feeder = pd.read_csv(ROOT / 'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    assert len(base) == len(feeder) == 126
    assert base['셀 ID'].is_unique and feeder['셀 ID'].is_unique
    assert set(base['셀 ID']) == set(feeder['셀 ID'])
    assert feeder[['Δ광역', 'Δ광역 출근', 'Δ광역 그 외']].notna().all().all()
    np.testing.assert_allclose(feeder['Δ광역'], feeder['Δ광역 출근'] + feeder['Δ광역 그 외'])
    reduction = int(base['board_2024'].sum() - base['board_2025'].sum())
    morning = -int(feeder['Δ광역 출근'].sum())
    other = -int(feeder['Δ광역 그 외'].sum())
    assert (reduction, morning, other) == (1593, 812, 781)
    assert morning + other == reduction

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
        return f'{pct:.1f}%\n{int(round(pct * reduction / 100)):,}건'

    with plt.rc_context({'font.family': family, 'font.weight': 'bold',
                         'pdf.fonttype': 42, 'axes.unicode_minus': False}):
        fig, ax = plt.subplots(figsize=(9.8, 6.3))
        wedges, texts, values = ax.pie(
            [morning, other], labels=['출근시간대\n(06:00~09:59)', '그 외 시간대'],
            colors=['#E9A23B', '#315A78'], startangle=90, counterclock=True,
            autopct=value_label, pctdistance=.60, labeldistance=1.10,
            wedgeprops={'edgecolor': 'white', 'linewidth': 3},
            textprops={'fontsize': 18, 'fontweight': 'bold', 'color': '#181818'})
        for i, text in enumerate(values):
            text.set_fontsize(22)
            text.set_linespacing(1.5)
            text.set_color('#202020' if i == 0 else 'white')
        ax.set_aspect('equal')
        fig.tight_layout()
        figures = ROOT / 'results/paper/figures'
        figures.mkdir(parents=True, exist_ok=True)
        stem = figures / '그림03_광역버스_감소량_출근시간대_비중'
        for ext in ['png', 'pdf']:
            fig.savefig(f'{stem}.{ext}', dpi=300, facecolor='white',
                        bbox_inches='tight', pad_inches=.15)
        if show:
            plt.show()
        else:
            plt.close(fig)
    print(f'전체 순감소 {reduction:,}건 / 출근 {morning:,}건 ({morning/reduction*100:.1f}%)'
          f' / 그 외 {other:,}건 ({other/reduction*100:.1f}%)')
    return stem.with_suffix('.png')


if __name__ == '__main__':
    create_figure(show=False)
