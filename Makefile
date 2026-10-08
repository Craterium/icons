ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif

CRT := $(PYTHON) tools/craterium.py

.PHONY: all check strict svg png sprite manifest preview banner new clean help

all: check svg png sprite manifest preview

help:
	@echo "make            check and build svg, png, sprites, icons.json, preview.html"
	@echo "make check      validate every source grid"
	@echo "make strict     like check, but fail on warnings"
	@echo "make svg        svg/mono and svg/duotone"
	@echo "make png        png/<theme>/<variant>/<12|48|96>"
	@echo "make sprite     svg/sprite-mono.svg and svg/sprite-duotone.svg"
	@echo "make manifest   icons.json"
	@echo "make preview    preview.html contact sheet"
	@echo "make banner     banner/*.png (needs pillow)"
	@echo "make new CAT=ui NAME=thing   start a new icon from the template"
	@echo "make clean      remove generated files"

check:
	@$(CRT) check

strict:
	@$(CRT) check --strict

svg:
	@$(CRT) svg

png:
	@$(CRT) png

sprite:
	@$(CRT) sprite

manifest:
	@$(CRT) manifest

preview:
	@$(CRT) preview

banner:
	@$(PYTHON) tools/banner.py

new:
	@$(CRT) new $(CAT) $(NAME)

clean:
	@$(CRT) clean
