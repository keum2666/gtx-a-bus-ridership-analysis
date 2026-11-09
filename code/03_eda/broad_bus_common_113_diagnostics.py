"""공통 113개 광역버스 모형의 VIF와 3.2.3 결과표를 생성한다."""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/analysis/regression/common_113'
OUTPUT = ROOT / 'results/paper/tables'
OUTPUT.mkdir(parents=True, exist_ok=True)
data = pd.read_csv(SOURCE / '공통113격자_분석자료.csv').set_index('셀 ID')
stored = pd.read_csv(SOURCE / '광역버스_동일113격자_회귀계수.csv')
columns = ['log_walk', 'pop_20_50', 'log_floor', '주거지역 비율(%)',
           'competing_share', 'bus_time_mean', 'ic_access']
labels = ['GTX역 보행시간', '20~50대 인구', '건축물 연면적', '주거지역 비율',
          'GTX 경쟁 목적지 비율', '평균 버스 통행시간', 'IC 접근성']
assert len(data) == 113 and data.index.is_unique
rows, stats, coefficients = [], [], []
for period in ['하루 전체', '출근시간대']:
    x = data[columns].copy()
    if period == '출근시간대':
        x['competing_share'] = data['출근_경쟁목적지비율']
        x['bus_time_mean'] = data['출근_평균버스통행시간']
    design = sm.add_constant(x, has_constant='add')
    assert np.isfinite(design.to_numpy()).all()
    assert np.linalg.matrix_rank(design) == len(columns) + 1
    # VIF의 보조회귀에도 상수항을 포함하고, 상수항 자체의 VIF는 보고하지 않는다.
    for j, (key, label) in enumerate(zip(columns, labels), 1):
        vif = variance_inflation_factor(design.to_numpy(), j)
        standardized = sm.add_constant((x - x.mean()) / x.std(ddof=0))
        np.testing.assert_allclose(
            vif, variance_inflation_factor(standardized.to_numpy(), j), atol=1e-10)
        rows.append({'시간대': period, '변수': label, 'VIF': vif, '공차': 1 / vif})
    fit = sm.OLS(data['change' if period == '하루 전체' else '출근_변화량'],
                 design, missing='raise').fit(cov_type='HC3')
    # 기존 추정 방식 및 결과와 일치하는지 확인한다.
    expected = stored.loc[stored['모형'].eq(f'{period} 113개')].set_index('변수')
    for key, label in zip(['const'] + columns, ['상수항'] + labels):
        np.testing.assert_allclose(fit.params[key], expected.loc[label, '계수'], atol=1e-9)
        np.testing.assert_allclose(fit.pvalues[key], expected.loc[label, 'p값'], atol=1e-10)
        coefficients.append({'시간대': period, '변수': label, '계수': fit.params[key],
                             '표준오차': fit.bse[key], 'z-value': fit.tvalues[key],
                             'p-value': fit.pvalues[key]})
    stats.append({'시간대': period, '격자 수': int(fit.nobs), 'R²': fit.rsquared,
                  '수정된 R²': fit.rsquared_adj, 'F값': float(fit.fvalue),
                  '모형 p-value': float(fit.f_pvalue)})
    x.rename(columns=dict(zip(columns, labels))).corr().to_csv(
        OUTPUT / f'3_2_3_{period}_설명변수간_상관행렬.csv', encoding='utf-8-sig')

vif = pd.DataFrame(rows)
coef = pd.DataFrame(coefficients)
model_stats = pd.DataFrame(stats)
vif.to_csv(OUTPUT / '3_2_3_광역버스_VIF.csv', index=False, encoding='utf-8-sig')
coef.to_csv(OUTPUT / '3_2_3_광역버스_회귀결과.csv', index=False, encoding='utf-8-sig')
model_stats.to_csv(OUTPUT / '3_2_3_광역버스_모형적합도.csv', index=False, encoding='utf-8-sig')
print(vif.to_string(index=False))
print(coef.to_string(index=False))
print(model_stats.to_string(index=False))
