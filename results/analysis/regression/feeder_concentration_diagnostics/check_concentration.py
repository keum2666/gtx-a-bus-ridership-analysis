"""Sensitivity checks for the existing 113-grid feeder OLS; no source results overwritten."""
from pathlib import Path
import pandas as pd
import numpy as np
import statsmodels.api as sm

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
T=ROOT/'results/analysis/feeder_bus/tables'
ids=pd.read_csv(ROOT/'results/analysis/regression/common_113/공통113격자_분석자료.csv')['셀 ID']
f=pd.read_csv(T/'H11a_격자별_공급구조_GTX역행.csv').set_index('셀 ID').reindex(ids)
p=pd.read_csv(T/'H14_격자별_20~50대인구_2025.csv').set_index('셀 ID').reindex(ids)
r=pd.read_csv(ROOT/'data/processed/gtx_a/feeder_bus/support/feature_expansion/S5_후보변수_126격자.csv').set_index('셀 ID').reindex(ids)
X=f[['log(1+GTX역 보행시간)','log(1+건축물 연면적)','주거지역 비율(%)']].copy()
X['20~50대 인구 2025(명)']=p['20~50대 인구 2025(명)']
X['1km 안 기존 철도역 수']=r['n_rail_1km']
X['운정 더미']=f['권역'].eq('운정중앙').astype(int)
cols=['log(1+GTX역 보행시간)','20~50대 인구 2025(명)','log(1+건축물 연면적)','주거지역 비율(%)','1km 안 기존 철도역 수','운정 더미']
X=X[cols]
stored=pd.read_csv(ROOT/'results/analysis/regression/common_113/연계버스_동일113격자_회귀계수.csv')
labels={cols[0]:'GTX역 보행시간',cols[2]:'건축물 연면적'}
coef=[];fits=[];influence=[];distribution=[]

def fit_model(y,x,period,model):
 z=sm.OLS(y.astype(float),sm.add_constant(x.astype(float),has_constant='add'),missing='raise').fit(cov_type='HC3')
 ci=z.conf_int()
 for key in z.params.index:
  coef.append({'시간대':period,'모형':model,'독립변수':labels.get(key,key),'계수':z.params[key],'p값':z.pvalues[key],'95%CI하한':ci.loc[key,0],'95%CI상한':ci.loc[key,1]})
 fits.append({'시간대':period,'모형':model,'N':int(z.nobs),'R2':z.rsquared,'adjR2':z.rsquared_adj})
 return z

for period,target in [('하루 전체','GTX역행 2025'),('출근시간대','GTX역행 2025 출근')]:
 y=f[target]
 z=fit_model(y,X,period,'현재 모형 113개')
 expected=stored.loc[stored['모형'].eq(period+' 113개')].set_index('변수')
 for key in z.params.index:
  lab='상수항' if key=='const' else labels.get(key,key)
  np.testing.assert_allclose(z.params[key],expected.loc[lab,'계수'],atol=1e-10)
  np.testing.assert_allclose(z.pvalues[key],expected.loc[lab,'p값'],atol=1e-10)
 # Two intercept dummies distinguish all three regions, versus the original Unjeong/others split.
 xf=X.copy();xf['킨텍스 더미']=f['권역'].eq('킨텍스').astype(int)
 fit_model(y,xf,period,'세 권역 평균 차이 반영')
 non=f['권역'].ne('운정중앙')
 xx=X.loc[non].drop(columns='운정 더미').copy();xx['킨텍스 더미']=f.loc[non,'권역'].eq('킨텍스').astype(int)
 fit_model(y.loc[non],xx,period,'운정중앙 제외 58개')
 unj=f['권역'].eq('운정중앙')
 fit_model(y.loc[unj],X.loc[unj].drop(columns='운정 더미'),period,'운정중앙 내부 55개')
 infl=z.get_influence();cooks=pd.Series(infl.cooks_distance[0],index=X.index)
 for idx in X.index:
  influence.append({'시간대':period,'셀 ID':idx,'권역':f.loc[idx,'권역'],'승차건수':y.loc[idx],'CookD':cooks.loc[idx],'레버리지':infl.hat_matrix_diag[X.index.get_loc(idx)]})
 for k in [1,3]:
  exclude=cooks.nlargest(k).index;keep=~X.index.isin(exclude)
  fit_model(y.loc[keep],X.loc[keep],period,f'CookD 상위 {k}개 제외')
 for region,g in f.groupby('권역'):
  values=g[target]
  distribution.append({'시간대':period,'권역':region,'격자수':len(g),'표본비중(%)':len(g)/len(f)*100,'승차건수':int(values.sum()),'이용비중(%)':values.sum()/y.sum()*100,'0건격자':int(values.eq(0).sum()),'0건격자비율(%)':values.eq(0).mean()*100,'최대값':values.max(),'평균':values.mean(),'중앙값':values.median()})

for name,rows in [('회귀계수_민감도',coef),('모형적합도_민감도',fits),('격자별_영향력',influence),('권역별_표본과_이용분포',distribution)]:
 pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
print('Original 113-grid coefficients and p-values reproduced exactly. Original source files unchanged.')
print(pd.DataFrame(distribution).round(3).to_string(index=False))
print(pd.DataFrame(coef).query('독립변수 in ["GTX역 보행시간", "건축물 연면적", "1km 안 기존 철도역 수"]').round(5).to_string(index=False))
print(pd.DataFrame(influence).sort_values('CookD',ascending=False).head(8).round(4).to_string(index=False))
