"""원래 통합 격자 지도를 읽는 방법을 보여 주는 공통 범례 예시.

프로젝트 루트에서 python code/03_eda/figure06_legend.py 실행.
실제 분석격자 그림은 변경하지 않고 범례용 PNG/PDF만 생성한다.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Rectangle


def main():
    root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'config.py').is_file())
    for font in [Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf',
                 Path(r'C:\Windows\Fonts\malgunbd.ttf'),
                 Path('/Library/Fonts/NanumGothicBold.ttf'),
                 Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')]:
        if font.is_file():
            fm.fontManager.addfont(str(font))
            plt.rcParams['font.family'] = fm.FontProperties(fname=str(font)).get_name()
            break
    plt.rcParams.update({'axes.unicode_minus':False,'font.weight':'bold','pdf.fonttype':42})
    colors = {'감소':'#D73027','유지':'#EEEEEE','증가':'#2166AC'}
    fig, ax = plt.subplots(figsize=(13, 5.7))
    fig.patch.set_facecolor('white')
    ax.set_xlim(0,13);ax.set_ylim(0,5.7);ax.set_aspect('equal');ax.axis('off')
    ax.text(6.5,5.35,'격자별 색상 표현 예시',ha='center',va='center',fontsize=24)
    ax.text(6.5,4.85,'격자 왼쪽: 하루 전체    /    격자 오른쪽: 출근시간대',
            ha='center',va='center',fontsize=16,color='#333333')
    examples = [(2.2,'동일한 변화','감소','감소'),
                (6.5,'반대 방향','증가','감소'),
                (10.8,'유지 여부 차이','유지','감소')]
    for center,heading,day,am in examples:
        ax.text(center,4.15,heading,ha='center',va='center',fontsize=20)
        left,bottom,size=center-.58,2.65,1.16
        ax.add_patch(Rectangle((left,bottom),size/2,size,facecolor=colors[day],edgecolor='none'))
        ax.add_patch(Rectangle((center,bottom),size/2,size,facecolor=colors[am],edgecolor='none'))
        ax.add_patch(Rectangle((left,bottom),size,size,fill=False,
                               edgecolor='#FFD400' if day!=am else '#333333',
                               linewidth=5 if day!=am else 1.6))
        ax.text(center,2.10,f'하루 전체 {day} / 출근 {am}',ha='center',va='center',fontsize=16)
    y=.78
    for x,label in [(1.5,'감소'),(4.2,'유지'),(6.9,'증가'),(9.25,'변화 구분 불일치')]:
        ax.add_patch(Rectangle((x-.18,y-.15),.34,.30,
                               facecolor='white' if label=='변화 구분 불일치' else colors[label],
                               edgecolor='#FFD400' if label=='변화 구분 불일치' else '#555555',
                               linewidth=3 if label=='변화 구분 불일치' else 1.2))
        ax.text(x+.31,y,label,ha='left',va='center',fontsize=17)
    fig.subplots_adjust(left=.015,right=.985,top=.99,bottom=.01)
    output=root/'results/paper/figures';output.mkdir(parents=True,exist_ok=True)
    for ext in ['png','pdf']:
        fig.savefig(output/f'격자별_색상표현_범례.{ext}',dpi=400,facecolor='white',
                    bbox_inches='tight',pad_inches=.12)
    plt.close(fig)
    print('격자별_색상표현_범례.png / PDF 생성 완료')

if __name__=='__main__':main()
