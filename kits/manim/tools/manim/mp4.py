"""Read an MP4 file's frame count, length and picture size without ffprobe or
Manim: walk the ISO-BMFF boxes (moov > trak > mdia > mdhd, minf > stbl > stts,
tkhd). Stdlib only, so the checks run anywhere plain python3 does."""
import struct


def _boxes(data, start, end):
    i = start
    while i + 8 <= end:
        size, kind = struct.unpack(">I4s", data[i:i + 8])
        head = 8
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            head = 16
        elif size == 0:
            size = end - i
        if size < head or i + size > end:
            raise ValueError(f"a {kind!r} box runs past the end of the file")
        yield kind.decode("latin-1"), i + head, i + size
        i += size


def _find(data, start, end, path):
    for kind, a, b in _boxes(data, start, end):
        if kind == path[0]:
            return (a, b) if len(path) == 1 else _find(data, a, b, path[1:])
    return None


def video_info(data):
    """{'frames', 'ms', 'width', 'height', 'brand'} of the first video track."""
    if data[4:8] != b"ftyp":
        raise ValueError("not an MP4 file: no ftyp box first")
    brand = data[8:12].decode("latin-1")
    moov = _find(data, 0, len(data), ["moov"])
    if not moov:
        raise ValueError("no moov box")
    for kind, a, b in _boxes(data, *moov):
        if kind != "trak":
            continue
        hdlr = _find(data, a, b, ["mdia", "hdlr"])
        if not hdlr or data[hdlr[0] + 8:hdlr[0] + 12] != b"vide":
            continue
        mdhd = _find(data, a, b, ["mdia", "mdhd"])
        version = data[mdhd[0]]
        if version == 1:
            timescale, duration = struct.unpack(">IQ", data[mdhd[0] + 20:mdhd[0] + 32])
        else:
            timescale, duration = struct.unpack(">II", data[mdhd[0] + 12:mdhd[0] + 20])
        stts = _find(data, a, b, ["mdia", "minf", "stbl", "stts"])
        n = struct.unpack(">I", data[stts[0] + 4:stts[0] + 8])[0]
        frames = sum(struct.unpack(">I", data[stts[0] + 8 + 8 * k:stts[0] + 12 + 8 * k])[0] for k in range(n))
        tkhd = _find(data, a, b, ["tkhd"])
        w, h = struct.unpack(">II", data[tkhd[1] - 8:tkhd[1]])
        return {"frames": frames, "ms": round(duration * 1000 / timescale), "width": w >> 16,
                "height": h >> 16, "brand": brand}
    raise ValueError("no video track")


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG file")
    return struct.unpack(">II", data[16:24])
