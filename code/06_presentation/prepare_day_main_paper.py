"""하루 전체 중심 원고에 사용할 126개 격자 통계와 정적 지도. 기존 자료는 덮어쓰지 않는다."""
from pathlib import Path
import os,importlib.util,json
ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR','/tmp/urop_mpl_capture')
import numpy as np,pandas as pd,statsmodels.api as sm
from scipy.stats import pearsonr,spearmanr
from statsmodels.stats.outliers_influence import variance_inflation_factor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Patch,Rectangle
from matplotlib.lines import Line2D
import geopandas as gpd
from shapely.geometry import box

OUT=ROOT/'results/paper/day_main';FIG=OUT/'figures';TABLE=OUT/'tables'
ORDER=['운정중앙','킨텍스','대곡']
FEATURES=['log_walk','pop_20_50','log_floor','주거지역 비율(%)','competing_share','bus_time_mean','ic_access']
LABELS=['GTX역 보행시간','20~50대 인구','건축물 연면적','주거지역 비율','GTX 경쟁 목적지 비율','평균 버스 통행시간','IC 도로거리']

def prepare():
    d=pd.read_csv(ROOT/'data/final/gtx_a/S1_126격자_건수기준_기초표.csv')
    d['log_walk']=np.log1p(d.walk_min);d['log_floor']=np.log1p(d['2024년 건축물 연면적(천㎡)'])
    assert len(d)==126 and d[['change',*FEATURES]].notna().all().all()
    X=sm.add_constant(d[FEATURES]);m=sm.OLS(d.change,X).fit(cov_type='HC3')
    coef=pd.DataFrame({'변수':['상수항',*LABELS],'계수':m.params.to_numpy(),'표준오차':m.bse.to_numpy(),'p':m.pvalues.to_numpy()})
    fit={'N':int(m.nobs),'R2':m.rsquared,'adj_R2':m.rsquared_adj,'F':float(m.fvalue),'p':float(m.f_pvalue)}
    cor=pd.DataFrame([{'변수':label,'r':pearsonr(d[col],d.change).statistic,'p':pearsonr(d[col],d.change).pvalue} for col,label in zip(FEATURES,LABELS)])
    vif=pd.DataFrame([{'변수':label,'VIF':variance_inflation_factor(X.to_numpy(),i)} for i,label in enumerate(LABELS,1)])
    reg=d.groupby('nearest_station').agg(N=('セル ID','size')) if False else d.groupby('nearest_station').agg(N=('셀 ID','size'),before=('board_2024','sum'),after=('board_2025','sum'),change=('change','sum')).reindex(ORDER)
    reg['pct']=reg.change/reg.before*100
    grid=pd.crosstab(d.nearest_station,np.sign(d.change)).reindex(index=ORDER,columns=[-1,0,1],fill_value=0)
    f=pd.read_csv(ROOT/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    f=f.merge(d[['셀 ID','walk_min']],on='셀 ID',validate='one_to_one')
    feeder=f.groupby('권역').agg(N=('셀 ID','size'),count=('GTX역행 2025','sum'),active=('GTX역행 2025',lambda x:x.gt(0).sum())).reindex(ORDER)
    feeder['mean']=feeder['count']/feeder.N;feeder['share']=feeder['count']/feeder['count'].sum()*100
    feeder['active_pct']=feeder.active/feeder.N*100
    f['walk_bin']=pd.cut(f.walk_min,[-np.inf,20,50,np.inf],labels=['20분 이하','20분 초과 50분 이하','50분 초과'])
    walk=f.groupby('walk_bin',observed=False).agg(N=('셀 ID','size'),count=('GTX역행 2025','sum'));walk['mean']=walk['count']/walk.N
    rho=pd.DataFrame([{'권역':region,'N':len(a),'rho':spearmanr(a['Δ광역'],a['GTX역행 2025']).statistic,'p':spearmanr(a['Δ광역'],a['GTX역행 2025']).pvalue} for region,a in [('전체',f),*[(s,f[f['권역'].eq(s)]) for s in ORDER]]])
    for name,t in [('회귀계수',coef),('피어슨상관',cor),('VIF',vif),('권역별광역버스',reg),('격자별변화',grid),('연계버스',feeder),('보행시간구간',walk),('순위상관',rho)]:
        t.to_csv(TABLE/f'{name}.csv',encoding='utf-8-sig',index=name in ['권역별광역버스','격자별변화','연계버스','보행시간구간'])
    (TABLE/'모형적합도.json').write_text(json.dumps(fit,indent=2))
    np.testing.assert_allclose(m.params.log_walk,26.586377,rtol=1e-5)
    assert reg.before.sum()==7110 and reg.after.sum()==5517 and feeder['count'].sum()==1015
    path=ROOT/'code/03_eda/kakao_combined_grid_overlay.py';spec=importlib.util.spec_from_file_location('_day_paper_map',path);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    geo,_=h.load_combined_grid(ROOT)
    admin=gpd.read_file(ROOT/'data/raw/common/api_cache_gtx_a_routes/HangJeongDong_ver20260701.geojson').to_crs(geo.crs)
    admin=admin.loc[admin.geometry.intersects(box(*geo.total_bounds))]
    payload=h.make_combined_payload(geo,ROOT)
    font=Path.home()/'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    if not font.exists():font=Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
    fm.fontManager.addfont(str(font));family=fm.FontProperties(fname=str(font)).get_name()
    with plt.rc_context({'font.family':family,'axes.unicode_minus':False,'font.weight':'bold'}):
        fig,ax=plt.subplots(figsize=(10.5,6.4));xs=np.arange(3);w=.34
        for offset,col,color,label in [(-w/2,'before','#B9B9B9','GTX-A 개통 전'),(w/2,'after','#8064A2','GTX-A 개통 후')]:
            bars=ax.bar(xs+offset,reg[col],w,color=color,label=label);ax.bar_label(bars,labels=[f'{int(v):,}' for v in reg[col]],fontsize=15,fontweight='bold',padding=6)
        ax.set_xticks(xs,[s+'역' for s in ORDER],fontsize=16);ax.set_ylabel('승차건수(건)',fontsize=18,fontweight='bold')
        ax.set_ylim(0,4100);ax.tick_params(labelsize=14);ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False,fontsize=14)
        fig.tight_layout();fig.savefig(FIG/'하루전체_권역별_광역버스_승차건수.png',dpi=260);plt.close(fig)
        for station in ORDER:
            part=geo[geo.nearest_station.eq(station)]
            full=np.array(part.total_bounds)+np.array([-400,-400,400,400])
            main=gpd.GeoSeries([box(*payload[station]['bounds']['main'])],crs=4326).to_crs(geo.crs).total_bounds
            if station=='킨텍스':main=full
            point=gpd.GeoSeries(gpd.points_from_xy([payload[station]['point'][1]],[payload[station]['point'][0]]),crs=4326).to_crs(geo.crs).iloc[0]
            def draw(ax,bounds,small=False):
                area=box(*bounds);bg=admin[admin.geometry.intersects(area)].copy()
                bg.geometry=bg.geometry.intersection(area)
                if len(bg):bg.plot(ax=ax,color='#F4F4F4',edgecolor='#C8C8C8',linewidth=.4)
                part.plot(ax=ax,color=part.day_sign.map(h.COLORS),edgecolor='#333333',linewidth=.45 if small else 1)
                ax.scatter([point.x],[point.y],marker='*',s=90 if small else 330,c='#00865A',edgecolors='white',zorder=5)
                ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
            fig,ax=plt.subplots(figsize=(10,9));draw(ax,main)
            if station!='킨텍스':
                inset=ax.inset_axes([.73,.66,.26,.32]);draw(inset,full,True)
                inset.add_patch(Rectangle((main[0],main[1]),main[2]-main[0],main[3]-main[1],fill=False,edgecolor='#222222',linewidth=1.2))
                inset.set_title('권역 전체',fontsize=12)
            ax.set_title(f'{station}역 · 하루 전체 승차 변화',fontsize=21,pad=18)
            handles=[Patch(facecolor=h.COLORS[k],edgecolor='#333333',label=t) for k,t in [(-1,'감소'),(0,'유지'),(1,'증가')]]
            handles.append(Line2D([],[],marker='*',color='#00865A',ls='none',markersize=13,label='GTX역'))
            fig.legend(handles=handles,loc='lower center',ncol=4,frameon=False,fontsize=14)
            fig.subplots_adjust(left=.03,right=.97,top=.9,bottom=.08)
            fig.savefig(FIG/f'{station}_하루전체_격자별변화.png',dpi=260,bbox_inches='tight');plt.close(fig)
    print('모형',fit)
    print('격자',grid.to_string());print('연계버스',feeder.to_string());print('보행',walk.to_string())

if __name__=='__main__':prepare()
