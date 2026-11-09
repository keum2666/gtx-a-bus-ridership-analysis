"""하루 전체 126개 격자: 지터·버블·헥스빈. 모든 그림의 축/빈도 척도를 통일한다."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'results/paper/no_feeder_regression/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

OUT=ROOT/'results/presentation/figures/순위상관_전체출근_공통축'
X,Y='Δ광역','GTX역행 2025'
XLIM=(-225,75);YLIM=(-3,100)
EXTENT=(*XLIM,*YLIM);GRIDSIZE=(26,18)
DENSITY_CMAP=LinearSegmentedColormap.from_list('visible_blues',plt.get_cmap('Blues')(np.linspace(.22,1,256)))
REGIONS=['운정중앙','킨텍스','대곡']
COLORS={'전체':'#315D86','운정중앙':'#3264A8','킨텍스':'#D18C32','대곡':'#359475'}
JITTER_COLORS={'전체':'#315D86','운정중앙':'#C45A88','킨텍스':'#888888','대곡':'#8A6446'}


def main(period='하루전체', kinds=None, regional_views=(False,True), nonlinear_y=False):
    global X,Y
    X,Y=('Δ광역','GTX역행 2025') if period=='하루전체' else ('Δ광역 출근','GTX역행 2025 출근')
    period_title='하루 전체' if period=='하루전체' else '출근시간대'
    OUT.mkdir(parents=True,exist_ok=True)
    data=pd.read_csv(ROOT/'results/analysis/feeder_bus/tables/H11a_격자별_공급구조_GTX역행.csv')
    assert len(data)==126 and data['셀 ID'].is_unique
    assert np.isfinite(data[[X,Y]].to_numpy()).all()
    assert data[Y].eq(0).sum()==(83 if period=='하루전체' else 88) and data[Y].sum()==(1015 if period=='하루전체' else 646)
    assert data[X].between(*XLIM).all() and data[Y].between(*YLIM).all()
    rng=np.random.default_rng(42)
    data['display_x']=data[X]+rng.uniform(-.7,.7,len(data))
    data['display_y']=np.abs(data[Y]+rng.uniform(-.3,.3,len(data)))
    font=Path.home()/'Library/Fonts/KoPubWorld Dotum Bold.ttf'
    if not font.exists():font=Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
    fm.fontManager.addfont(str(font));family=fm.FontProperties(fname=str(font)).get_name()
    rc={'font.family':family,'font.weight':'bold','axes.labelweight':'bold','axes.titleweight':'bold',
        'axes.unicode_minus':False,'pdf.fonttype':42}
    check,ax=plt.subplots()
    hexmax=1
    for refx,refy in [('Δ광역','GTX역행 2025'),('Δ광역 출근','GTX역행 2025 출근')]:
        hb=ax.hexbin(data[refx],data[refy],gridsize=GRIDSIZE,extent=EXTENT,mincnt=1)
        hexmax=max(hexmax,int(hb.get_array().max()));ax.clear()
    plt.close(check)
    norm=LogNorm(vmin=1,vmax=max(2,hexmax))
    stats=[]
    for region in ['전체',*REGIONS]:
        part=data if region=='전체' else data[data['권역'].eq(region)]
        rho,p=spearmanr(part[X],part[Y])
        stats.append({'권역':region,'격자수':len(part),'연계버스0건격자':int(part[Y].eq(0).sum()),'rho':rho,'p':p})
    pd.DataFrame(stats).to_csv(OUT/f'{period}_순위상관_검증.csv',index=False,encoding='utf-8-sig')
    data[['셀 ID','권역',X,Y,'display_x','display_y']].to_csv(OUT/f'{period}_원자료와지터표시좌표.csv',index=False,encoding='utf-8-sig')

    with plt.rc_context(rc):
        for kind,name in [('jitter','지터'),('bubble','버블'),('hexbin','헥스빈')]:
            if kinds is not None and kind not in kinds: continue
            for regional in regional_views:
                groups=REGIONS if regional else ['전체']
                fig,axes=plt.subplots(1,len(groups),figsize=(18.5,7.1) if regional else (10.5,7.8),
                                      sharex=True,sharey=True,squeeze=False)
                axes=axes.ravel();hexplot=None
                for ax,region in zip(axes,groups):
                    part=data if region=='전체' else data[data['권역'].eq(region)]
                    st=next(r for r in stats if r['권역']==region)
                    ps='p < .001' if st['p']<.001 else f'p = {st["p"]:.3f}'
                    color=JITTER_COLORS[region] if kind=='jitter' else COLORS[region]
                    if kind=='jitter':
                        ax.scatter(part.display_x,part.display_y,s=92,color=color,alpha=.7,
                                   edgecolors='white',linewidths=.7,zorder=3)
                        slope,intercept=np.polyfit(part[X],part[Y],1)
                        gx=np.linspace(part[X].min(),part[X].max(),400);gy=slope*gx+intercept
                        keep=gy>=0
                        ax.plot(gx[keep],gy[keep],color='#444444',lw=2.2,ls='--',zorder=2)
                    elif kind=='bubble':
                        counts=part.groupby([X,Y]).size().reset_index(name='count')
                        assert counts['count'].sum()==len(part)
                        ax.scatter(counts[X],counts[Y],s=counts['count']*62,color=color,alpha=.7,
                                   edgecolors='white',linewidths=.8,zorder=3)
                    else:
                        hexplot=ax.hexbin(part[X],part[Y],gridsize=GRIDSIZE,extent=EXTENT,mincnt=1,
                                          cmap=DENSITY_CMAP,norm=norm,linewidths=.35,edgecolors='#D6DFE7',zorder=3)
                    ax.axvline(0,color='#AAAAAA',lw=.9,zorder=1)
                    ax.set_xlim(XLIM);ax.set_ylim(YLIM)
                    ax.set_xticks([-200,-150,-100,-50,0,50]);ax.set_yticks([0,20,40,60,80,100])
                    if nonlinear_y:
                        ax.set_yscale('symlog',linthresh=5,linscale=1,base=10)
                        ax.set_ylim(-.5,100)
                        ax.set_yticks([0,5,10,50,100],labels=['0','5','10','50','100'])
                        ax.minorticks_off()
                    ax.tick_params(labelsize=16 if regional else 18,pad=7)
                    ax.set_title(f'{region+"역" if regional else "전체"} ({len(part)}개)\nρ = {st["rho"]:.3f} · {ps}'.replace('-0.','−0.'),
                                 fontsize=22 if regional else 25,fontweight='bold',pad=18,linespacing=1.45)
                    ax.set_xlabel('광역버스 승차 변화량(건)',fontsize=19 if regional else 22,labelpad=14)
                    ax.spines[['top','right']].set_visible(False)
                    ax.set_axisbelow(True);ax.grid(axis='y',color='#DDDDDD',lw=.7,alpha=.6)
                axes[0].set_ylabel('개통 후 GTX역 연계버스\n승차건수(건, 비선형 축)' if nonlinear_y
                                   else '개통 후 GTX역 연계버스 승차건수(건)',fontsize=20,labelpad=14)
                if kind=='jitter':
                    fig.legend([Line2D([],[],color='#444444',lw=2.2,ls='--')],['원자료의 선형 추세 (비선형 축에 표시)' if nonlinear_y else '원자료의 선형 추세선'],
                               loc='lower center',bbox_to_anchor=(.5,.055),frameon=False,fontsize=15)
                    note='점 위치에만 작은 지터 적용 · 상관계수와 추세선은 0건을 포함한 원자료로 계산'
                elif kind=='bubble':
                    handles=[axes[0].scatter([],[],s=n*62,color='#657586',alpha=.7,edgecolors='white',label=f'{n}개') for n in [1,5,12]]
                    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.045),ncol=3,
                               frameon=False,fontsize=15,title='원 면적: 동일 좌표의 격자 수',title_fontsize=15)
                    note='0건 포함 · 원자료 좌표 유지 · 모든 권역에 같은 원 면적 기준 적용'
                else:
                    fig.subplots_adjust(right=.90)
                    cax=fig.add_axes([.925,.24,.013,.5])
                    cb=fig.colorbar(hexplot,cax=cax)
                    ticks=[n for n in [1,2,5,10,20,50] if n<=hexmax]
                    if hexmax not in ticks:ticks.append(hexmax)
                    cb.set_ticks(ticks);cb.set_ticklabels([str(n) for n in ticks]);cb.ax.tick_params(labelsize=13)
                    cb.set_label('격자 수(개)',fontsize=16,labelpad=10)
                    note='0건 포함 · 모든 그림에 동일한 육각형 구간과 빈도 색상 기준 적용'
                if nonlinear_y:
                    note='Y축: 0~5건은 선형, 5건 초과는 로그 간격 · 모든 권역·시간대 동일 축 · 통계는 원자료로 계산'
                fig.suptitle(f'{period_title} · {name}',fontsize=25,fontweight='bold',y=.99)
                fig.text(.5,.015,note,ha='center',fontsize=13,color='#444444')
                fig.subplots_adjust(left=.085 if regional else .13,right=.90 if kind=='hexbin' else .98,
                                    top=.78,bottom=.23,wspace=.19)
                stem=OUT/f'{"권역별" if regional else "전체126격자"}_{name}_{period}_공통축'
                if nonlinear_y: stem=stem.parent/(stem.name+'_비선형Y축')
                if kind=='jitter' and regional and nonlinear_y:
                    target=stem.parent/(stem.name+'_핑크회색갈색.png')
                    fig.savefig(target,dpi=300,facecolor='white',bbox_inches='tight',pad_inches=.18)
                else:
                    fig.savefig(stem.with_suffix('.png'),dpi=300,facecolor='white',bbox_inches='tight',pad_inches=.18)
                for ax in axes:
                    assert tuple(ax.get_xlim())==XLIM and tuple(ax.get_ylim())==((-.5,100) if nonlinear_y else YLIM)
                plt.close(fig)
                print(target if kind=='jitter' and regional and nonlinear_y else stem.with_suffix('.png'))
    print(pd.DataFrame(stats).to_string(index=False));print('공통 축:',XLIM,YLIM,'헥스빈 최대 빈도:',hexmax)


if __name__=='__main__':
    main('하루전체',kinds=('jitter',),regional_views=(True,),nonlinear_y=True)
    main('출근시간대',kinds=('jitter',),regional_views=(True,),nonlinear_y=True)
