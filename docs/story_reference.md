# Internal story reference — full spoilers

**Keep this file out of model prompts.** It is a research index, not translation source. The Japanese source of record is the extracted PC-98 scene text in ignored `work/messages.jsonl`. Walkthroughs identify possible routes and later context; they do not supply wording for translation. Add only a note proven safe at a passage's exact point in a verified branch. Do not expose later revelations, route outcomes, or sibling-choice text to earlier prompts.

## Source key and confidence

- **P98**: supplied `MAX2_SCN.PAK`, extracted with `tools/scenes.py`. Cite a stable message ID. High confidence for the words present in this supplied revision; scene order and route reachability need event/gameplay checks.
- **W96**: [walkthrough explicitly labeled 1996 version](https://lastcharles.com/pc-18/walkthrough/pc-18/kizuato). Medium confidence for broad route order and choice mapping; this is a guide, not the supplied binary.
- **R02-C** and **R02-A**: [Renewal Chizuru chart](https://shisnap.iza-yoi.net/game/pc/kizuato_r/kizuatoR_chizuru.htm) and [Renewal Azusa chart](https://shisnap.iza-yoi.net/game/pc/kizuato_r/kizuatoR_azusa.htm). Low confidence for PC-98 mechanics. The pages identify the game as Renewal; the user identifies them as 2002-era references. Do not copy their choice order or wording into the PC-98 patch without verification.

The PC-98 character table alignment is verified against the opening, not the entire script. A source ID is stronger evidence than an unlocated summary, but a difficult reading still needs visual or font verification.

## Characters and relationships

| Note | Evidence | Confidence | Earliest safe use |
| --- | --- | --- | --- |
| The first-person narrator is addressed as **耕一** (working English: **Koichi**). | P98 `001.SCN/text/004`; `001.SCN/text/012` | High for name; romanization provisional | After the first address in `001.SCN/text/004` |
| **柏木千鶴** (**Kashiwagi Chizuru**) is Koichi's older cousin, 23, three years older than him, and the Kashiwagi household head. | P98 `001.SCN/text/005` | High | After `001.SCN/text/005` |
| **梓** (**Azusa**) is Chizuru's younger sister, the household's second daughter, 18, and a high-school student. The narrator contrasts her rough speech with Chizuru's manner. | P98 `006.SCN/text/007` | High | After `006.SCN/text/007` on a reached branch |
| **楓** (**Kaede**) is the third sister, 16, in her second year of high school. The narrator initially reads her reserve as possible dislike; that is his impression, not a verified motive. | P98 `016.SCN/text/004`; `016.SCN/text/006` | High for introduction and age; low for motive | After `016.SCN/text/006` |
| **初音** (**Hatsune**) is the youngest/fourth sister, 15, in her first year of high school. She addresses Koichi as an older brother. | P98 `010.SCN/text/000`; `010.SCN/text/002` | High | After `010.SCN/text/002` |
| **柳川** (**Yanagawa**) appears with officer Nagase and identifies himself as a police officer. A later route bears his name. | P98 `035.SCN/text/000`; W96 Yanagawa section | High for introduction, medium for route label | After `035.SCN/text/000`; route label only after verified route entry |
| **鶴来屋** (**Tsurugiya**, spelling provisional) is a lodging-centered business group chaired by Chizuru; the narrator attributes its founding to his grandfather. | P98 `034.SCN/text/013` | High for relationship; English spelling unreviewed | After `034.SCN/text/013` |

The ages above are PC-98 script facts relevant to review. Do not infer that every route or later scene has the same narrator perspective or speaker without checking its message and event context.

## Route order and gated choices

W96 organizes a completion path as **Chizuru → Azusa → Kaede → Yanagawa → Hatsune → extras**, with each later section described as starting after the preceding ending. **Confidence: medium, guide-only for full unlock logic.** P98 `000.SCN` contains a flag-gated nightmare/wake choice and a fresh-game conditional load into `001.SCN`. P98 `001.SCN` contains the first reachable three-option answer to Chizuru (tell the dream, joke about her appearing, or laugh it off); its three event branches lead to scenes `002`, `003`, and `004`. Those opening structures are verified in the supplied bytes; the full route sequence still needs gameplay/event-graph confirmation.

R02-C and R02-A give a **different, Renewal-only unlock account**: Azusa availability is tied to specific Chizuru bad endings, and additional options appear after other clears. **Confidence for this PC-98 revision: low.** Do not use those flags, option numbers, or wording as PC-98 facts. They are clues to investigate, not implementation requirements.

## Recurring terms and changing clues

| Term or clue | Early reading to preserve | Later information — spoilers | Evidence and confidence |
| --- | --- | --- | --- |
| Repeated dream / “other self” | The narrator fears an increasingly forceful presence, then reassures himself it is only a dream. Keep both uncertainty and self-doubt. | He later suspects the killer may be within him; another later passage says a dream matches a real crime scene. These are narrated beliefs and observations, not an omniscient solution. | P98 `001.SCN/text/009`–`011`, `059.SCN/text/019`–`021`, `096.SCN/text/009`; high for the statements, route order unverified |
| “たかゆき” | A name heard in a remembered phone message, with convenience-store work as a clue. Do not assign an identity early. | In a later investigation, Koichi and Azusa use the name and job clue while searching after a murder/abduction report. | P98 `091.SCN/text/042`, `095.SCN/text/003`, `096.SCN/text/009`, `097.SCN/text/006`; high for the text, chronology requires event check |
| Chizuru's possible secret | Early scenes present her as kind and composed; do not color those lines with a later accusation. | W96 includes a late Chizuru-route choice about whether she is concealing something. The guide's phrasing is a player-choice hypothesis, not proof. | P98 `001.SCN/text/004`–`006`; W96 Chizuru section; medium for guide clue |
| Yanagawa and the investigation | He is introduced as a police officer accompanying Nagase. | W96 later labels a distinct Yanagawa route after Kaede's ending. Do not imply route-specific motives during his introduction. | P98 `035.SCN/text/000`; W96 Yanagawa section; high/medium respectively |

## Prompt release rule

For a current message, use its extracted Japanese text; earlier messages on the **same confirmed path**; only glossary entries present in that text/context; and voice notes already supported by that point. `tools/compare_local.py` checks the original archive hash and `001.SCN` event bytes, then admits only messages 0–15 as prior context for its small sample. These messages form the opening common prefix before the first branch. It does **not** infer cross-scene route ancestry, so no cross-scene history or later notes are released automatically. The sample's explicit voice notes live in `examples/model_sample.json`. A future route graph must prove any broader context selection before this reference is wired into prompts.

## Verification queue

1. Trace PC-98 event flags and play the first reachable choice's three branches; map the early scenes to W96's Chizuru/Azusa guidance.
2. Check each claimed ending unlock against PC-98 save flags and gameplay. Keep R02 unlock rules separate.
3. Verify the full character table and readings of the terms above against native rendering where ambiguous.
4. Tag later clue messages with a verified route/stage before using them as translation context.
