#!/usr/bin/env python3
"""Extrai as malhas de um projeto .3mf do Bambu Studio para STL binario.

case/clawd_tela.scad importa models/upstream/3mf-corpo.stl e 3mf-chapa.stl, que
o .gitignore nao versiona (sao geometria de terceiro, CC BY-NC-SA 4.0). Este
script as regenera a partir do seu clawd_mochi.3mf:

    python3 models/extrai_3mf.py clawd_mochi.3mf

As malhas saem como estao no arquivo — centradas na origem e SEM as escalas da
matriz do item, que ficam por conta do .scad (veja 'escala_z').
"""
import struct, sys, zipfile, pathlib
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
DESTINO = pathlib.Path("models/upstream")

# id do objeto no 3mf -> nome do arquivo. O corpo e o de 420 faces, a chapa 632.
POR_FACES = {420: "3mf-corpo.stl", 632: "3mf-chapa.stl"}


def escreve_stl(caminho, vertices, triangulos):
    with open(caminho, "wb") as f:
        f.write(b"extraido de um projeto .3mf".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(triangulos)))
        for a, b, c in triangulos:
            f.write(struct.pack("<3f", 0, 0, 0))       # normal nula: o STL permite
            for i in (a, b, c):
                f.write(struct.pack("<3f", *vertices[i]))
            f.write(b"\0\0")


def main(arquivo):
    DESTINO.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arquivo) as z:
        raiz = ET.fromstring(z.read("3D/3dmodel.model"))

    achados = 0
    for obj in raiz.iter():
        if obj.tag.split("}")[-1] != "object":
            continue
        malha = obj.find("m:mesh", NS)
        if malha is None:
            continue
        vs = [(float(v.get("x")), float(v.get("y")), float(v.get("z")))
              for v in malha.find("m:vertices", NS)]
        ts = [(int(t.get("v1")), int(t.get("v2")), int(t.get("v3")))
              for t in malha.find("m:triangles", NS)]
        nome = POR_FACES.get(len(ts))
        if nome is None:
            print(f"  objeto {obj.get('id')}: {len(ts)} faces — nao reconhecido, pulando")
            continue
        escreve_stl(DESTINO / nome, vs, ts)
        bb = [(min(v[k] for v in vs), max(v[k] for v in vs)) for k in range(3)]
        print(f"  {DESTINO / nome}: {len(ts)} triangulos, "
              f"{bb[0][1]-bb[0][0]:.2f} x {bb[1][1]-bb[1][0]:.2f} x {bb[2][1]-bb[2][0]:.2f} mm")
        achados += 1

    if achados != 2:
        sys.exit(f"esperava 2 malhas conhecidas, achei {achados}. "
                 f"O 3mf e mesmo o clawd_mochi original?")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "clawd_mochi.3mf")
