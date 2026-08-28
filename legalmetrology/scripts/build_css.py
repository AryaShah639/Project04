#!/usr/bin/env python3
"""Build a standalone Tailwind CSS file for the LM Compliance UI.
Uses the Tailwind standalone CLI via the Play CDN JS evaluated with a stub DOM,
extracting the CSS to static/css/ui.css."""
import re, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---- collect classes used across templates (plus safelist for dynamic ones) ----
class_names = set()
for dirpath, _, files in os.walk(os.path.join(ROOT, "templates")):
    for f in files:
        src = open(os.path.join(dirpath, f)).read()
        class_names.update(re.findall(r'class="([^"]+)"', src))
        class_names.update(re.findall(r"class='([^']+)'", src))

all_tokens = set()
for c in class_names:
    all_tokens.update(c.split())

safelist = set("""
w-6 h-6 w-8 h-8 w-10 h-10 w-12 h-12 w-14 h-14 w-16 h-16 w-20 h-20 w-24 h-24
w-32 w-40 w-48 w-56 w-64 w-72 w-80 w-96
h-1 h-1.5 h-2 h-2.5 h-3 h-4 h-5 h-6 h-7 h-8 h-9 h-10 h-12 h-14 h-16 h-20 h-24
w-1 w-1.5 w-2 w-2.5 w-3 w-4 w-5 w-6 w-7 w-8 w-9 w-10 w-11 w-12 w-14 w-16 w-20
p-0 p-1 p-2 p-3 p-4 p-5 p-6 p-8 p-10 px-1 px-2 px-3 px-4 px-5 px-6 px-8 py-1 py-2 py-3 py-4 py-5 py-6 py-8
pt-2 pt-3 pt-4 pt-6 pb-2 pb-3 pb-4 pb-6 pl-3 pl-4 pr-3 pr-4 pr-8
m-0 m-1 m-2 m-4 m-6 mt-1 mt-2 mt-3 mt-4 mt-5 mt-6 mt-8 mt-10 mt-12 mb-1 mb-2 mb-3 mb-4 mb-5 mb-6 mb-8 mb-10 ml-1 ml-2 ml-3 ml-4 mr-1 mr-2 mr-3 mr-4 mr-6
gap-0 gap-1 gap-2 gap-3 gap-4 gap-5 gap-6 gap-8 gap-x-3 gap-x-4 gap-y-2 gap-y-3 gap-y-4
grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 grid-cols-5 grid-cols-6 grid-cols-7
grid-cols-12 col-span-1 col-span-2 col-span-3 col-span-4 col-span-5 col-span-6
col-span-7 col-span-8 col-span-9 col-span-10 col-span-12
text-xs text-sm text-base text-lg text-xl text-2xl text-3xl text-4xl
text-[11px] text-[13px] text-[15px] text-[26px] text-[28px] text-[32px]
leading-4 leading-5 leading-6 leading-7 leading-8 leading-9 leading-10
rounded rounded-sm rounded-md rounded-lg rounded-xl rounded-2xl rounded-full
font-normal font-medium font-semibold font-bold font-extrabold
text-slate-400 text-slate-500 text-slate-600 text-slate-700 text-slate-800 text-slate-900
text-white text-gray-400 text-gray-500 text-neutral-400 text-neutral-500
text-blue-50 text-blue-100 text-blue-200 text-blue-500 text-blue-600 text-blue-700
text-emerald-500 text-emerald-600 text-emerald-700 text-green-500 text-green-600 text-green-700
text-amber-500 text-amber-600 text-amber-700 text-orange-600 text-red-400 text-red-500 text-red-600 text-red-700
text-indigo-500 text-indigo-600
bg-white bg-slate-50 bg-slate-100 bg-slate-200 bg-slate-800 bg-slate-900
bg-gray-50 bg-gray-100 bg-gray-200 bg-neutral-100 bg-neutral-200 bg-neutral-50
bg-blue-50 bg-blue-100 bg-blue-500 bg-blue-600 bg-blue-700 bg-indigo-600 bg-indigo-50
bg-emerald-50 bg-emerald-100 bg-emerald-500 bg-emerald-600 bg-emerald-700 bg-green-50 bg-green-100 bg-green-500 bg-green-600
bg-amber-50 bg-amber-100 bg-amber-500 bg-amber-600 bg-red-50 bg-red-100 bg-red-500 bg-red-600 bg-red-700
bg-teal-50 bg-teal-100 bg-teal-600 bg-rose-50 bg-rose-100 bg-violet-50 bg-violet-100 bg-sky-50 bg-sky-100
border border-0 border-2 border-4 border-t border-b
border-slate-100 border-slate-200 border-slate-300 border-gray-200 border-gray-300
border-blue-200 border-blue-600 border-emerald-200 border-emerald-600 border-red-200 border-red-600
border-amber-200 border-amber-600 border-slate-800 border-white/10 border-white/20 border-white/5
border-l-4 border-l-blue-600 border-l-emerald-500 border-l-amber-500 border-l-red-500 border-l-slate-300
divide-y divide-slate-100 divide-gray-100
shadow-sm shadow-md shadow-lg shadow-xl shadow-none
ring-1 ring-2 ring-slate-200 ring-blue-500/30 ring-emerald-500/30 ring-red-500/30 ring-amber-500/30
ring-offset-2
inline-flex items-center justify-center flex flex-col flex-row flex-1 flex-wrap flex-shrink-0
grid block hidden inline-block
max-w-2xl max-w-3xl max-w-4xl max-w-5xl max-w-6xl max-w-xl max-w-sm max-w-md max-w-lg
min-w-0 w-full h-full
absolute relative sticky fixed inset-0 top-0 left-0 right-0 z-10 z-20 z-30 z-40 z-50
overflow-hidden overflow-x-auto overflow-y-auto overflow-visible
truncate line-clamp-1 line-clamp-2 whitespace-nowrap break-words
text-left text-center text-right uppercase tracking-tight tracking-wide
object-cover object-contain object-center aspect-video aspect-square
cursor-pointer cursor-default select-none pointer-events-none
opacity-40 opacity-50 opacity-60 opacity-70 opacity-80
transition duration-150 ease-in-out hover:bg-slate-50 hover:bg-slate-100 hover:bg-blue-700 hover:bg-blue-50
hover:bg-slate-700 hover:bg-slate-800 hover:text-white hover:text-blue-700 hover:text-slate-900
hover:shadow-md hover:border-slate-300 hover:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500
focus:border-blue-500 focus:ring-0
group group-hover:block group-hover:opacity-100
space-x-1 space-x-2 space-x-3 space-y-1 space-y-2 space-y-3 space-y-4
sm:grid-cols-2 sm:grid-cols-3 lg:grid-cols-2 lg:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4
md:flex-row md:items-center md:justify-between md:flex lg:flex lg:flex-row
sm:text-sm sm:text-lg sm:px-6 md:col-span-2 lg:col-span-3
invert saturate-0
animate-pulse animate-spin
""".split())

