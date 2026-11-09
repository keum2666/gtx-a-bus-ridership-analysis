"""권역별 지터·원자료 선형 추세. 모든 격자 및 0건 포함, 통계에는 지터 미적용."""
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
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

def main():
    d=pd.read_csv(ROOT/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    x,y='Δ광역 출근','GTX역행 2025 출근'
    assert len(d)==126 and d[[x,y]].notna().all().all()
    font=Path.home()/'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    fm.fontManager.addfont(str(font))
    rc={'font.family':fm.FontProperties(fname=str(font)).get_name(),'font.weight':'bold',
        'axes.labelweight':'bold','axes.titleweight':'bold','axes.unicode_minus':False,'pdf.fonttype':42}
    rng=np.random.default_rng(42)
    with plt.rc_context(rc):
        fig,axes=plt.subplots(2,3,figsize=(17,10.6))
        for j,(region,color) in enumerate(zip(['운정중앙','킨텍스','대곡'],['#3264A8','#D18C32','#359475'])):
            a=d[d['권역'].eq(region)]; rx=a[x].to_numpy(); ry=a[y].to_numpy()
            rho,p=spearmanr(rx,ry); ps='p < .001' if p<.001 else f'p = {p:.3f}'
            jx=rx+rng.uniform(-.6,.6,len(a))
            jy=ry+rng.uniform(-.3,.3,len(a))
            # A zero record stays within a small nonnegative display band.
            jy=np.abs(jy)
            slope,intercept=np.polyfit(rx,ry,1)
            gx=np.linspace(rx.min(),rx.max(),500); gy=slope*gx+intercept
            valid=gy>=0
            for row in range(2):
                ax=axes[row,j]
                mask=np.ones(len(a),dtype=bool) if row==0 else ((ry<=5)&(rx>=-15)&(rx<=15))
                ax.scatter(jx[mask],jy[mask],s=70 if row==0 else 92,color=color,
                           alpha=.68,edgecolors='white',linewidths=.7,zorder=3)
                ax.plot(gx[valid],gy[valid],ls='--',lw=2.5,color='#444444',zorder=2)
                ax.axvline(0,color='#AAAAAA',lw=1,zorder=1)
                ax.set_xlim((-100,50) if row==0 else (-15,15))
                ax.set_ylim((-1.5,70) if row==0 else (-.4,5.6))
                ax.set_xticks([-100,-50,0,50] if row==0 else [-15,-10,-5,0,5,10,15])
                ax.set_yticks([0,20,40,60] if row==0 else [0,1,2,3,4,5])
                ax.tick_params(labelsize=16,pad=7)
                ax.spines[['top','right']].set_visible(False)
                ax.set_axisbelow(True);ax.grid(axis='y',lw=.8,color='#DDDDDD',alpha=.6)
                if row==0:
                    ax.set_title(f'{region}역 ({len(a)}개)\nρ = {rho:.3f} · {ps}'.replace('-0.','−0.'),
                                 fontsize=23,pad=19,linespacing=1.45)
                else:
                    ax.set_xlabel('광역버스 승차 변화량(건)',fontsize=19,labelpad=13)
                if j==0:
                    ax.set_ylabel(('전체 분포\n' if row==0 else '0건 주변 확대\n')+'연계버스 승차건수(건)',
                                  fontsize=20,labelpad=14)
        fig.legend(handles=[Line2D([0],[0],ls='--',lw=2.5,color='#444444',label='원자료의 선형 추세선')],
                   loc='lower center',bbox_to_anchor=(.5,.045),frameon=False,fontsize=17)
        fig.text(.5,.025,'점 위치에만 작은 지터 적용 · 상관계수와 추세선은 지터를 넣지 않은 각 권역 전체 자료로 계산',
                 ha='center',fontsize=13,color='#555555')
        fig.subplots_adjust(left=.10,right=.985,top=.87,bottom=.20,hspace=.28,wspace=.24)
        stem=OUT/'05_권역별_지터_추세선_출근시간대_0건포함'
        for ext in ['png','pdf']:
            fig.savefig(stem.with_suffix('.'+ext),dpi=300,facecolor='white',bbox_inches='tight',pad_inches=.2)
        plt.close(fig)
    print(stem.with_suffix('.png'))

if __name__=='__main__':main()
