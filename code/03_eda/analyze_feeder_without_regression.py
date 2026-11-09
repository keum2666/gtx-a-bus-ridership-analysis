"""연계버스 회귀 제외 원고용 기초통계·순위상관. 기존 원고·분석 결과는 덮어쓰지 않는다."""
from pathlib import Path
import json
import hashlib
import os

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/paper/no_feeder_regression'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(OUT / '.matplotlib'))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

ORDER = ['운정중앙', '킨텍스', '대곡']
COLORS = {'운정중앙': '#3264A8', '킨텍스': '#D18C32', '대곡': '#359475'}
HOURLY_COLORS = {'운정중앙': '#C45A88', '킨텍스': '#8A6446', '대곡': '#E9BFA3'}
HOURLY_FIGURE = '그림17_시간대별_GTX역_연계버스_승차건수_분홍갈색살구'
SOURCE = ROOT / 'results/analysis/feeder_bus/tables'


def load_data():
    base = pd.read_csv(ROOT / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv').set_index('셀 ID')
    data = pd.read_csv(SOURCE / 'H11a_격자별_공급구조_GTX역행.csv').set_index('셀 ID').reindex(base.index)
    hour = pd.read_csv(SOURCE / 'H10a_권역x시간대_광역vsGTX역행.csv')
    assert len(base) == len(data) == 126 and base.index.is_unique and data.index.is_unique
    assert data['권역'].eq(base['nearest_station']).all()
    np.testing.assert_array_equal(data['Δ광역'], base['board_2025'] - base['board_2024'])
    morning_reference = pd.read_csv(ROOT / 'results/paper/tables/3_1_3_격자별_승차건수_변화량.csv').set_index('셀 ID').reindex(base.index)
    np.testing.assert_array_equal(data['Δ광역 출근'], morning_reference['morning_2025'] - morning_reference['morning_2024'])
    assert np.isfinite(data[['GTX역행 2025', 'GTX역행 2025 출근', 'Δ광역', 'Δ광역 출근']]).all().all()
    assert data['GTX역행 2025 출근'].le(data['GTX역행 2025']).all()
    assert (data[['GTX역행 2025', 'GTX역행 2025 출근']] >= 0).all().all()
    assert data.groupby('권역').size().reindex(ORDER).tolist() == [63, 26, 37]
    hourly = hour.pivot(index='hour', columns='권역', values='GTX역행 2025').reindex(index=range(24), columns=ORDER).fillna(0).astype(int)
    np.testing.assert_array_equal(hourly.sum(), data.groupby('권역')['GTX역행 2025'].sum().reindex(ORDER))
    np.testing.assert_array_equal(hourly.loc[6:9].sum(), data.groupby('권역')['GTX역행 2025 출근'].sum().reindex(ORDER))
    data['보행시간(분)'] = base['walk_min']
    data['보행시간 구간'] = pd.cut(data['보행시간(분)'], [-np.inf, 20, 50, np.inf], right=True,
                                  labels=['20분 이하', '20분 초과 50분 이하', '50분 초과'])
    return base, data, hourly


def save_table(frame, name):
    frame.to_csv(OUT / (name + '.csv'), index=False, encoding='utf-8-sig')


def generate_statistics(data, hourly):
    h = hourly.copy()
    h['전체'] = h.sum(axis=1)
    h.index.name = '승차 시간대'
    save_table(h.reset_index(), '3_3_2_시간대별_연계버스_승차건수')
    dist, walk, cor = [], [], []
    periods = [('하루 전체', 'GTX역행 2025', 'Δ광역'), ('출근시간대', 'GTX역행 2025 출근', 'Δ광역 출근')]
    for region in ORDER + ['전체']:
        part = data if region == '전체' else data.loc[data['권역'].eq(region)]
        row = {'권역': region, '격자 수': len(part)}
        for period, col, delta in periods:
            v = part[col]
            row[period + ' 이용 격자 수'] = int(v.gt(0).sum())
            row[period + ' 이용 격자 비율(%)'] = float(v.gt(0).mean() * 100)
            row[period + ' 승차건수'] = int(v.sum())
            row[period + ' 격자당 평균'] = float(v.mean())
            row[period + ' 최대값'] = int(v.max())
            row[period + ' 중앙값'] = float(v.median())
            rho, p = spearmanr(part[delta], v, alternative='two-sided', nan_policy='raise')
            cor.append({'시간대': period, '권역': region, 'N': len(part), 'rho': float(rho), 'p': float(p)})
        dist.append(row)
    for band, part in data.groupby('보행시간 구간', observed=True):
        row = {'보행시간 구간': str(band), '격자 수': len(part)}
        for period, col, _ in periods:
            row[period + ' 승차건수'] = int(part[col].sum())
            row[period + ' 격자당 평균'] = float(part[col].mean())
        walk.append(row)
    distribution, walk, cor = pd.DataFrame(dist), pd.DataFrame(walk), pd.DataFrame(cor)
    save_table(distribution, '3_3_3_격자별_연계버스_이용분포')
    save_table(walk, '3_3_3_보행시간구간별_연계버스_이용')
    save_table(cor, '3_4_순위상관_전체와권역별')
    # Independent agreement with the results previously verified for the meeting deck.
    reference = ROOT / 'results/presentation/.meeting_build/correlation.csv'
    if reference.exists():
        ref = pd.read_csv(reference).set_index(['시간대', '권역']).sort_index()
        check = cor.set_index(['시간대', '권역']).sort_index()
        np.testing.assert_allclose(check[['rho', 'p']], ref[['rho', 'p']], atol=1e-12)
    assert distribution.iloc[-1]['하루 전체 이용 격자 수'] == 43
    assert distribution.iloc[-1]['출근시간대 이용 격자 수'] == 38
    assert walk['하루 전체 승차건수'].sum() == 1015
    assert walk['출근시간대 승차건수'].sum() == 646
    return distribution, walk, cor


def font_config():
    for path in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]:
        if path.is_file():
            fm.fontManager.addfont(str(path))
            return fm.FontProperties(fname=str(path)).get_name()
    raise FileNotFoundError('한글 글꼴을 찾지 못했습니다.')


