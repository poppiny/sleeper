"""Sleeper asset pipeline: ComfyUI (FLUX.2 klein 4B + BiRefNet) -> candidates -> pick -> pixel art -> assets/*.png

usage:
  python tools/gen.py awake [id,...] [n]   n candidates per character (default 3)
  python tools/gen.py sleep [id,...] [n]   sleeping variants, referenced from the picked awake image
  python tools/gen.py bg day|night [n]     room backgrounds (night references the picked day room)
  python tools/gen.py pixel [name,...] [n] pixel-art redraw of picks, e.g. "pixel awake_tsuki,bg_day"
  python tools/gen.py sheet <prefix>       contact sheet of candidates, e.g. "awake" or "pix_sleep"
  python tools/gen.py pick <name> <k>      choose candidate k, e.g. "pick pix_awake_tsuki 1"
  python tools/gen.py build                pix_* picks -> assets/*.png + app icons
"""
import json, sys, time, uuid, shutil, random, urllib.request
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "tools" / "work"
ASSETS = ROOT / "assets"
COMFY = Path(r"C:\dev\ComfyUI")
API = "http://127.0.0.1:8188"

STYLE = ("Cute kawaii mascot character for a virtual pet game. Chibi proportions, soft pastel colors, "
         "thick clean dark brown outline, simple flat cel shading, smooth vector illustration. "
         "Only one character, full body, centered, facing the viewer. "
         "Plain pure white background, no ground shadow, no text, no letters.")

CHARS = {
    "egg": "A round pastel lavender egg covered with tiny yellow stars and crescent moons, a small blue striped "
           "nightcap with a white pom-pom sitting on top, the egg has a tiny peaceful sleeping face with closed eyes and rosy cheeks. Just an egg: no arms, no legs, no feet.",
    "baby": "A tiny round white mochi blob creature, soft and squishy, big sparkling black eyes, rosy pink cheeks, "
            "a small curl of lavender fluff on top of its head, tiny nub feet.",
    "moko": "A small round fluffy cream-colored lamb-like creature with a cloud-like wool body, short stubby legs, "
            "big sparkling eyes, rosy cheeks, tiny lavender horns, wearing a small blue striped nightcap.",
    "bosa": "A small round scruffy ash-gray creature with messy spiky unkempt fur, short stubby legs, "
            "grumpy half-closed tired eyes with dark circles, a crooked faded nightcap.",
    "tsuki": "An elegant fluffy midnight-blue cat-like creature with a glowing golden crescent moon mark on its forehead, "
             "a long fluffy tail with a little star at the tip, tiny twinkling stars in its fur, calm gentle eyes.",
    "hidamari": "A cheerful fluffy sunny-yellow lion-cub-like creature with a round fluffy orange mane shaped like the sun, "
                "big happy smile, rosy cheeks, holding a small sunflower.",
    "kumo": "A soft white fluffy cloud creature floating in the air, round puffy body like a cumulus cloud, "
            "relaxed happy half-closed eyes, rosy cheeks, tiny light-blue raindrop-shaped feet.",
    "neguse": "A chubby gray raccoon-like creature with wild messy bedhead hair sticking out in all directions, "
              "sleepy grumpy eyes with dark circles, hugging a slightly worn pillow.",
    "obake": "A cute little pale lavender ghost creature with a wispy tail instead of legs, droopy tired eyes with "
             "dark circles, a small pout, a faint blue glow around it.",
    "kujira": "A small magical flying whale creature whose body is a deep blue night sky filled with twinkling stars "
              "and a galaxy swirl, glowing star-shaped fins, gentle smile, floating.",
    "unicorn": "A magical fluffy pastel unicorn-like creature with a flowing aurora rainbow mane, a horn shaped like "
               "a golden crescent moon, small feathered wings, sparkles around it, dreamy gentle eyes.",
}

