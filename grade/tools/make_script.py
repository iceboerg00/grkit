# Erzeugt aus einem GRade-Rezept (JSON wie in der App) ein SD-Startskript
# (script/startup.ttl), das Look, Regler und Weissabgleich per
# "UserData Set" in einen Custom-Slot der GR IV schreibt.
#
# usage: make_script.py <rezepte.json> <name|index> --slot 1 [--out DIR] [--no-wb]
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # grade/

# Wire-Basiscode -> Look-Name in UserData
LOOKS = {0: 'Standard', 1: 'Vivid', 2: 'MonotoneGR', 3: 'SoftMonotone',
         4: 'HardMonotone', 5: 'HighContrastBW', 6: 'PositiveFilm',
         7: 'BleechBypass_GR', 8: 'Retro', 9: 'HdrCuisine', 13: 'NegativeFilm',
         14: 'CinemaYellow', 15: 'CinemaGreen', 16: 'CrossProcess'}

# App-Parameter-ID -> Reglername (ohne Look-Praefix)
SIGNED = {0: 'Saturation', 1: 'ColorHue', 2: 'ImageKey', 3: 'Contrast',
          4: 'ContrastHighLight', 5: 'ContrastShadow', 6: 'Sharpness',
          19: 'Shading', 20: 'ClarityControl', 10: 'ColorToneRetro'}
INDEXED = {7: 'ColorToneMonotone', 9: 'ColorToneBleechBypass', 8: 'ColorToneCinema',
           11: 'ColorToneHdrIntense', 24: 'HdrIntense', 25: 'ColorToneCrossProcess',
           21: 'Particle', 22: 'ParticleSize', 23: 'ParticleStrength',
           12: 'FilterEffectCustom'}
FILTER = {'R': (13, 14), 'G': (15, 16), 'B': (17, 18)}  # (high, low)

# App-WBMode -> UserData-Modus
WB = {'auto': 'AutoStandard', 'autoWarm': 'AutoWarm', 'autoWhite': 'AutoWhite',
      'daylight': 'Daylight', 'shade': 'Shade', 'cloud': 'Cloudiness',
      'daylightFluorescent': 'Flu_D', 'dayWhiteFluorescent': 'Flu_N',
      'coolWhiteFluorescent': 'Flu_W', 'warmWhiteFluorescent': 'Flu_L',
      'tungsten': 'Tungsten', 'cte': 'Cte', 'manual1': 'Manual1',
      'colorTemp1': 'ColorTemp1'}


# manual-Feld -> UserData-Einstellung, mit den Werten aus der Firmware
EXTRAS = {'highlight': 'StillHighlightCorrect', 'shadow': 'StillShadowCorrect',
          'peripheral': 'StillLensShadingCorrection', 'noise': 'StillHighIsoNR'}
EXTRA_VALUES = {'StillHighlightCorrect': ['Auto', 'On', 'Off'],
                'StillShadowCorrect': ['Auto', 'Low', 'Mid', 'High', 'Off'],
                'StillLensShadingCorrection': ['On', 'Off'],
                'StillHighIsoNR': ['Auto', 'Low', 'Mid', 'High', 'Custom', 'Off']}


def registry():
    """Name (ohne StillImageControlNo1Param) -> erlaubte Textwerte, aus der Firmware."""
    reg = {}
    for line in (ROOT / 'data' / 'werte-custom1.txt').read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith('0x'):
            reg[parts[0]] = parts[2:]
    return reg


def signed_text(v):
    return 'OFF' if v == 0 else (f'P{v}' if v > 0 else f'M{-v}')


def commands(recipe, slot, with_wb):
    reg = registry()
    base = recipe['base_effect_id']
    if base not in LOOKS:
        raise SystemExit(f'Basis {base} unbekannt')
    look = LOOKS[base]
    pre = f'StillImageControlNo{slot}'
    # Look des Slots setzen, dann die Kamera auf diesen Custom-Slot schalten
    # (StillActiveImageControlSet No0..No3, No1 = Custom 1), damit Live-View
    # und Fotos ihn sofort verwenden.
    out = [f'{pre} {look}', f'StillActiveImageControlSet No{slot}']
    params = {int(k): int(v) for k, v in recipe['params'].items()}

    def add(reg_name, value, per_look=True):
        full = (look if per_look else '') + reg_name
        allowed = reg.get(full)
        if allowed is None:
            raise SystemExit(f'{full} gibt es in der Firmware nicht')
        if allowed and value not in allowed:
            raise SystemExit(f'{full}: Wert {value} nicht in {allowed}')
        out.append(f'{pre}Param{full} {value}')

    for pid in sorted(params):
        v = params[pid]
        if pid in SIGNED:
            add(SIGNED[pid], signed_text(v))
        elif pid in INDEXED:
            allowed = reg.get(look + INDEXED[pid]) or []
            if not 0 <= v < len(allowed):
                raise SystemExit(f'{look}{INDEXED[pid]}: Index {v} ausserhalb {allowed}')
            add(INDEXED[pid], allowed[v])
    if params.get(12):
        for ch, (hi, lo) in FILTER.items():
            raw = ((params.get(hi, 0) & 0xFF) << 8) | (params.get(lo, 0) & 0xFF)
            # die RGB-Filter gelten fuer den ganzen Slot, ohne Look im Namen
            add(f'FilterEffect{ch}Custom1', str(raw - 0x10000 if raw >= 0x8000 else raw),
                per_look=False)

    if with_wb:
        live, manual = recipe.get('live', {}), recipe.get('manual', {})
        mode = WB.get(live.get('WBMode', ''))
        if mode:
            out.append(f'StillWhiteBalance {mode}')
            ab, gm = int(manual.get('wbAB') or 0), int(manual.get('wbGM') or 0)
            if not (-14 <= ab <= 14 and -14 <= gm <= 14):
                raise SystemExit(f'WB-Shift {ab}/{gm} ausserhalb ±14')
            # App-Konvention: wbAB positiv = B, wbGM positiv = G
            out.append(f'StillWhiteBalance{mode}AdjustBA '
                       + ('NORMAL' if ab == 0 else (f'B{ab}' if ab > 0 else f'A{-ab}')))
            out.append(f'StillWhiteBalance{mode}AdjustGM '
                       + ('NORMAL' if gm == 0 else (f'G{gm}' if gm > 0 else f'M{-gm}')))
            k = re.search(r'(\d{4,5})\s*K', manual.get('notes', ''))
            if mode == 'ColorTemp1' and k:
                out.append(f'StillWhiteBalanceColorTemp {k.group(1)}')
        # Korrekturen und Rauschunterdrueckung (Kamera-Menue, nicht im Slot)
        for key, setting in EXTRAS.items():
            value = manual.get(key)
            if value is None:
                continue
            value = {'Medium': 'Mid'}.get(value, value)
            if value not in EXTRA_VALUES[setting]:
                raise SystemExit(f'{setting}: Wert {value} nicht in {EXTRA_VALUES[setting]}')
            out.append(f'{setting} {value}')
    return out


