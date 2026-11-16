# Data licences

`careers-seed.json` — career statistics of current Formula 1 drivers and teams (seasons, wins, podiums, points, final position).
Source: [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) (Ergast-compatible), licensed under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). This file is shared under the same licence:
attribution to Jolpica, non-commercial use only, share-alike. Retrieved 14 November 2026 with the API's published rate limits.

Other files (`manual-careers`, `person-info`, `directory-extra`, `calendars-extra`) come from open sources listed in the Motorsport Hub app; calendars are weekend dates taken from the series' announcements.

`results.json` — winner of each round and season standings of 21 championships (F1, F2, F3, Formula E, IndyCar, Indy NXT, Super Formula, WEC, IMSA, ELMS, Asian Le Mans, GT World Challenge Europe, DTM, British GT, WRC, ERC, NASCAR Cup / O'Reilly / Trucks, Supercars, BTCC).
Source: the English-language Wikipedia season articles (link given for each championship inside the file), text licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Only facts are extracted (winners, pole, fastest lap, points tables), never prose.
Rebuilt every day by `tools/open_results.py` (workflow `.github/workflows/open-results.yml`, one request per article). Attribution: Wikipedia contributors; share-alike applies to this file.
