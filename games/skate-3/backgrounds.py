"""Pack user-supplied 4:3 art into a COPY of Skate 3's frontend archive.

Requires Pillow >= 12. No game assets or generated artwork are distributed.
Never changes the source archive. Use alongside this game's APK patch.
"""
import argparse
import io
import struct
from pathlib import Path


def u32(data, offset):
    return struct.unpack_from('>I', data, offset)[0]


def unpack_refpack(data, expected):
    if data[:2] != b'\x10\xfb' or int.from_bytes(data[2:5], 'big') != expected:
        raise ValueError('Unsupported frontend compression header')
    out = bytearray()
    p = 5
    while p < len(data):
        a = data[p]
        p += 1
        length = 0
        distance = 0
        if a < 128:
            b = data[p]
            p += 1
            literal, distance, length = a & 3, ((a & 96) << 3) + b + 1, ((a & 28) >> 2) + 3
        elif a < 192:
            b, c = data[p:p+2]
            p += 2
            literal, distance, length = b >> 6, ((b & 63) << 8) + c + 1, (a & 63) + 4
        elif a < 224:
            b, c, e = data[p:p+3]
            p += 3
            literal, distance, length = a & 3, ((a & 16) << 12) + (b << 8) + c + 1, ((a & 12) << 6) + e + 5
        else:
            literal = ((a & 31) << 2) + 4 if a < 252 else a & 3
        if p+literal > len(data) or len(out)+literal+length > expected:
            raise ValueError('Truncated or oversized RefPack payload')
        out.extend(data[p:p+literal])
        p += literal
        if length and distance > len(out):
            raise ValueError('Invalid RefPack back-reference')
        for _ in range(length):
            out.append(out[-distance])
        if a >= 252:
            if len(out) != expected:
                raise ValueError('Incomplete RefPack payload')
            return bytes(out)
    raise ValueError('Missing RefPack end marker')


def entries(data):
    if data[:4] != b'EB\0\3':
        raise ValueError('Expected an EA EB version 3 archive')
    count = u32(data, 4)
    flags = int.from_bytes(data[8:10], 'big')
    align = data[10]
    names = u32(data, 12)
    filename_length, folder_length = data[20:22]
    folders = (names + count*filename_length + 15) & ~15
    if not 0 < count < 10000 or flags != 0x10 or align != 6 or filename_length < 3 or not folder_length:
        raise ValueError('Unsupported frontend archive layout')
    types = 48 + count*16
    if types+count > names or folders > len(data):
        raise ValueError('Invalid archive directory bounds')
    result = []
    for i in range(count):
        toc = 48+i*16
        offset, compressed, size = struct.unpack_from('>III', data, toc)
        offset <<= align
        n = names+i*filename_length
        folder = int.from_bytes(data[n:n+2], 'big')
        f = folders+folder*folder_length
        if f+folder_length > len(data) or offset+(compressed or size) > len(data):
            raise ValueError('Archive member is outside the file')
        name = data[f:f+folder_length].split(b'\0')[0] + b'/' + data[n+2:n+filename_length].split(b'\0')[0]
        result.append((name.decode('ascii'), toc, types+i, offset, compressed, size))
    if len({e[0] for e in result}) != count:
        raise ValueError('Duplicate archive paths')
    return result