def style_axis(ax):
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#DADADA', lw=.8, alpha=.65)
    ax.tick_params(labelsize=13, pad=7)
    for t in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        t.set_fontweight('bold')


def save_figure(fig, name):
    for suffix in ['png', 'pdf']:
        fig.savefig(OUT / f'{name}.{suffix}', dpi=300, facecolor='white', bbox_inches='tight', pad_inches=.15)
    plt.close(fig)


def hourly_figure(hourly):
    """그림 17만 재생성한다. 다른 그림·원고·통계 파일은 변경하지 않는다."""
    rc = {'font.family': font_config(), 'font.weight': 'bold', 'axes.labelweight': 'bold',
          'axes.titleweight': 'bold', 'axes.unicode_minus': False, 'pdf.fonttype': 42}
    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=(14.5, 5.8))
        x = np.arange(24); bottom = np.zeros(24)
        ax.axvspan(5.5, 9.5, color='#F8E9B9', alpha=.55, zorder=0)
        for region in ORDER:
            vals = hourly[region].to_numpy()
            ax.bar(x, vals, bottom=bottom, width=.68, color=HOURLY_COLORS[region], label=region + '역', zorder=3)
            bottom += vals
        for i in range(6, 10):
            ax.annotate(f'{int(bottom[i]):,}건', (i, bottom[i]), xytext=(0, 7), textcoords='offset points',
                        ha='center', va='bottom', fontsize=16, fontweight='bold')
        ax.set_xticks(x, [f'{i}시' for i in x])
        ax.set_ylim(0, bottom.max() * 1.23)
        ax.set_xlabel('승차 시간대', fontsize=16, labelpad=10)
        ax.set_ylabel('GTX역 연계버스 승차건수(건)', fontsize=16, labelpad=10)
        ax.legend(frameon=False, fontsize=15)
        style_axis(ax); fig.tight_layout()
        save_figure(fig, HOURLY_FIGURE)