all_classes = sorted(all_tokens | safelist)
print(f"tokens: {len(all_tokens)} + safelist -> {len(all_classes)}")

# ---- run tailwind via node (standalone CLI from Play CDN is a full bundle) ----
cfg = {
    "theme": {
        "extend": {
            "fontFamily": {"sans": ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]},
            "colors": {
                "brand": {"50": "#eef6ff", "100": "#d9ebff", "200": "#bcdcff", "300": "#8ec6ff",
                          "400": "#59a6ff", "500": "#3283f6", "600": "#1b66df", "700": "#1451b8",
                          "800": "#174595", "900": "#193c78", "950": "#14264a"},
            },
            "boxShadow": {
                "card": "0 1px 2px 0 rgb(16 24 40 / 0.04), 0 1px 3px 0 rgb(16 24 40 / 0.06)",
                "lift": "0 4px 12px -2px rgb(16 24 40 / 0.12)",
            },
        }
    },
    "plugins": [],
}
import json, tempfile
cfg_path = os.path.join(HERE, "tailwind.config.json")
json.dump(cfg, open(cfg_path, "w"))

# build a small html file listing classes
probe = os.path.join(HERE, "_probe.html")
with open(probe, "w") as f:
    f.write('<div class="%s"></div>' % " ".join(all_classes))

# Use the standalone tailwind CLI if available, else fallback: download node binary via npm-free path
cli = None
for cand in ["npx", "node"]:
    try:
        subprocess.run([cand, "--version"], capture_output=True, check=True, timeout=15)
        cli = cand
        break
    except Exception:
        continue

if cli is None:
    print("no node available; cannot build tailwind — aborting")
    sys.exit(1)

try:
    out = subprocess.run(["npx", "-y", "tailwindcss@3.4.17", "-c", cfg_path,
                          "-i", os.path.join(HERE, "_input.css"), "-o",
                          os.path.join(ROOT, "static/css/ui.css"), "--minify",
                          "--content", probe],
                         capture_output=True, text=True, timeout=240)
    if out.returncode != 0:
        print("tailwind build failed:", out.stderr[-800:])
        sys.exit(1)
    print("tailwind ok:", len(open(os.path.join(ROOT, "static/css/ui.css")).read()), "bytes")
except FileNotFoundError:
    print("npx not available")
    sys.exit(1)
