"""Sleeper asset pipeline: ComfyUI (FLUX.2 klein 4B + BiRefNet) -> candidates -> pick -> assets/*.webp

usage:
  python tools/gen.py awake [id,...] [n]   n candidates per character (default 3)
  python tools/gen.py sleep [id,...] [n]   sleeping variants, referenced from the picked awake image
  python tools/gen.py bg day|night [n]     room backgrounds (night references the picked day room)
  python tools/gen.py sheet <prefix>       contact sheet of candidates, e.g. "awake" or "sleep_tsuki"
  python tools/gen.py pick <name> <k>      choose candidate k, e.g. "pick awake_tsuki 2"
  python tools/gen.py build                picked -> assets/*.webp + app icons
"""
import json, sys, time, uuid, shutil, random, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

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


def cmd_sheet(prefix):
    files = sorted(p for p in (WORK / "cand").glob(prefix + "*.png") if not p.stem.endswith("_raw"))
    cols, s = 6, 256
    sheet = Image.new("RGB", (cols * s, (len(files) + cols - 1) // cols * (s + 18)), "#c9cfe0")
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(files):
        im = Image.open(p).convert("RGBA")
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


def cmd_build():
    ASSETS.mkdir(exist_ok=True)
    for p in sorted((WORK / "pick").glob("*.png")):
        kind, name = p.stem.split("_", 1)
        im = Image.open(p).convert("RGBA")
        if kind == "bg":
            im.convert("RGB").resize((768, 768), Image.LANCZOS).save(ASSETS / f"bg_{name}.webp", quality=80)
            continue
        a = im.getchannel("A").point(lambda v: 0 if v < 40 else (255 if v > 215 else v))
        im.putalpha(a)
        im = im.crop(a.getbbox())
        im.thumbnail((480, 480), Image.LANCZOS)
        # bottom-aligned square canvas: every sprite stands on the same floor line
        c = Image.new("RGBA", (512, 512))
        c.alpha_composite(im, ((512 - im.width) // 2, 512 - 8 - im.height))
        c.save(ASSETS / (f"{name}.webp" if kind == "awake" else f"{name}_sleep.webp"), quality=86, method=6)
    egg = Image.open(ASSETS / "egg.webp").convert("RGBA")
    egg = egg.crop(egg.getchannel("A").getbbox())
    for size, fname in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        bg = ImageOps.colorize(Image.linear_gradient("L").resize((size, size)), "#2b2d6e", "#b9a7ea").convert("RGBA")
        e = egg.copy()
        e.thumbnail((int(size * 0.72), int(size * 0.72)), Image.LANCZOS)
        bg.alpha_composite(e, ((size - e.width) // 2, (size - e.height) // 2 + size // 40))
        bg.convert("RGB").save(ASSETS / fname)
    print("built", len(list(ASSETS.iterdir())), "files")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"awake": cmd_awake, "sleep": cmd_sleep, "bg": cmd_bg, "sheet": cmd_sheet, "pick": cmd_pick, "build": cmd_build}[cmd](*args)