def figures(data, hourly, walk):
    hourly_figure(hourly)
    rc = {'font.family': font_config(), 'font.weight': 'bold', 'axes.labelweight': 'bold',
          'axes.titleweight': 'bold', 'axes.unicode_minus': False, 'pdf.fonttype': 42}
    with plt.rc_context(rc):
        fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.8), sharey=True)
        labels = ['20분 이하', '20분 초과\n50분 이하', '50분 초과']
        for ax, period, color in zip(axes, ['하루 전체', '출근시간대'], ['#167D8D', '#8153A0']):
            vals = walk[period + ' 격자당 평균']
            bars = ax.bar(np.arange(3), vals, width=.55, color=color)
            ax.bar_label(bars, labels=[f'{v:.1f}건' for v in vals], padding=7, fontsize=17, fontweight='bold')
            ax.set_xticks(np.arange(3), labels)
            ax.set_title(period, fontsize=22, pad=18)
            ax.set_xlabel('GTX역까지 보행시간', fontsize=16, labelpad=12)
            ax.set_ylabel('격자당 평균 승차건수(건)', fontsize=16, labelpad=12)
            ax.set_ylim(0, walk['하루 전체 격자당 평균'].max() * 1.22)
            style_axis(ax)
        fig.tight_layout(w_pad=2.8)
        save_figure(fig, '그림18_보행시간구간별_연계버스_평균승차건수')

        fig, axes = plt.subplots(1, 2, figsize=(14.5, 6.2))
        for ax, period, delta, target in zip(axes, ['하루 전체', '출근시간대'],
                                           ['Δ광역', 'Δ광역 출근'], ['GTX역행 2025', 'GTX역행 2025 출근']):
            for region in ORDER:
                part = data.loc[data['권역'].eq(region)]
                ax.scatter(part[delta], part[target], s=52, color=COLORS[region],
                           edgecolors='white', linewidths=.45, alpha=.75, label=region + '역', zorder=3)
            ax.axvline(0, color='#777777', lw=1)
            ax.set_title(period, fontsize=22, pad=18)
            ax.set_xlabel('광역버스 승차건수 변화량(건)', fontsize=15, labelpad=12)
            ax.set_ylabel('GTX역 연계버스 승차건수(건)', fontsize=15, labelpad=12)
            ax.legend(frameon=False, fontsize=13, loc='upper right')
            style_axis(ax)
        fig.tight_layout(w_pad=2.8)
        save_figure(fig, '그림19_광역버스변화량과_연계버스승차건수')



def fmt_p(value):
    return '< .001' if value < .001 else f'{value:.3f}'