def ttl(name, cmds, marker):
    safe = re.sub(r"[^A-Za-z0-9 +\-.]", '', name)
    lines = [f'; GRade Rezept: {safe}', f'; Laeuft nur einmal (Marker C:\\{marker}).',
             '', 'mpause 15000', f"filesearch 'C:\\{marker}'", 'if result = 1 then',
             '    end', 'endif', f"filecreate f 'C:\\{marker}'", 'if f < 0 then', '    end',
             'endif', f"filewriteln f 'GRade Rezept: {safe}'", 'n = 0', '']
    for c in cmds:
        lines += [f"sendln 'UserData Set {c}'", 'if result != 0 then', '    n = n + 1',
                  f"    filewriteln f 'FEHLER: {c}'", 'endif']
    lines += ['', "filewriteln f 'Befehle:'", f"int2str s {len(cmds)}", 'filewriteln f s',
              "filewriteln f 'Fehler:'", 'int2str s n', 'filewriteln f s', 'fileclose f', 'end', '']
    return '\r\n'.join(lines)


def write_pack(data, slot, out, with_wb):
    """Fuer das GRKit-Recipes-Plugin: SCRIPT/PLUGINS/RECIPES/NAMES.TXT (ein Name
    pro Zeile) und Rnnn.TXT (ein "Name Wert"-Paar pro Zeile) je Rezept."""
    folder = Path(out) / 'SCRIPT' / 'PLUGINS' / 'RECIPES'
    folder.mkdir(parents=True, exist_ok=True)
    names = []
    for i, r in enumerate(data[:100], start=1):
        cmds = commands(r, slot, with_wb)
        name = re.sub(r'[^ -~]', '?', r['name'])[:31]
        names.append(name)
        # Jede Zeile ist ein ganzer Shell-Befehl; der Slot bekommt den
        # Rezeptnamen (max. 32 Zeichen, Anfuehrungszeichen fuer Leerzeichen).
        slot_name = re.sub(r'[^ -~]|["\']', '', r['name'])[:32].strip()
        lines = [f'UserData Set {c}' for c in cmds]
        lines.append(f'camctl_set_user_still_imgctl_custom_name {slot} "{slot_name}"')
        (folder / f'R{i:03d}.TXT').write_bytes(
            ''.join(c + '\r\n' for c in lines).encode('ascii') + b'\r\n')
    (folder / 'NAMES.TXT').write_bytes(''.join(n + '\r\n' for n in names).encode('ascii'))
    print(f'{len(names)} Rezepte nach {folder}')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--pack':
        ap = argparse.ArgumentParser()
        ap.add_argument('--pack', action='store_true'); ap.add_argument('json')
        ap.add_argument('--slot', type=int, choices=(1, 2, 3), default=1)
        ap.add_argument('--out', required=True)
        ap.add_argument('--no-wb', action='store_true')
        a = ap.parse_args()
        data = json.loads(Path(a.json).read_text(encoding='utf-8'))
        write_pack(data if isinstance(data, list) else [data], a.slot, a.out, not a.no_wb)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument('json'); ap.add_argument('recipe')
    ap.add_argument('--slot', type=int, choices=(1, 2, 3), required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--no-wb', action='store_true')
    ap.add_argument('--marker', default='GRADE5.TXT')
    a = ap.parse_args()
    data = json.loads(Path(a.json).read_text(encoding='utf-8'))
    data = data if isinstance(data, list) else [data]
    if a.recipe.isdigit():
        r = data[int(a.recipe)]
    else:
        hits = [x for x in data if x['name'].lower() == a.recipe.lower()]
        if not hits:
            raise SystemExit('Rezept nicht gefunden')
        r = hits[0]
    cmds = commands(r, a.slot, not a.no_wb)
    script = ttl(r['name'], cmds, a.marker)
    if a.out:
        p = Path(a.out) / 'script' / 'startup.ttl'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(script, encoding='ascii')
    print(f"{r['name']} -> Custom {a.slot}, {len(cmds)} Befehle")
    for c in cmds:
        print('  ', c)


if __name__ == '__main__':
    main()
