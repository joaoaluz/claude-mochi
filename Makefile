# claude-mochi — geracao dos arquivos de impressao
#
#   make stl     exporta os STL de todas as placas em hardware/stl/
#   make png     regenera as imagens do guia (precisa de xvfb em servidor)
#   make clean   apaga o que foi gerado
#
# Requer OpenSCAD >= 2021.01:
#   sudo apt install openscad        (Debian/Ubuntu)
#   brew install --cask openscad     (macOS)

OPENSCAD ?= openscad
XVFB     := $(shell command -v xvfb-run 2>/dev/null)
RENDER   := $(if $(XVFB),xvfb-run -a $(OPENSCAD),$(OPENSCAD))

SRC    := hardware/mochi.scad hardware/boards.scad
MAIN   := hardware/mochi.scad
STLDIR := hardware/stl
IMGDIR := hardware/img
BOARDS := pi_zero pico

STLS := $(foreach b,$(BOARDS),$(STLDIR)/$(b)-casca.stl $(STLDIR)/$(b)-base.stl)
PNGS := $(IMGDIR)/frente.png $(IMGDIR)/montado.png $(IMGDIR)/corte.png $(IMGDIR)/base.png

.PHONY: all stl png clean
all: stl

stl: $(STLS)
png: $(PNGS)

$(STLDIR) $(IMGDIR):
	mkdir -p $@

$(STLDIR)/%-casca.stl: $(SRC) | $(STLDIR)
	$(OPENSCAD) -o $@ --export-format=binstl -D 'part="casca"' -D 'board_name="$*"' $(MAIN)

$(STLDIR)/%-base.stl: $(SRC) | $(STLDIR)
	$(OPENSCAD) -o $@ --export-format=binstl -D 'part="base"' -D 'board_name="$*"' $(MAIN)

$(IMGDIR)/frente.png: $(SRC) | $(IMGDIR)
	$(RENDER) -o $@ --imgsize=700,600 --camera=0,0,34,90,0,0,255 \
	  --projection=p --colorscheme=Tomorrow -D 'part="casca"' $(MAIN)

$(IMGDIR)/montado.png: $(SRC) | $(IMGDIR)
	$(RENDER) -o $@ --imgsize=800,620 --camera=0,0,32,68,0,25,320 \
	  --projection=p --colorscheme=Tomorrow -D 'part="montado"' $(MAIN)

$(IMGDIR)/corte.png: $(SRC) | $(IMGDIR)
	$(RENDER) -o $@ --imgsize=820,620 --camera=0,0,32,74,0,205,300 \
	  --projection=p --colorscheme=Tomorrow -D 'part="corte"' $(MAIN)

$(IMGDIR)/base.png: $(SRC) | $(IMGDIR)
	$(RENDER) -o $@ --imgsize=800,600 --camera=0,0,2,55,0,25,240 \
	  --projection=p --colorscheme=Tomorrow -D 'part="base"' $(MAIN)

clean:
	rm -rf $(STLDIR) $(IMGDIR)
