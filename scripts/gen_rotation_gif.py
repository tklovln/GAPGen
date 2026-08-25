#!/usr/bin/env python3
"""gen_rotation_gif.py — 2D sprite 自轉動畫(GIF)生成實驗。

用法:
  .venv/bin/python scripts/gen_rotation_gif.py [sprite路徑] [--frames 10]

做法: 重用 art_pipeline.gemini_api 的圖生圖。每一幀都給兩張參考圖 —
  A) 原始 sprite(鎖身分/畫風)  B) 前一幀(鎖旋轉連續性)
prompt 只講一件事: 同一個物件、繞垂直軸轉 N 度、其他全部不變。

產出: generated_art/rotation_test/<name>/frame_XX.png + rotation.gif
"""
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from art_pipeline import gemini_api  # noqa: E402
from art_pipeline.postprocess import _flood_fill_from_border  # noqa: E402


def strip_white_bg(png_bytes: bytes, thresh: int = 235) -> bytes:
    """白底去背：近白像素中「與影像邊框連通」的整片才移除，主體內部白色保留。"""
    import io
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    data = np.array(im)
    rgb = data[..., :3]
    candidate = (rgb > thresh).all(axis=-1) & (data[..., 3] > 0)
    data[..., 3][_flood_fill_from_border(candidate)] = 0
    out = io.BytesIO()
    Image.fromarray(data).save(out, format='PNG')
    return out.getvalue()

# 精簡直觀的 turntable prompt：一句身分、一句動作、一句凍結其餘變因
PROMPT = (
    'Reference A is the original sprite; reference B is the previous rotation frame.\n'
    'Redraw the exact same object as A, rotated {deg} degrees clockwise around its '
    'vertical axis, like one frame of a turntable animation.\n'
    'Keep everything else identical to A: hand-drawn ink style, line weight, colors, '
    'proportions, scale, centered composition, plain white background. '
    'Change ONLY the viewing angle.'
)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('sprite', nargs='?',
                    default='generated_art/deo_cat_ip/sprites/Soda90.png')
    ap.add_argument('--frames', type=int, default=10)
    args = ap.parse_args()

    src = PROJECT_ROOT / args.sprite
    assert src.is_file(), f'找不到 sprite: {src}'
    out_dir = PROJECT_ROOT / 'generated_art' / 'rotation_test' / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    original = src.read_bytes()
    client = gemini_api.get_client()
    model = gemini_api.DEFAULT_IMAGE_MODEL
    step = 360 // args.frames

    prev = original
    frame_paths = []
    for i in range(args.frames):
        deg = i * step
        fp = out_dir / f'frame_{i:02d}.png'
        frame_paths.append(fp)
        if fp.exists():
            print(f'[{i+1}/{args.frames}] {deg:3d}° 已存在，跳過')
            prev = fp.read_bytes()
            continue
        if deg == 0:
            fp.write_bytes(original)  # 0° 就是原圖，不浪費一次生成
            print(f'[{i+1}/{args.frames}]   0° = 原圖')
            continue
        print(f'[{i+1}/{args.frames}] 生成 {deg:3d}° …', flush=True)
        png = gemini_api.generate_image(
            client, model, PROMPT.format(deg=deg),
            ref_images=[(original, 'Reference A: original sprite'),
                        (prev, 'Reference B: previous rotation frame')],
        )
        png = strip_white_bg(png)
        fp.write_bytes(png)
        prev = png

    # 串 GIF
    from PIL import Image
    frames = []
    for fp in frame_paths:
        im = Image.open(fp).convert('RGBA')
        bg = Image.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.getchannel('A'))
        frames.append(bg.resize((512, 512)))
    gif = out_dir / 'rotation.gif'
    frames[0].save(gif, save_all=True, append_images=frames[1:],
                   duration=140, loop=0)
    print(f'\nGIF: {gif}')


if __name__ == '__main__':
    main()
