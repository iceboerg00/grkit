# GRade recipes for GRKit

This folder holds the recipe pack for the Recipes plugin (`runtime/plugins/recipes`) on the RICOH GR IV, firmware 1.11.

| Path | Contents |
| --- | --- |
| `recipes/ricohcookbook-80.json` | 80 recipes in the GRade app format |
| `sd/SCRIPT/PLUGINS/RECIPES/` | The generated files for the card: `NAMES.TXT`, then `R001.TXT` to `R080.TXT` |
| `tools/make_script.py` | The generator |
| `data/werte-custom1.txt` | The setting names and values of the Custom 1 slot, read from firmware 1.11 |

## Install

1. Build and copy GRKit as usual (see the main README).
2. Copy `sd/SCRIPT` to the root of the card, next to the GRKit files.
3. Start the camera. ADJ → GRK → RCP lists the recipes. Highlight a row to preview it, press OK to keep it.

## Make your own pack

```sh
python grade/tools/make_script.py --pack my-recipes.json --slot 1 --out my-pack
```

Each recipe file holds one engineering shell command per line, ends with an empty line, and sets the look, the parameters, the slot name, the white balance mode, color temperature and shift, and the highlight, shadow, peripheral and noise reduction settings.

## Credits

The 80 recipes come from [ricohcookbook.com](https://ricohcookbook.com). Each recipe keeps the link to its page in `manual.notes`. The recipes belong to their authors.

RICOH and GR are trademarks of Ricoh Company, Ltd. This project is not affiliated with Ricoh.