def build_sections(data, hourly, distribution, walk, cor):
    hour_all = hourly.sum(axis=1)
    assert int(hour_all.idxmax()) == 7 and int(hour_all.max()) == 294
    hour_rows = []
    for h in range(6, 10):
        vals = hourly.loc[h]
        hour_rows.append(f'| {h}시대 | {int(vals[ORDER[0]]):,}건 | {int(vals[ORDER[1]]):,}건 | {int(vals[ORDER[2]]):,}건 | {int(vals.sum()):,}건 |')
    vals = hourly.loc[6:9].sum()
    hour_rows.append(f'| 출근시간대 합계 | {int(vals[ORDER[0]]):,}건 | {int(vals[ORDER[1]]):,}건 | {int(vals[ORDER[2]]):,}건 | {int(vals.sum()):,}건 |')
    s332 = '''#### 3.3.2 시간대별 이용

개통 후 GTX역 연계버스 승차기록을 1시간 단위로 집계한 결과, 7시대에 294건으로 이용이 가장 많았다. 이는 하루 전체 1,015건의 29.0%에 해당한다. 6시대 124건, 8시대 159건, 9시대 69건을 포함하면 출근시간대 승차건수는 646건이었다(<표 25>).

| 승차 시간대 | 운정중앙역 | 킨텍스역 | 대곡역 | 전체 |
| --- | ---: | ---: | ---: | ---: |
''' + '\n'.join(hour_rows) + '''

표 25 GTX-A 개통 후 출근시간대의 권역별 GTX역 연계버스 승차건수

권역별로는 운정중앙역과 킨텍스역에서 7시대 이용이 가장 많았으며, 대곡역은 8시대에 가장 많았다. 특히 운정중앙역은 7시대에 238건이 관측되어 해당 시간대 전체 이용 294건의 81.0%를 차지하였다. 출근시간대 전체에서 확인한 운정중앙역의 이용 집중은 7시대에 더욱 뚜렷하게 나타났다.

<그림 17>은 하루 전체의 시간대별 승차건수를 권역별로 구분한 것이다. 노란색 배경은 출근시간대인 6~9시대를 나타낸다. 연계버스 이용은 오전에 집중되었으며, 이후 시간대의 이용 규모는 상대적으로 작았다. 다만 승차시각을 기준으로 구분한 결과이므로, 해당 기록이 모두 출근 목적의 통행이라고 해석하지는 않았다.

![시간대별 GTX역 연계버스 승차건수](../results/paper/no_feeder_regression/그림17_시간대별_GTX역_연계버스_승차건수_분홍갈색살구.png)

그림 17 GTX-A 개통 후 시간대별 GTX역 연계버스 승차건수
'''
    rows = []
    for _, r in distribution.iterrows():
        rows.append(f'| {r["권역"] + "역" if r["권역"] != "전체" else "전체"} | {r["격자 수"]}개 | {r["하루 전체 이용 격자 수"]}개({r["하루 전체 이용 격자 비율(%)"]:.1f}%) | {r["출근시간대 이용 격자 수"]}개({r["출근시간대 이용 격자 비율(%)"]:.1f}%) |')
    band_rows = []
    for _, r in walk.iterrows():
        band_rows.append(f'| {r["보행시간 구간"]} | {r["격자 수"]}개 | {r["하루 전체 승차건수"]:,}건 | {r["하루 전체 격자당 평균"]:.1f}건 | {r["출근시간대 승차건수"]:,}건 | {r["출근시간대 격자당 평균"]:.1f}건 |')
    s333 = '''#### 3.3.3 격자별·보행시간 구간별 이용 분포

전체 126개 격자 중 GTX역 연계버스 이용이 관측된 격자는 하루 전체 43개(34.1%), 출근시간대 38개(30.2%)였다. 나머지는 각각 83개와 88개로, 분석 기준일의 해당 시간대에 GTX역 연계버스 승차기록이 없었다. 이러한 격자도 0건으로 포함하여 이용이 나타난 지역과 나타나지 않은 지역을 함께 살펴보았다(<표 26>).

| 권역 | 분석격자 수 | 하루 전체 이용 격자 수(비율) | 출근시간대 이용 격자 수(비율) |
| --- | ---: | ---: | ---: |
''' + '\n'.join(rows) + '''

표 26 권역별 GTX역 연계버스 이용이 관측된 격자 수

운정중앙역은 하루 전체와 출근시간대 모두 21개 격자에서 이용이 관측되었다. 대곡역은 각각 13개와 12개, 킨텍스역은 9개와 5개였다. 앞서 운정중앙역의 승차건수가 많았던 것과 함께, 실제 이용이 관측된 격자의 분포도 확인할 수 있다. 이때 이용이 없는 격자는 해당 기준일에 추출 조건을 충족하는 기록이 없었다는 의미이며, 연계버스 노선이 없다는 뜻은 아니다.

GTX역까지의 보행시간을 세 구간으로 나누어 이용 규모를 비교하였다. 구간별 격자 수가 다르므로 승차건수 합계와 함께 격자당 평균을 제시하였다. 평균을 계산할 때에는 이용이 없는 격자도 포함하였다(<표 27>).

| GTX역 보행시간 | 격자 수 | 하루 전체 승차건수 | 하루 전체 격자당 평균 | 출근시간대 승차건수 | 출근시간대 격자당 평균 |
| --- | ---: | ---: | ---: | ---: | ---: |
''' + '\n'.join(band_rows) + '''

표 27 GTX역 보행시간 구간별 연계버스 이용 규모

승차건수 합계는 두 시간대 모두 20분 초과 50분 이하 구간에서 가장 많았다. 반면 격자당 평균은 20분 이하 구간에서 하루 전체 20.6건, 출근시간대 14.9건으로 가장 높았다. 50분 초과 구간의 평균은 각각 1.0건과 0.7건이었다(<그림 18>). 이는 분석 대상 격자에서 보행시간이 짧은 구간의 연계버스 이용이 상대적으로 많았음을 보여준다. 다만 구간별 권역 구성과 노선 공급 등도 함께 다르므로, 이 차이를 보행시간만의 영향으로 해석하지는 않았다.

![보행시간 구간별 연계버스 평균 승차건수](../results/paper/no_feeder_regression/그림18_보행시간구간별_연계버스_평균승차건수.png)

그림 18 GTX역 보행시간 구간별 연계버스의 격자당 평균 승차건수

이상의 기초통계에서는 연계버스 이용이 운정중앙역 권역과 출근시간대에 집중되어 있으며, 일부 격자에서 주로 관측되는 모습을 확인하였다. 다음 절에서는 이러한 이용 분포를 광역버스 승차 변화량과 같은 격자에서 연결하여 두 지표의 관계를 살펴보았다.
'''
    indexed = cor.set_index(['권역', '시간대'])
    overall = []
    for period in ['하루 전체', '출근시간대']:
        r = indexed.loc[('전체', period)]
        overall.append(f'| {period} | {int(r["N"])}개 | {r["rho"]:.3f} | {fmt_p(r["p"])} |')
    regional = []
    for region in ORDER:
        a, b = indexed.loc[(region, '하루 전체')], indexed.loc[(region, '출근시간대')]
        regional.append(f'| {region}역 | {int(a["N"])}개 | {a["rho"]:.3f} | {fmt_p(a["p"])} | {b["rho"]:.3f} | {fmt_p(b["p"])} |')
    s34 = '''### 3.4 광역버스 승차 변화와 GTX역 연계버스 이용의 관계

앞선 분석에서는 광역버스 승차 변화와 관련 요인을 살펴보고, GTX역 연계버스가 어느 지역과 시간대에서 많이 이용되는지 확인하였다. 이 절에서는 두 지표를 같은 격자에서 연결하여, 광역버스 변화량이 낮은 지역에서 개통 후 연계버스 이용이 많은 경향이 나타나는지 살펴보았다.

#### 3.4.1 하루 전체·출근시간대 순위상관분석

전체 126개 격자를 대상으로 스피어만 순위상관분석을 수행하였다. 하루 전체 광역버스 승차 변화량에는 하루 전체 연계버스 승차건수를, 출근시간대 변화량에는 같은 시간대의 연계버스 승차건수를 연결하였다. 연계버스 이용이 없는 격자도 0건으로 포함하였다.

분석 결과, 하루 전체에서 ρ = −0.359, 출근시간대에서 ρ = −0.290으로 나타났으며 두 결과 모두 유의수준 5%에서 통계적으로 유의하였다(<표 28>). 즉, 광역버스 승차가 더 크게 감소하거나 증가폭이 작은 격자일수록 개통 후 GTX역 연계버스 이용이 많은 경향을 보였다.

| 시간대 | 격자 수 | 스피어만 상관계수(ρ) | p값 |
| --- | ---: | ---: | ---: |
''' + '\n'.join(overall) + '''

표 28 광역버스 승차 변화량과 GTX역 연계버스 승차건수의 순위상관분석

두 지표의 격자별 분포는 <그림 19>와 같다. 가로축은 GTX-A 개통 후에서 개통 전을 뺀 광역버스 승차건수 변화량이며, 세로축은 개통 후 GTX역 연계버스 승차건수이다. 점 하나는 분석격자 하나를 나타내며, 같은 값을 갖는 격자는 점이 겹칠 수 있다.

![광역버스 승차 변화량과 GTX역 연계버스 승차건수의 관계](../results/paper/no_feeder_regression/그림19_광역버스변화량과_연계버스승차건수.png)

그림 19 같은 격자에서의 광역버스 승차 변화량과 GTX역 연계버스 승차건수

#### 3.4.2 권역별 순위상관분석

연계버스 이용이 운정중앙역 권역에 집중되어 있다는 점을 고려하여, 각 권역 안에서도 두 지표의 관계를 확인하였다. 권역별 분석은 운정중앙역 63개, 킨텍스역 26개, 대곡역 37개 격자를 대상으로 수행하였다(<표 29>).

| 권역 | 격자 수 | 하루 전체 ρ | p값 | 출근시간대 ρ | p값 |
| --- | ---: | ---: | ---: | ---: | ---: |
''' + '\n'.join(regional) + '''

표 29 권역별 광역버스 승차 변화량과 GTX역 연계버스 승차건수의 순위상관분석

운정중앙역 권역은 하루 전체와 출근시간대 모두 유의한 음의 관계를 보였다. 대곡역 권역에서도 두 시간대 모두 유의한 음의 관계가 나타났다. 반면 킨텍스역 권역에서는 계수의 방향은 음이었으나 두 시간대 모두 유의수준 5%에서 관계가 확인되지 않았다. 전체에서 관찰된 음의 관계가 운정중앙역뿐 아니라 대곡역 내부에서도 나타났다는 점을 확인할 수 있다.

대곡역은 출근시간대 광역버스 승차건수가 권역 전체에서 39건 증가했지만, 권역 내부에서는 광역버스 변화량이 낮은 격자일수록 연계버스 이용이 많은 경향을 보였다. 따라서 권역 전체의 증가·감소와 같은 권역 안의 격자별 관계를 함께 살펴볼 필요가 있다.

#### 3.4.3 하루 전체와 출근시간대의 관계 비교

하루 전체와 출근시간대 모두 광역버스 변화량과 GTX역 연계버스 이용 사이에 음의 관계가 나타났다. 권역별로도 운정중앙역과 대곡역은 두 시간대 모두 유의하였고, 킨텍스역은 두 시간대 모두 유의하지 않았다. 시간대별 이용 규모와 권역 비중에는 차이가 있었지만, 두 지표가 연결되는 방향에는 공통점이 있었다.

이 결과는 광역버스 승차 변화와 GTX역으로 향하는 버스 이용이 같은 공간에서 관련되어 나타났음을 보여준다. 기존 광역버스 통행의 일부가 GTX 연계통행으로 전환되었을 가능성을 살펴볼 간접 근거로 활용할 수 있다. 다만 순위상관에는 역 접근성과 인구·토지이용 등 다른 지역 특성의 영향도 함께 반영될 수 있으며, 기존 이용자가 실제로 GTX를 탔는지를 확인한 결과는 아니다.

특히 운정중앙역과 대곡역은 광역버스의 권역별 증감 방향이 다르면서도, 두 시간대 모두 권역 내부에서 음의 관계를 보였다. 다음 장에서는 두 권역의 보행시간 구간별 이용과 현장답사 내용을 연결하여, 서로 다른 접근·환승 여건에서 이러한 결과가 어떻게 나타났는지 살펴보았다.
'''
    for name, section in [('3_3_2_본문', s332), ('3_3_3_본문', s333), ('3_4_본문', s34)]:
        (OUT / (name + '.md')).write_text(section)


def main():
    base, data, hourly = load_data()
    distribution, walk, cor = generate_statistics(data, hourly)
    figures(data, hourly, walk)
    build_sections(data, hourly, distribution, walk, cor)
    inputs = [SOURCE / 'H11a_격자별_공급구조_GTX역행.csv', SOURCE / 'H10a_권역x시간대_광역vsGTX역행.csv',
              ROOT / 'data/final/gtx_a/S1_126격자_건수기준_기초표.csv']
    (OUT / 'data_lineage.json').write_text(json.dumps({
        'inputs': [{'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],
        'N': 126, 'morning_hours': [6, 7, 8, 9], 'day_total': 1015, 'morning_total': 646,
        'positive_grid_day': 43, 'positive_grid_morning': 38, 'correlations_match_existing': True,
        'regression_performed': False,
    }, ensure_ascii=False, indent=2))
    print(distribution.to_string(index=False))
    print(walk.round(3).to_string(index=False))
    print(cor.round(6).to_string(index=False))
    print('Saved new descriptive and Spearman results:', OUT)


if __name__ == '__main__':
    main()
