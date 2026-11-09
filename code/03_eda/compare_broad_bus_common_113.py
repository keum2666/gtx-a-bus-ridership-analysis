"""013의 기존 집계·모형을 재사용하여 두 버스의 회귀를 동일 113개로 비교."""
from pathlib import Path
import contextlib
import io
import json

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
notebook = json.loads((ROOT / 'code/03_eda/013_출근시간대_추가분석.ipynb').read_text())
scope = {}
# 기존 원자료 연결, 출근시간 집계, OLS 정의를 그대로 사용한다.
# 원 노트북과 기존 결과 파일에는 쓰지 않는다.
with contextlib.redirect_stdout(io.StringIO()):
    for cell_index in [1, 3, 7, 12]:
        if cell_index == 3:
            scope['display'] = lambda *args, **kwargs: None
        exec(compile(''.join(notebook['cells'][cell_index]['source']),
                     f'013_cell_{cell_index}', 'exec'), scope)

mask = scope['mask_broad_morning_013']
data = scope['morning_013']
assert int(mask.sum()) == 113
fits = {
    '하루 전체 126개(기존)': scope['broad_day_fit_013'],
    '하루 전체 113개': scope['fit_hc3_013'](
        data.loc[mask, 'change'], scope['X_day_013'].loc[mask]),
    '출근시간대 113개': scope['fit_hc3_013'](
        data.loc[mask, '출근_변화량'], scope['X_morn_013'].loc[mask]),
}
assert fits['하루 전체 113개'].model.data.row_labels.equals(
    fits['출근시간대 113개'].model.data.row_labels)
np.testing.assert_allclose(fits['출근시간대 113개'].params,
                           scope['broad_morning_fit_013'].params, atol=1e-12)
labels = dict(scope['BROAD_LABELS_013'])
labels.update({'log_walk': 'GTX역 보행시간', 'log_floor': '건축물 연면적',
               'ic_access': 'IC 접근성'})
coef = pd.DataFrame([
    row for name, fit in fits.items()
    for row in scope['coefficient_rows_013'](fit, name, labels)
])
stats = pd.DataFrame([scope['fit_row_013'](fit, name) for name, fit in fits.items()])
out = ROOT / 'results/analysis/regression/common_113'
out.mkdir(parents=True, exist_ok=True)
coef.to_csv(out / '광역버스_동일113격자_회귀계수.csv', index=False, encoding='utf-8-sig')
stats.to_csv(out / '광역버스_동일113격자_모형적합도.csv', index=False, encoding='utf-8-sig')
data.loc[mask].to_csv(out / '공통113격자_분석자료.csv', encoding='utf-8-sig')

feeder_fits = {
    name: scope['fit_hc3_013'](scope['feeder_013'].loc[mask, target],
                               scope['X_feeder_013'].loc[mask])
    for name, target in [('하루 전체 113개', 'GTX역행 2025'),
                         ('출근시간대 113개', 'GTX역행 2025 출근')]
}
for fit in feeder_fits.values():
    assert fit.model.data.row_labels.equals(fits['하루 전체 113개'].model.data.row_labels)
feeder_labels = dict(scope['FEEDER_LABELS_013'])
feeder_labels.update({'log(1+GTX역 보행시간)': 'GTX역 보행시간',
                      'log(1+건축물 연면적)': '건축물 연면적'})
feeder_coef = pd.DataFrame([
    row for name, fit in feeder_fits.items()
    for row in scope['coefficient_rows_013'](fit, name, feeder_labels)
])
feeder_stats = pd.DataFrame([scope['fit_row_013'](fit, name)
                             for name, fit in feeder_fits.items()])
feeder_coef.to_csv(out / '연계버스_동일113격자_회귀계수.csv', index=False, encoding='utf-8-sig')
feeder_stats.to_csv(out / '연계버스_동일113격자_모형적합도.csv', index=False, encoding='utf-8-sig')

print(stats.to_string(index=False))
print(coef[['모형', '변수', '계수', 'p값', '5% 유의']].to_string(index=False))
print(feeder_stats.to_string(index=False))
print(feeder_coef[['모형', '변수', '계수', 'p값', '5% 유의']].to_string(index=False))
print('공통113개 권역별 격자 수:', data.loc[mask, 'nearest_station'].value_counts().to_dict())
print('저장:', out)
