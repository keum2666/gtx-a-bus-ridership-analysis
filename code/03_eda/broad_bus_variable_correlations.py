"""3.2.2: 광역버스 승차 변화량과 7개 설명변수의 Pearson 상관분석.

013의 검증된 원자료 집계 셀을 재사용한다. 기존 노트북·모형·결과 파일은 수정하지 않는다.
실행: python code/03_eda/broad_bus_variable_correlations.py
"""
from pathlib import Path
import contextlib
import io
import json
import numpy as np
import pandas as pd
from scipy.stats import pearsonr


def calculate(root):
    notebook = root / 'code/03_eda/013_출근시간대_추가분석.ipynb'
    cells = json.loads(notebook.read_text(encoding='utf-8'))['cells']
    sources = [''.join(c['source']) for c in cells if c['cell_type']=='code']
    setup = next(s for s in sources if 'base_013 = pd.read_csv' in s)
    aggregate = next(s for s in sources if s.startswith('def haversine_013'))
    namespace = {}
    # 실제 승차기록과 하차좌표로 집계한다. 회귀모형은 재추정하지 않는다.
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(setup,str(notebook),'exec'),namespace)
        namespace['display'] = lambda *args: None
        exec(compile(aggregate,str(notebook),'exec'),namespace)
    data = namespace['morning_013'].copy()
    data['log_walk'] = np.log1p(data['walk_min'])
    data['log_floor'] = np.log1p(data['2024년 건축물 연면적(천㎡)'])
    columns = ['log_walk','pop_20_50','log_floor','주거지역 비율(%)',
               'competing_share','bus_time_mean','ic_access']
    labels = ['GTX역 보행시간 ln(1+x)','20~50대 인구','건축물 연면적 ln(1+x)',
              '주거지역 비율','GTX 경쟁 목적지 비율','평균 버스 통행시간','IC 접근성']
    common_mask = data['출근_승차건수_2024'].gt(0)
    assert int(common_mask.sum()) == 113
    rows=[]; samples=[]
    for period in ['하루 전체','출근시간대']:
        X=data[columns].astype(float).copy()
        if period=='출근시간대':
            X['competing_share']=data['출근_경쟁목적지비율']
            X['bus_time_mean']=data['출근_평균버스통행시간']
        y=data['change' if period=='하루 전체' else '출근_변화량'].astype(float)
        mask=common_mask & np.isfinite(X.to_numpy()).all(axis=1) & np.isfinite(y.to_numpy())
        assert int(mask.sum()) == 113
        np.testing.assert_array_equal(mask, common_mask)
        for col,label in zip(columns,labels):
            r,p=pearsonr(X.loc[mask,col],y.loc[mask])
            rows.append({'시간대':period,'변수':label,'상관계수':float(r),'p-value':float(p),
                         '격자 수':int(mask.sum()),'5% 유의':bool(p<.05)})
        for cell in X.index[mask]:samples.append({'시간대':period,'셀 ID':int(cell)})
    return pd.DataFrame(rows),pd.DataFrame(samples)


def main():
    root=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'config.py').is_file())
    output=root/'results/paper/tables';output.mkdir(parents=True,exist_ok=True)
    results,samples=calculate(root)
    results.to_csv(output/'3_2_2_광역버스_변수별_피어슨상관.csv',index=False,encoding='utf-8-sig')
    samples.to_csv(output/'3_2_2_광역버스_상관분석_표본.csv',index=False,encoding='utf-8-sig')
    print(results.to_string(index=False,float_format=lambda v:f'{v:.6f}'))

if __name__=='__main__':main()
