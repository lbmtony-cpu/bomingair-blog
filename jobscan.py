#!/usr/bin/env python3
"""
Scan the local iCloud photo library for job-site photo clusters.

Reads EXIF (DateTimeOriginal + GPS) from JPG/HEIC, maps GPS to the nearest
service-area city, groups photos into (date, city) clusters = one job visit.
Skips cloud placeholders (not yet downloaded) unless --hydrate is passed.
Writes _jobscan.json.

Usage: jobscan.py [N_recent_files] [--hydrate]   (default 500)
"""
import os, sys, json, math, pathlib
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

LIB = pathlib.Path(r"E:\iCloudPhotos\Photos")
OUT = pathlib.Path(__file__).parent / "_jobscan.json"

CITY_COORDS = {
    "Chino Hills": (33.9898, -117.7326), "Chino": (34.0122, -117.6889),
    "Diamond Bar": (34.0286, -117.8103), "Walnut": (34.0203, -117.8653),
    "Rowland Heights": (33.9761, -117.9053), "Pomona": (34.0551, -117.7500),
    "Ontario": (34.0633, -117.6509), "Corona": (33.8753, -117.5664),
    "Eastvale": (33.9525, -117.5848), "Norco": (33.9310, -117.5487),
    "Yorba Linda": (33.8886, -117.8131), "Brea": (33.9167, -117.9000),
    "Montclair": (34.0775, -117.6897), "Upland": (34.0975, -117.6484),
    "Rancho Cucamonga": (34.1064, -117.5931), "Fontana": (34.0922, -117.4350),
    "Riverside": (33.9533, -117.3962), "Anaheim Hills": (33.8555, -117.7583),
    "Moreno Valley": (33.9425, -117.2297), "West Covina": (34.0686, -117.9390),
    "Hacienda Heights": (33.9931, -117.9687), "Fullerton": (33.8704, -117.9242),
    "Anaheim": (33.8366, -117.9143), "Irvine": (33.6846, -117.8265),
}


def dist_mi(a, b, c, d):
    r = 3959
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(x))


def nearest_city(lat, lon):
    best, bd = None, 1e9
    for c, (clat, clon) in CITY_COORDS.items():
        d = dist_mi(lat, lon, clat, clon)
        if d < bd:
            best, bd = c, d
    return (best, round(bd, 1)) if bd <= 12 else (None, round(bd, 1))


def to_deg(v):
    try:
        d, m, s = v
        return float(d) + float(m)/60 + float(s)/3600
    except Exception:
        return None


def read_exif(fp):
    try:
        im = Image.open(fp)
        ex = im.getexif()
        if not ex:
            return None, None, None
        dt = ex.get(306) or ex.get(36867)
        ifd = ex.get_ifd(0x8825)
        lat = lon = None
        if ifd:
            la, lo = ifd.get(2), ifd.get(4)
            if la and lo:
                lat, lon = to_deg(la), to_deg(lo)
                if lat is not None and ifd.get(1) == "S":
                    lat = -lat
                if lon is not None and ifd.get(3) == "W":
                    lon = -lon
        if not dt:
            exif_ifd = ex.get_ifd(0x8769)
            dt = exif_ifd.get(36867) if exif_ifd else None
        return dt, lat, lon
    except Exception:
        return None, None, None


def is_placeholder(p):
    a = p.stat().st_file_attributes
    return bool(a & 0x400000) or bool(a & 0x1000)


def main():
    args = sys.argv[1:]
    hydrate = "--hydrate" in args
    nums = [a for a in args if a.isdigit()]
    n = int(nums[0]) if nums else 500
    files = [p for p in LIB.iterdir()
             if p.suffix.lower() in (".jpg", ".jpeg", ".heic", ".png")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    clusters = {}
    scanned = skipped_ph = no_gps = 0
    for p in files:
        if scanned >= n:
            break
        try:
            if not hydrate and is_placeholder(p):
                skipped_ph += 1
                continue
        except Exception:
            continue
        scanned += 1
        dt, lat, lon = read_exif(p)
        if lat is None or dt is None:
            no_gps += 1
            continue
        city, d = nearest_city(lat, lon)
        if not city:
            continue
        day = dt.split(" ")[0].replace(":", "-")
        key = f"{day}|{city}"
        clusters.setdefault(key, []).append({"file": str(p), "time": dt, "mi": d})

    out = [{"date": k.split("|")[0], "city": k.split("|")[1],
            "count": len(v), "photos": v}
           for k, v in sorted(clusters.items(), reverse=True)]
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"scanned {scanned} hydrated files (skipped {skipped_ph} placeholders, {no_gps} w/o gps)")
    print(f"clusters: {len(out)}")
    for c in out[:15]:
        print(f"  {c['date']}  {c['city']:18s} x{c['count']}")


if __name__ == "__main__":
    main()