SLEEP = ("The same character as in the reference image, keeping exactly the same design, colors, proportions and art style. "
         "The character is now fast asleep: curled up peacefully, eyes closed, relaxed happy sleeping face. "
         "Only one character, full body, centered, plain pure white background, no ground shadow, no text, no letters, no Zzz.")

BG = {
    "day": ("Cozy pastel bedroom interior background for a cute virtual pet game. A round window showing a sunny blue sky "
            "with fluffy clouds, a fluffy round rug, a small bed with a patchwork quilt, potted plants, soft warm daylight. "
            "Flat illustration style, simple shapes, soft pastel colors, empty open floor space in the center. "
            "No characters, no animals, no text."),
    "night": ("The same room as in the reference image, same composition and style, but at night: calm dark navy blue lighting, "
              "the window shows a starry night sky with a crescent moon, a small night lamp glowing warmly. "
              "No characters, no animals, no text."),
}

PIXEL = ("Redraw the character from the reference image as a retro 16-bit pixel art game sprite, like a monster sprite from a SNES RPG. "
         "Keep exactly the same character design, pose, colors and signature features. "
         "Big chunky square pixels on a strict grid (the whole character is about 48 pixels tall), limited palette of clear saturated colors, "
         "crisp one-pixel dark outline, simple 2-3 tone cel shading, no anti-aliasing, no gradients, no blur. "
         "Readable at small size: few large flat color areas, no tiny sparkles or speckles. "
         "Only one character, full body, centered, plain pure white background, no text.")
PIXEL_BG = ("Redraw the reference image as a retro 16-bit pixel art game background, like a room in a SNES RPG. "
            "Same room, same composition, same lighting and colors. Big chunky square pixels on a strict grid (the image is about "
            "128 pixels wide), limited palette, no anti-aliasing, no blur. No characters, no animals, no text.")
PIX_H = {"egg": 26, "baby": 24, "moko": 34, "bosa": 34}  # sprite height in pixels (adults: 48) on a shared pixel scale


# ---------- ComfyUI ----------
def post(path, data):
    req = urllib.request.Request(API + path, json.dumps(data).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def get(path):
    return json.loads(urllib.request.urlopen(API + path).read())


def workflow(prompt, seed, prefix, ref=None, remove_bg=True, size=1024):
    """Node 22 = final image (RGBA when remove_bg), node 23 = raw RGB (kept as a reference for later edits)."""
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b-fp8.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b_fp8_mixed.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
        "12": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
        "13": {"class_type": "Flux2Scheduler", "inputs": {"steps": 4, "width": size, "height": size}},
        "14": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "16": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["15", 0], "guider": ["11", 0], "sampler": ["14", 0], "sigmas": ["13", 0], "latent_image": ["12", 0]}},
        "17": {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["3", 0]}},
    }
    pos, neg = ["4", 0], ["5", 0]
    if ref:
        g["6"] = {"class_type": "LoadImage", "inputs": {"image": ref}}
        g["7"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 16}}
        g["8"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["7", 0], "vae": ["3", 0]}}
        g["9"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": pos, "latent": ["8", 0]}}
        g["10"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": neg, "latent": ["8", 0]}}
        pos, neg = ["9", 0], ["10", 0]
    g["11"] = {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": pos, "negative": neg, "cfg": 1.0}}
    out = ["17", 0]
    if remove_bg:
        g["18"] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}}
        g["19"] = {"class_type": "RemoveBackground", "inputs": {"image": ["17", 0], "bg_removal_model": ["18", 0]}}
        g["20"] = {"class_type": "InvertMask", "inputs": {"mask": ["19", 0]}}
        g["21"] = {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["17", 0], "alpha": ["20", 0]}}
        g["23"] = {"class_type": "SaveImage", "inputs": {"images": ["17", 0], "filename_prefix": prefix + "_raw"}}
        out = ["21", 0]
    g["22"] = {"class_type": "SaveImage", "inputs": {"images": out, "filename_prefix": prefix}}
    return g


