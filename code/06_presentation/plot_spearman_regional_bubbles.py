"""권역별 출근시간대 버블 그림: 모든 격자·0건 포함, 원자료 좌표 유지."""
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
import pandas as pd
from scipy.stats import spearmanr

def main():
    d=pd.read_csv(ROOT/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    regions=['운정중앙','킨텍스','대곡']; colors=['#3264A8','#D18C32','#359475']
    x,y='Δ광역 출근','GTX역행 2025 출근'
    f=Path.home()/'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    fm.fontManager.addfont(str(f))
    rc={'font.family':fm.FontProperties(fname=str(f)).get_name(),'font.weight':'bold',
        'axes.labelweight':'bold','axes.titleweight':'bold','axes.unicode_minus':False,'pdf.fonttype':42}
    with plt.rc_context(rc):
        fig,axes=plt.subplots(2,3,figsize=(17,10.2),sharex=True)
        for j,(region,color) in enumerate(zip(regions,colors)):
            a=d[d['권역'].eq(region)]
            rho,p=spearmanr(a[x],a[y]); ps='p < .001' if p<.001 else f'p = {p:.3f}'
            counts=a.groupby([x,y]).size().reset_index(name='N')
            assert counts['N'].sum()==len(a)
            for row in range(2):
                ax=axes[row,j]
                c=counts if row==0 else counts[counts[y]<=5]
                ax.scatter(c[x],c[y],s=c['N']*65,c=color,alpha=.72,
                           edgecolors='white',linewidths=.9,zorder=3)
                ax.axvline(0,color='#999999',lw=1,zorder=1)
                ax.set_xlim(-100,50);ax.set_ylim((-1.5,70) if row==0 else (-.5,5.5))
                ax.set_xticks([-100,-50,0,50])
                ax.set_yticks([0,20,40,60] if row==0 else [0,1,2,3,4,5])
                ax.spines[['top','right']].set_visible(False)
                ax.set_axisbelow(True);ax.grid(axis='y',color='#DDDDDD',lw=.8,alpha=.65)
                ax.tick_params(labelsize=17,pad=7)
                if row==0:
                    ax.set_title(f'{region}역 ({len(a)}개)\nρ = {rho:.3f} · {ps}'.replace('-0.','−0.'),
                                 fontsize=22,pad=17,linespacing=1.5)
                else:
                    ax.set_xlabel('광역버스 승차 변화량(건)',fontsize=19,labelpad=13)
                if j==0:
                    ax.set_ylabel(('전체 분포\n' if row==0 else '0~5건 확대\n')+'연계버스 승차건수(건)',
                                  fontsize=20,labelpad=15)
        # One shared frequency scale applies to all regions and both rows.
        handles=[axes[0,0].scatter([],[],s=n*65,c='#657586',alpha=.72,
                                 edgecolors='white',label=f'{n}개') for n in [1,5,10]]
        fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.005),
                   ncol=3,frameon=False,fontsize=16,title='원 면적: 같은 좌표의 격자 수',title_fontsize=16)
        fig.subplots_adjust(left=.10,right=.985,top=.87,bottom=.17,hspace=.30,wspace=.23)
        stem=OUT/'04_권역별_버블_출근시간대_0건포함'
        for ext in ['png','pdf']:
            fig.savefig(stem.with_suffix('.'+ext),dpi=300,facecolor='white',bbox_inches='tight',pad_inches=.2)
        plt.close(fig)
    print(stem.with_suffix('.png'))

if __name__=='__main__':main()
