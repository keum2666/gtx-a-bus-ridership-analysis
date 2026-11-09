"""0건 포함 126개 원자료의 지터·카운트 버블·헥스빈 비교. 통계에는 지터 미적용."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/presentation/figures/순위상관_0건포함_비교'
OUT.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'results/paper/no_feeder_regression/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.colors import LogNorm
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

def main():
    d=pd.read_csv(ROOT/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    x=d['Δ광역 출근'].to_numpy(); y=d['GTX역행 2025 출근'].to_numpy()
    assert len(x)==126 and np.isfinite(x).all() and np.isfinite(y).all()
    rho,p=spearmanr(x,y)
    assert (y==0).sum()==88
    rng=np.random.default_rng(42)
    jx=x+rng.uniform(-.4,.4,len(x)); jy=y+rng.uniform(-.3,.3,len(y))
    # Show zero-count points inside the nonnegative domain, without changing the source.
    jy=np.maximum(jy,0)  # below-zero offsets reflect upwards, rather than clipping points
    zy=y==0; jy[zy]=np.abs(rng.uniform(-.3,.3,zy.sum()))
    c=d.groupby(['Δ광역 출근','GTX역행 2025 출근']).size().reset_index(name='格子数')
    assert c['格子数'].sum()==126
    font=Path.home()/'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    fm.fontManager.addfont(str(font)); family=fm.FontProperties(fname=str(font)).get_name()
    rc={'font.family':family,'font.weight':'bold','axes.labelweight':'bold','axes.titleweight':'bold',
        'axes.unicode_minus':False,'pdf.fonttype':42}
    for kind,title,note in [
        ('01_지터','지터 산점도','점 하나는 격자 하나 · 표시 위치에만 작은 지터 적용 · 상관계수는 원자료로 계산'),
        ('02_버블','중복 좌표 버블','원 면적은 동일 좌표의 격자 수에 비례 · 원자료 좌표 유지'),
        ('03_헥스빈','헥스빈','육각형 안의 격자 수를 색으로 표시 · 원자료 좌표 유지')]:
        with plt.rc_context(rc):
            fig,axes=plt.subplots(1,2,figsize=(16,6.8),gridspec_kw={'width_ratios':[1.5,1]})
            for ax,zoom in zip(axes,[False,True]):
                mask=(y<=5) if zoom else np.ones(len(y),dtype=bool)
                if kind=='01_지터':
                    ax.scatter(jx[mask],jy[mask],s=78,color='#315D86',alpha=.65,edgecolors='white',linewidths=.6,zorder=3)
                elif kind=='02_버블':
                    a=c[c['GTX역행 2025 출근']<=5] if zoom else c
                    ax.scatter(a.iloc[:,0],a.iloc[:,1],s=a['格子数']*52,
                               color='#315D86',alpha=.64,edgecolors='white',linewidths=.8,zorder=3)
                    if not zoom:
                        handles=[ax.scatter([],[],s=n*52,color='#315D86',alpha=.64,edgecolors='white',label=f'{n}개') for n in [1,5,14]]
                        ax.legend(handles=handles,title='같은 좌표의 격자 수',fontsize=13,title_fontsize=13,
                                  loc='upper right',frameon=False,labelspacing=1.2)
                else:
                    h=ax.hexbin(x[mask],y[mask],gridsize=(19,12) if zoom else (24,16),
                                extent=(-100,50,-.5,5.5) if zoom else (-100,50,-1,70),
                                mincnt=1,cmap='Blues',linewidths=.45,edgecolors='#D2DBE3',norm=LogNorm(vmin=1,vmax=40))
                    cb=fig.colorbar(h,ax=ax,pad=.025,fraction=.045)
                    cb.set_ticks([1,2,5,10,20,40]); cb.set_ticklabels(['1','2','5','10','20','40'])
                    cb.set_label('격자 수(개)',fontsize=14); cb.ax.tick_params(labelsize=12)
                ax.axvline(0,color='#AAAAAA',lw=1,zorder=1)
                ax.set_xlim(-100,50);ax.set_ylim((-.5,5.5) if zoom else (-1.5,70))
                ax.set_title(f'0~5건 구간 확대 ({int(mask.sum())}개)' if zoom else '전체 분포 (126개)',fontsize=23,pad=17)
                ax.set_xlabel('광역버스 승차 변화량(건)',fontsize=20,labelpad=13)
                ax.set_ylabel('개통 후 연계버스 승차건수(건)',fontsize=19,labelpad=12)
                ax.set_xticks([-100,-75,-50,-25,0,25,50]);ax.tick_params(labelsize=15,pad=7)
                ax.yaxis.set_major_locator(MaxNLocator(nbins=7,integer=True))
                ax.spines[['top','right']].set_visible(False)
                ax.set_axisbelow(True);ax.grid(axis='y',lw=.7,color='#DDDDDD',alpha=.6)
            fig.suptitle(f'{title}  |  출근시간대 · 스피어만 ρ = {rho:.3f} · p < .001'.replace('-0.','−0.'),fontsize=23,y=.98)
            fig.text(.5,.025,note,ha='center',fontsize=14,color='#444444')
            fig.subplots_adjust(left=.075,right=.97,bottom=.16,top=.82,wspace=.36)
            for ext in ['png','pdf']:
                fig.savefig(OUT/f'{kind}_출근시간대_126격자.{ext}',dpi=300,facecolor='white',bbox_inches='tight',pad_inches=.15)
            plt.close(fig)
    pd.DataFrame({'셀 ID':d['셀 ID'],'원자료_변화량':x,'원자료_연계버스':y,'지터_x':jx,'지터_y':jy}).to_csv(OUT/'검증_원자료와표시좌표.csv',index=False,encoding='utf-8-sig')
    print(f'N={len(d)}, 연계버스 0건={int((y==0).sum())}, rho={rho:.9f}, p={p:.9f}')
    print('세 대안 PNG·PDF 생성:',OUT)

if __name__=='__main__':main()
