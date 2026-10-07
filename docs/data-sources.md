# Data-source register

| Source | Data used | Access | Current status |
|---|---|---|---|
| OpenDota | Pro match index/details, drafts, Fantasy stats, heroes, teams, players, logos, portraits, league catalog, rank snapshots | Free tier; optional API key | Implemented |
| STRATZ GraphQL | Current-patch rank/role match enrichment, synergy, counters, detailed player metrics | Free token required | Client pending token |
| Valve Dota/Steam | Official patch notes, tournament announcements, match fallback | Some endpoints require Steam key | Metadata adapter pending |
| SteamTracking GameTracking-Dota2 | Fantasy schema, 18 scoring stat identifiers, title data structures | Public Git repository | Schema verified; hero category assignments are not exposed publicly |
| Official tournament/team pages | TI format, venue, roster verification, photos/logos where permitted | Public pages | TI venue/date, 2026 Round 1 fixtures, and Swiss pairing rules verified; initial pools inferred from the announced split start times |
| Purge TI 2026 Fantasy guide | Qualitative banner-stat priority, best-two-map implications, series-length risk, player-selection sanity checks | [YouTube, 7 Aug 2026](https://www.youtube.com/watch?v=sbsSf8t4qFU) | Reviewed; used as a low-weight expert/method reference, not as match data |
| Purge TI 2026 predictions | Complete 16-team group-stage placement board and qualitative team-form commentary | [YouTube, 7 Aug 2026](https://www.youtube.com/watch?v=Vdf85DFFsmQ&t=80s) | Board transcribed to `data/reference/ti_2026_expert_predictions.csv`; used only as a low-weight expert prior |

## Known limitations

- OpenDota `heroStats` is a rolling snapshot, so the pipeline stores dated snapshots. Trend graphs become stronger as scheduled snapshots accumulate.
- Historical TI league IDs can include qualifiers. Venue effects must be applied only after phase/date classification.
- Player portrait and team logo URLs are references to source-hosted assets; licensing and cache policy must be reviewed before public deployment.
- STRATZ enrichment cannot run until `STRATZ_API_TOKEN` is supplied.
- Screenshot title categories need authoritative hero-category extraction from current game files.
- Creator predictions are subjective and are never counted as played matches. They may only be used as a separately labeled, low-weight prior or a disagreement flag.
- The TI Road simulator follows the official five-round Swiss/elimination structure and applies the revealed 2026 Round 1 fixtures. The two initial pools are inferred from the announced split start times because Valve has not separately labeled them as Group A/Group B; this assumption is stored in the fixture file and should be rechecked if later pairings contradict it.
- OpenDota replay payloads provide 17 of the 18 current Fantasy stat families directly or through replay events. Watcher captures are not present and remain `NULL` pending STRATZ or custom replay parsing.
- `lotus_item_uses` records the replay-observed Healing Lotus item-use family; it must not be relabeled as exact lotus pickups until checked against the client scorer.
- `fountain_death_proxy` records deaths attributed to `dota_fountain`. The Cruel title requires positional verification and will not use this proxy as an exact activation label.

## Curated reference files

- `data/reference/ti_events.csv` records the ten TI editions used by the historical model. `venue_phase_only=true` prevents qualifier matches under an umbrella league ID from inheriting the arena location.
- `data/reference/ti_2026_participants.csv` maps TI display/rebrand names to source team IDs. Roster identity will remain the final authority.
- `data/reference/fantasy_titles_2026.csv` transcribes the title rules visible in the user-provided 2026 Fantasy client screenshot. Hero-to-prefix category mappings still require game-file verification.
- `data/reference/ti_2026_expert_predictions.csv` records Purge's displayed TI 2026 group-stage board. It is retained for reproducibility and model-vs-expert comparison; it does not overwrite Elo, Glicko, roster, draft, or Fantasy-stat evidence.
- `data/reference/ti_2026_round1.csv` records all eight revealed opening series and the inferred initial Swiss pools used for Rounds 1–3.
- `data/reference/ti_2026_live_results.csv` records completed TI 2026 Swiss series from OpenDota league `19719`; the conditional simulator fixes these outcomes instead of replaying already-finished rounds.
- `artifacts/ti_live_fantasy_points.json` contains map-level, best-two-map, and best-series scoring for the user's exact three banners through the recorded live cutoff. Lucky is applied exactly from map duration; Cerulean remains excluded until authoritative hero-color tags are available.
