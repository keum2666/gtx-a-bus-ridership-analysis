"""실제 출근시간대 변화량·연계버스 건수의 관계. 선형 추세는 시각적 보조이다."""
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/presentation/figures'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'results/paper/no_feeder_regression/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

def main():
    d=pd.read_csv(ROOT/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    x,y='Δ광역 출근','GTX역행 2025 출근'
    assert len(d)==126 and d[[x,y]].notna().all().all()
    rho,p=spearmanr(d[x],d[y])
    font=Path.home()/'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    fm.fontManager.addfont(str(font))
    rc={'font.family':fm.FontProperties(fname=str(font)).get_name(),'font.weight':'bold',
        'axes.labelweight':'bold','axes.unicode_minus':False,'pdf.fonttype':42}
    with plt.rc_context(rc):
        fig,ax=plt.subplots(figsize=(12.8,7.8))
        colors={'운정중앙':'#3264A8','킨텍스':'#D18C32','대곡':'#359475'}
        for region,color in colors.items():
            a=d[d['권역'].eq(region)]
            # Exact ties are represented by area, without jitter or moving data.
            counts=a.groupby([x,y]).size().reset_index(name='N')
            ax.scatter(counts[x],counts[y],s=85*counts['N'],color=color,
                       edgecolors='white',linewidths=1,alpha=.78,label=region+'역',zorder=3)
        slope,intercept=np.polyfit(d[x],d[y],1)
        gx=np.linspace(d[x].min(),d[x].max(),300);gy=slope*gx+intercept
        valid=gy>=0
        ax.plot(gx[valid],gy[valid],color='#595959',lw=2.7,ls='--',label='분포 추세선',zorder=2)
        ax.axvline(0,color='#AAAAAA',lw=1.1,zorder=1)
        ax.set_xlim(-100,50); ax.set_ylim(-3,70)
        ax.set_xticks([-100,-75,-50,-25,0,25,50])
        ax.set_yticks(range(0,71,10))
        ax.set_xlabel('광역버스 승차건수 변화량(건)',fontsize=23,labelpad=17)
        ax.set_ylabel('개통 후 GTX역 연계버스 승차건수(건)',fontsize=23,labelpad=17)
        ax.tick_params(labelsize=19,pad=8)
        for tick in [*ax.get_xticklabels(),*ax.get_yticklabels()]: tick.set_fontweight('bold')
        ax.set_axisbelow(True);ax.grid(axis='y',color='#DDDDDD',alpha=.7,lw=.8)
        ax.spines[['top','right']].set_visible(False)
        ax.legend(loc='upper right',frameon=False,fontsize=17,markerscale=.65)
        ax.text(.97,.64,f'스피어만 ρ = {rho:.3f}'.replace('-','−')+'\np < .001 · 126개 격자',
                transform=ax.transAxes,ha='right',va='top',fontsize=21,linespacing=1.5,
                bbox={'facecolor':'white','edgecolor':'none','alpha':.92})
        fig.text(.5,.98,'출근시간대 광역버스 승차 변화량과 GTX역 연계버스 이용',
                 ha='center',va='top',fontsize=25,fontweight='bold')
        fig.text(.52,.025,'원의 크기: 같은 값을 갖는 격자 수 · 점선: 원자료의 선형 추세',
                 ha='center',fontsize=14,color='#555555')
        fig.subplots_adjust(left=.12,right=.98,top=.90,bottom=.17)
        OUT.mkdir(parents=True,exist_ok=True)
        stem=OUT/'순위상관_실제변화량_연계버스승차건수_출근시간대'
        for ext in ['png','pdf']:
            fig.savefig(stem.with_suffix('.'+ext),dpi=300,facecolor='white',bbox_inches='tight',pad_inches=.15)
        plt.close(fig)
    print(stem.with_suffix('.png'))

if __name__=='__main__':main()