def run(jobs):
    """jobs: list of (workflow, dest stem Path). Writes <stem>.png and, if present, <stem>_raw.png."""
    cid = str(uuid.uuid4())
    pending = {post("/prompt", {"prompt": wf, "client_id": cid})["prompt_id"]: dest for wf, dest in jobs}
    while pending:
        time.sleep(2)
        for pid in list(pending):
            h = get(f"/history/{pid}").get(pid)
            if not h:
                continue
            dest = pending.pop(pid)
            if h.get("status", {}).get("status_str") == "error":
                print("ERROR", dest.name, h["status"].get("messages", [])[-1:], flush=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            for node, suffix in (("22", ".png"), ("23", "_raw.png")):
                for i in h["outputs"].get(node, {}).get("images", [])[:1]:
                    shutil.copy(COMFY / "output" / i["subfolder"] / i["filename"], dest.with_name(dest.name + suffix))
            print("ok", dest.name, flush=True)


def seed():
    return random.randint(1, 2**31)


# ---------- commands ----------
def cmd_awake(ids=None, n=3):
    ids = ids.split(",") if ids else list(CHARS)
    run([(workflow(f"{CHARS[c]} {STYLE}", seed(), f"sleeper/awake_{c}"), WORK / "cand" / f"awake_{c}_{k}")
         for c in ids for k in range(int(n))])


def cmd_sleep(ids=None, n=2):
    ids = ids.split(",") if ids else [c for c in CHARS if c != "egg"]
    run([(workflow(f"{SLEEP} Keep its signature features: {CHARS[c]}", seed(), f"sleeper/sleep_{c}", ref=f"sleeper/awake_{c}.png"),
          WORK / "cand" / f"sleep_{c}_{k}")
         for c in ids for k in range(int(n))])


def cmd_bg(kind, n=3):
    ref = "sleeper/bg_day.png" if kind == "night" else None
    run([(workflow(BG[kind], seed(), f"sleeper/bg_{kind}", ref=ref, remove_bg=False), WORK / "cand" / f"bg_{kind}_{k}")
         for k in range(int(n))])


def cmd_pixel(names=None, n=2):
    """Pixel-art redraw of picked images (awake_x, sleep_x, bg_x), referenced from the pick itself."""
    names = names.split(",") if names else sorted(p.stem for p in (WORK / "pick").glob("*.png") if not p.stem.startswith("pix_"))
    jobs = []
    for nm in names:
        kind, c = nm.split("_", 1)
        prompt = PIXEL_BG if kind == "bg" else PIXEL + (" It is fast asleep, curled up with its eyes closed." if kind == "sleep" else f" Signature features: {CHARS[c]}")
        jobs += [(workflow(prompt, seed(), f"sleeper/pix_{nm}", ref=f"sleeper/{nm}.png", remove_bg=kind != "bg"), WORK / "cand" / f"pix_{nm}_{k}")
                 for k in range(int(n))]
    run(jobs)


def cmd_sheet(prefix):
    files = sorted(p for p in (WORK / "cand").glob(prefix + "*.png") if not p.stem.endswith("_raw"))
    cols, s = 6, 256
    sheet = Image.new("RGB", (cols * s, (len(files) + cols - 1) // cols * (s + 18)), "#c9cfe0")
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(files):
        im = Image.open(p).convert("RGBA")
        if p.stem.startswith("pix_"):  # preview the final snapped pixel art
            im = grid(im, 128, 128, 48) if p.stem.startswith("pix_bg") else pixelate(im, 48)
            im = im.resize((im.width * (s // max(im.size)), im.height * (s // max(im.size))), Image.NEAREST)
        im.thumbnail((s, s))
        x, y = i % cols * s, i // cols * (s + 18)
        sheet.paste(im, (x, y), im)
        d.text((x + 4, y + s + 3), p.stem, fill="black")
    out = WORK / f"sheet_{prefix}.jpg"
    sheet.save(out, quality=88)
    print(out)


def cmd_pick(name, k):
    src = WORK / "cand" / f"{name}_{k}"
    (WORK / "pick").mkdir(parents=True, exist_ok=True)
    (COMFY / "input" / "sleeper").mkdir(parents=True, exist_ok=True)
    shutil.copy(src.with_name(src.name + ".png"), WORK / "pick" / f"{name}.png")
    raw = src.with_name(src.name + "_raw.png")
    shutil.copy(raw if raw.exists() else src.with_name(src.name + ".png"), COMFY / "input" / "sleeper" / f"{name}.png")
    print("picked", name, k)


def grid(im, w, h, colors=32):
    """Snap an AI 'pixel art' render onto a real w x h pixel grid. Each cell takes its most common palette color
    (or transparency), so small accents stay crisp instead of being averaged away."""
    im = im.convert("RGBA")
    pal = im.convert("RGB").quantize(colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    rgb, idx, alpha = pal.getpalette(), pal.load(), im.getchannel("A").load()
    out = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            votes = Counter(idx[i, j] if alpha[i, j] > 110 else -1
                            for j in range(y * im.height // h, (y + 1) * im.height // h)
                            for i in range(x * im.width // w, (x + 1) * im.width // w))
            c = votes.most_common(1)[0][0]
            if c >= 0:
                out.putpixel((x, y), (*rgb[c * 3:c * 3 + 3], 255))
    return out


def pixelate(im, h):
    """Crop a sprite to its silhouette, snap it to a grid about h pixels tall (at most 58 wide), add a 1px outline."""
    im = im.convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    s = min(h / im.height, 58 / im.width)
    sp = grid(im, max(1, round(im.width * s)), max(1, round(im.height * s)))
    c = Image.new("RGBA", (sp.width + 2, sp.height + 2))
    c.alpha_composite(sp, (1, 1))
    a, px = c.getchannel("A").load(), c.load()
    for y in range(c.height):
        for x in range(c.width):
            if not a[x, y] and any(0 <= x + dx < c.width and 0 <= y + dy < c.height and a[x + dx, y + dy]
                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = (31, 26, 51, 255)
    return c


def cmd_build():
    """pick/pix_* -> assets/*.png: 64x64 sprites on one shared pixel scale, 128x128 rooms, pixel app icons."""
    ASSETS.mkdir(exist_ok=True)
    for p in sorted((WORK / "pick").glob("pix_*.png")):
        kind, name = p.stem[4:].split("_", 1)
        im = Image.open(p)
        if kind == "bg":
            grid(im, 128, 128, 48).save(ASSETS / f"bg_{name}.png", optimize=True)
            continue
        h = PIX_H.get(name, 48)
        sp = pixelate(im, round(h * 0.8) if kind == "sleep" else h)
        c = Image.new("RGBA", (64, 64))  # bottom-aligned: every sprite stands on the same floor line
        c.alpha_composite(sp, ((64 - sp.width) // 2, 62 - sp.height))
        c.save(ASSETS / (f"{name}.png" if kind == "awake" else f"{name}_sleep.png"), optimize=True)
    egg = Image.open(ASSETS / "egg.png")
    egg = egg.crop(egg.getchannel("A").getbbox())
    for size, fname in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        k = int(size * 0.62 / max(egg.size))
        e = egg.resize((egg.width * k, egg.height * k), Image.NEAREST)
        bg = Image.new("RGBA", (size, size), "#1d1b3a")
        bg.alpha_composite(e, ((size - e.width) // 2, (size - e.height) // 2))
        bg.convert("RGB").save(ASSETS / fname)
    print("built", len(list(ASSETS.iterdir())), "files")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"awake": cmd_awake, "sleep": cmd_sleep, "bg": cmd_bg, "pixel": cmd_pixel, "sheet": cmd_sheet, "pick": cmd_pick,
     "build": cmd_build}[cmd](*args)
