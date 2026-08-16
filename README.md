# claude-mochi

Repositório para criar um assistente de mesa do Claude Code.

## Modelo para impressão 3D

A carcaça é paramétrica, feita em OpenSCAD, e sai em duas peças imprimíveis sem
suporte. Os STL prontos ficam em [`hardware/stl/`](hardware/stl) e o guia
completo — medidas, parafusos, perfil de fatiamento e montagem — está em
[`hardware/README.md`](hardware/README.md).

```bash
make stl     # regera os STL de todas as placas
make png     # regera as imagens do guia
```

Versões prontas: Raspberry Pi Zero / Zero 2 W (94 × 64 × 71 mm) e
Raspberry Pi Pico (76 × 52 × 59 mm).
