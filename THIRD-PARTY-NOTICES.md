# Third-party notices

WNTB is licensed under the GNU General Public License v3.0 (see `LICENSE`). This file holds the
notices that third-party licences ask for, covering data and constants WNTB carries.
`docs/ATTRIBUTIONS.md` is the wider list of acknowledgements.

## Screenshots: crop rectangles and filename masks (GPL-3.0)

The HUD-panel crop rectangles, the Thargoid-scan crop and the filename mask scheme (`SYSTEM`, `BODY`,
`CMDR`, `DATE`, `NNNNN` tokens and sequence numbering) in `plugin/screenshot_gui_focus.py` and
`plugin/screenshot_naming.py` follow
[NoFoolLikeOne/EDMC-Screenshot](https://github.com/NoFoolLikeOne/EDMC-Screenshot), licensed GPL-3.0,
the same licence as WNTB. That project carries the standard GPL-3.0 text and no separate copyright
line, so this repository's `LICENSE` applies. Credit for the original plugin belongs to NoFoolLikeOne.

## Mining: deposit depletion figures (GPL-3.0)

The depletion figures in `plugin/mining_deposit.py` (125-175 t per rig position, the Density factors
and the Amount bands) are measurements published by
[Fumlop/EDRhinoSpotter](https://github.com/Fumlop/EDRhinoSpotter), licensed GPL-3.0, the same licence
as WNTB.

## Exobiology species and region data (GPL-2.0 or later, MIT)

`plugin/organic_species_data.py` (species and genus conditions) and `plugin/organic_region_data.py`
(galactic region grid, Guardian zones) are generated from the published data of
[Silarn/EDMC-BioScan](https://github.com/Silarn/EDMC-BioScan) and
[Silarn/EDMC-ExploData](https://github.com/Silarn/EDMC-ExploData), both licensed GPL version 2 or
later, which allows use under the GPL-3.0 that WNTB carries. The region grid
originates in
[klightspeed/EliteDangerousRegionMap](https://github.com/klightspeed/EliteDangerousRegionMap), whose
licence follows:

```
MIT License

Copyright (c) 2020 Ben Peddell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Exploration Value: scan-value constants (GPL-3.0)

The per-planet-class base values and the mass exponent in `plugin/exploration_value.py` are the
community's figures for Frontier's exploration payout, as published in
[Faber38/CMDRHelper](https://github.com/Faber38/CMDRHelper), licensed GPL-3.0, the same licence as WNTB.

## Landing Assist: pad layouts (GPL-2.0 or later)

The pad layouts drawn by `plugin/landing.py` follow
[bgol/LandingPad](https://github.com/bgol/LandingPad), licensed GPL version 2 or later, which allows
use under the GPL-3.0 that WNTB carries: the starport pad table, shell sizes and pad sectors (which the
game's station design dictates), the fleet carrier and squadron carrier pad rectangles, and the list of
colonisation ship market ids. The code that draws them is WNTB's own.

## Micro-resource names

`plugin/inventory_names_fdevids.py` is generated from the `microresources.csv` published by
[EDCD/FDevIDs](https://github.com/EDCD/FDevIDs), which declares no licence. The names are Frontier's
own.