def texture_records(data):
    from PIL import Image
    if data[:16] != b'\x89RW4xb2\0\r\n\x1a\n\x01\x20\x04\0':
        raise ValueError('Expected a big-endian Xbox 360 texture arena')
    table, count, base = u32(data, 0x30), u32(data, 0x20), u32(data, 0x44)
    if count > 512 or table+count*24 > len(data) or base > len(data):
        raise ValueError('Invalid texture directory bounds')
    result = []
    for i in range(count):
        off, _, size, _, _, kind = struct.unpack_from('>6I', data, table+i*24)
        if kind != 0x200e8:
            continue
        if size != 52 or off+52 > base:
            raise ValueError('Unrecognized texture descriptor')
        fetch = struct.unpack_from('>6I', data, off+28)
        fmt = fetch[1] & 63
        if fmt not in (18, 20) or fetch[0] >> 31:
            continue
        width, height = (fetch[2] & 8191)+1, ((fetch[2] >> 13) & 8191)+1
        resource = fetch[1] >> 12
        if resource >= count:
            raise ValueError('Invalid texture resource index')
        resource_offset, _, allocation, _, _, resource_type = struct.unpack_from('>6I', data, table+resource*24)
        begin = base+resource_offset
        if resource_type != 0x10031 or begin+allocation > len(data):
            raise ValueError('Invalid texture resource range')
        pitch = ((fetch[0] >> 22) & 511)*32
        block = 8 if fmt == 18 else 16
        row = ((width+3)//4)*block
        stride = max(width,pitch)//4*block
        raw = b''.join(data[begin+y*stride:begin+y*stride+row] for y in range((height+3)//4))
        raw = bytes(b for j in range(0,len(raw),2) for b in raw[j:j+2][::-1])
        image = Image.frombytes('RGBA',(width,height),raw,'bcn',(1 if fmt==18 else 3,))
        result.append((off, begin, allocation, fetch, image))
    return result


def replace_texture(data, record, image):
    off, begin, allocation, fetch, _ = record
    width, height = image.size
    stream = io.BytesIO()
    image.convert('RGB').save(stream, format='DDS', pixel_format='DXT1')
    raw = stream.getvalue()[128:]
    raw = bytes(b for j in range(0,len(raw),2) for b in raw[j:j+2][::-1])
    if width % 128 or len(raw) > allocation:
        raise ValueError('Replacement exceeds the existing texture allocation')
    data[begin:begin+allocation] = raw + bytes(allocation-len(raw))
    fetch = list(fetch)
    fetch[0] = (fetch[0] & ~(511<<22)) | ((width//32)<<22)
    fetch[1] = (fetch[1] & ~63) | 18
    fetch[2] = (width-1) | ((height-1)<<13)
    struct.pack_into('>6I', data, off+28, *fetch)


def replace_art(data, art, title):
    from PIL import Image
    records = texture_records(data)
    result = bytearray(data)
    if title:
        canvas = art.resize((1280,720),Image.Resampling.LANCZOS)
        for x,y,w,h in ((0,0,1024,512),(1024,0,256,512),(0,512,1024,256),(1024,512,256,256)):
            matches = [r for r in records if r[4].size == (w,h) and r[4].crop((0,0,w,min(h,720-y))).getchannel('A').getextrema() == (255,255)]
            if len(matches) != 1:
                raise ValueError('Title background tile missing or ambiguous')
            replace_texture(result,matches[0],canvas.crop((x,y,x+w,y+h)))
    else:
        matches = [r for r in records if r[4].getchannel('A').getextrema() == (255,255) and
                   (r[4].size == (64,64) or (r[4].size == (128,128) and r[3][1]&63 == 18))]
        if len(matches) != 1:
            raise ValueError('Startup gradient missing or ambiguous')
        replace_texture(result,matches[0],art.resize((128,128),Image.Resampling.LANCZOS))
    return bytes(result)


def build(archive, title, menu):
    result = bytearray(archive)
    targets = {
        'data/fe/source/screens/bootflow/pressstart.rx2': (title,True),
        'data/fe/source/screens/demo/pressstart.rx2': (title,True),
        'data/fe/source/screens/bootflow/welcomescreen.rx2': (menu,False),
        'data/fe/source/screens/bootflow/coachfrank.rx2': (menu,False),
    }
    found = set()
    for name,toc,compression,offset,compressed,size in entries(archive):
        if name not in targets:
            continue
        raw = archive[offset:offset+(compressed or size)]
        data = unpack_refpack(raw,size) if compressed else raw
        art, is_title = targets[name]
        replacement = replace_art(data,art,is_title)
        if len(replacement) != size:
            raise ValueError('Texture edit changed the arena size')
        new_offset = (len(result)+63) & ~63
        result.extend(bytes(new_offset-len(result)))
        result.extend(replacement)
        struct.pack_into('>III',result,toc,new_offset>>6,0,size)
        result[compression] = 0
        found.add(name)
    if found != set(targets):
        raise ValueError('Required named frontend resources are missing')
    result.extend(bytes((-len(result))%64))
    struct.pack_into('>Q',result,24,len(result))
    entries(result)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True,help='Original data/big/fedynamic.big')
    parser.add_argument('--title',type=Path,required=True,help='Landscape 4:3 title background, without UI')
    parser.add_argument('--menu',type=Path,required=True,help='Landscape 4:3 menu background, without UI')
    parser.add_argument('--output',type=Path,required=True,help='New frontend archive; must not already exist')
    args = parser.parse_args()
    from PIL import Image
    images = [Image.open(p).convert('RGB') for p in (args.title,args.menu)]
    if any(im.width*3 != im.height*4 for im in images):
        parser.error('Both background images must be landscape 4:3')
    result = build(args.archive.read_bytes(),*images)
    with args.output.open('xb') as output:
        output.write(result)
    print(f'Created {args.output}; original archive preserved')


if __name__ == '__main__':
    main()
