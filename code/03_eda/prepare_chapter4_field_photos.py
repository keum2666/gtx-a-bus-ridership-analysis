"""보관된 현장답사 원본 사진을 방향 보정하여 논문용으로 배치한다."""
from pathlib import Path
import json
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/paper/sources/3_1_3_현장답사'
OUT = ROOT / 'results/paper/figures'
FONT = Path.home() / 'Library/Fonts/KoPubWorld Dotum Bold.ttf'


def photo(name, clockwise=0):
    with Image.open(SOURCE / name) as im:
        result = ImageOps.exif_transpose(im).convert('RGB')
    if clockwise:
        result = result.rotate(-clockwise, expand=True)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    labels = ['운정중앙역 버스 환승센터', '운정중앙역 임시주차장']
    names = [('s17_p2.jpeg', 0), ('s17_p0.jpeg', 90)]
    width, height, gap, margin, label_height = 1440, 1080, 32, 24, 100
    fig = Image.new('RGB', (2 * width + gap + 2 * margin,
                            height + label_height + 2 * margin), 'white')
    draw = ImageDraw.Draw(fig)
    font = ImageFont.truetype(str(FONT), 48)
    for i, ((name, angle), label) in enumerate(zip(names, labels)):
        im = photo(name, angle)
        im.thumbnail((width, height), Image.Resampling.LANCZOS)
        x = margin + i * (width + gap)
        fig.paste(im, (x + (width - im.width) // 2, margin + (height - im.height) // 2))
        box = draw.textbbox((0, 0), label, font=font)
        draw.text((x + (width - (box[2] - box[0])) / 2, margin + height + 24),
                  label, fill='#1D1D1D', font=font)
    fig.save(OUT / '그림20_운정중앙역_환승센터_임시주차장_현장답사.png', dpi=(300, 300))
    daegok = photo('s23_p1.jpeg', 90)
    daegok.save(OUT / '그림21_대곡역_출입구_주변도로_현장답사.png', dpi=(300, 300))
    provenance = {
        '그림20': {'원본사진': [n for n, _ in names], '처리': '방향 보정, 비율 유지 축소 및 나란히 배치'},
        '그림21': {'원본사진': 's23_p1.jpeg', '처리': '시계 방향 90도 회전'},
        '기존출처정보': str(SOURCE.relative_to(ROOT) / '출처.json'),
        '내용편집': '없음',
    }
    record = ROOT / 'results/paper/sources/4_1_현장답사'
    record.mkdir(parents=True, exist_ok=True)
    (record / '출처.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2))
    print('그림 20·21 생성 완료')


if __name__ == '__main__':
    main()
