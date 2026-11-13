# PC-98 route ending markers (spoilers)

The [1996 walkthrough](https://lastcharles.com/pc-18/walkthrough/pc-18/kizuato) gives route and ending labels. Its choice order is a guide, not proof of gameplay reachability in the supplied HDI. The original PC-98 event graph in ignored `work/event_graph-route-v1.json` confirms that each scene below ends with `96 94 95`, then loads common scene `169.SCN` block 1. The listed final message IDs occur in those terminal scenes. `tools/verify_route_endpoints.py` checks these facts against the hash-pinned original graph and verifies each English OCR marker occurs only once in the v6 edit set. The Japanese script is the source of story content; guide prose is not translation source text.

| Guide ending | Candidate terminal scene | Last displayed text ID | Mapping confidence |
| --- | --- | --- | --- |
| Chizuru bad 1 / 2 / 3 / good | `089` / `087` / `084` / `086` | `037` / `018` / `043` / `041` | Medium: guide choices align with PC-98 branch graph; not played through |
| Azusa bad 1 / 2 / 3 / good | `108` / `107` / `106` / `105` | `049` / `013` / `012` / `045` | Medium: guide choices align with PC-98 branch graph; flag conditions and playthrough unverified |
| Kaede bad / good | `130` / `129` | `019` / `039` | Medium: final choice paths align with guide; not played through |
| Yanagawa end | `135` | `028` | Medium: matching terminal scene and route placement; exact unlock not played |
| Hatsune bad / good | `159` / `158` | `012` / `054` | Medium: final choice paths align with guide; not played through |

The full IDs and short English markers are in `config/route_endpoints_v6.json`. For Azusa's good ending, the distinctive phrase lands on the penultimate text page, while the last page contains only “AFTER.” The recorder advances exactly once after seeing the phrase and checks that last page before stopping. An OCR failure stops for review; it does not silently declare an ending.

Terminal scenes `161`, `162`, `164`, and `168` also load `169`, but correspond to extras rather than the five main character routes. They are **not** configured for automated ending detection. Renewal charts for [Chizuru](https://shisnap.iza-yoi.net/game/pc/kizuato_r/kizuatoR_chizuru.htm) and [Azusa](https://shisnap.iza-yoi.net/game/pc/kizuato_r/kizuatoR_azusa.htm) describe different unlock conditions, so they are secondary and do not determine the PC-98 mappings above.

Use `advance_to_ending` only **after the last verified route choice**, because it presses Return repeatedly up to its configured limit. It does not resolve choices. In a route JSON file, make it the last step and give an `ending_id` from the manifest plus `max_presses` and `interval`. The file `config/route_recorder_end.example.json` is a short tail-only example. Full route action files still require observed keypresses and emulator verification. OCR marker recognition at native PC-98 resolution has **not** yet been tested, nor have the guide-to-scene mappings been confirmed by a complete gameplay run.
