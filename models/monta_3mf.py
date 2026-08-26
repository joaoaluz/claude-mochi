#!/usr/bin/env python3
"""Monta clawd_mochi_tela.3mf: o mesmo projeto, com as malhas trocadas.

Preserva TODOS os ajustes de fatiamento (project_settings.config), a disposicao
no prato e os perfis. Só troca a geometria dos dois objetos e desfaz a escala em
Z da matriz — a escala agora esta assada na malha pelo .scad.

    make clawd-3mf          # exporta as pecas e remonta o projeto

As miniaturas guardadas continuam mostrando o modelo antigo; o fatiador as
regenera quando voce fatiar.
"""
import re, struct, zipfile, os

ORIG = "clawd_mochi.3mf"
NOVO = "clawd_mochi_tela.3mf"
MALHAS = {"1": "case/stl/clawd-corpo.stl", "3": "case/stl/clawd-chapa.stl"}

def ler_stl(p):
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    tris = []
    for i in range(n):
        o = 84 + i*50
        tris.append([struct.unpack("<3f", d[o+12+j*12:o+24+j*12]) for j in range(3)])
    return tris

def malha_xml(tris):
    """solda vertices e devolve o bloco <mesh> do 3MF"""
    idx, verts = {}, []
    faces = []
    for t in tris:
        f = []
        for v in t:
            k = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
            if k not in idx:
                idx[k] = len(verts); verts.append(k)
            f.append(idx[k])
        if len(set(f)) == 3:
            faces.append(f)
    vs = "\n".join(f'     <vertex x="{x:.7g}" y="{y:.7g}" z="{z:.7g}"/>' for x, y, z in verts)
    fs = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    return f"<mesh>\n    <vertices>\n{vs}\n    </vertices>\n    <triangles>\n{fs}\n    </triangles>\n   </mesh>", len(verts), len(faces)

z = zipfile.ZipFile(ORIG)
itens = {i.filename: z.read(i.filename) for i in z.infolist()}
z.close()

model = itens["3D/3dmodel.model"].decode("utf-8")
contagens = {}
for oid, stl in MALHAS.items():
    bloco, nv, nf = malha_xml(ler_stl(stl))
    contagens[oid] = nf
    padrao = re.compile(rf'(<object id="{oid}" type="model">\s*)<mesh>.*?</mesh>', re.S)
    novo, n = padrao.subn(lambda m: m.group(1) + bloco, model)
    assert n == 1, f"objeto {oid}: {n} substituicoes"
    model = novo
    print(f"  objeto {oid} <- {stl}: {nv} vertices, {nf} triangulos")

# a escala em Z agora esta na malha: a matriz do item volta para 1
antes = model
model = model.replace("0 0 0.736842105 ", "0 0 1 ")
assert model != antes, "nao achei a escala Z na matriz do item"
print("  matriz do corpo: escala Z 0.736842105 -> 1 (ja assada na malha)")
itens["3D/3dmodel.model"] = model.encode("utf-8")

# model_settings.config: contagem de faces
ms = itens["Metadata/model_settings.config"].decode("utf-8")
ms = ms.replace('<metadata face_count="420"/>', f'<metadata face_count="{contagens["1"]}"/>')
ms = ms.replace('<metadata face_count="632"/>', f'<metadata face_count="{contagens["3"]}"/>')
ms = re.sub(r'mesh_stat face_count="420"', f'mesh_stat face_count="{contagens["1"]}"', ms)
ms = re.sub(r'mesh_stat face_count="632"', f'mesh_stat face_count="{contagens["3"]}"', ms)
ms = ms.replace("0 0 0.73684210500000002 ", "0 0 1 ")
itens["Metadata/model_settings.config"] = ms.encode("utf-8")

# os thumbnails velhos mostram o modelo sem janela; o fatiador regera ao fatiar
with zipfile.ZipFile(NOVO, "w", zipfile.ZIP_DEFLATED) as out:
    for nome, dados in itens.items():
        out.writestr(nome, dados)
print(f"\n{NOVO}: {os.path.getsize(NOVO):,} bytes")
