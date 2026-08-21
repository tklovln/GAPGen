# Retrospective summary (existing generated_art runs)

Source: `generated_art/*/report.json`

## H3 alignment notes

- Primary Fruit ablation must use **new** `research_B*_fruit` runs.
- `fruit_3dCartoonSimple` report theme field is **Alien** (folder name mismatch) → retrospective/qualitative only.
- Scope subset metrics = elements + powerups + crate name set used in SCOPE.md.

## Per-run table

| run | theme | mode | n | pass | needs_review | mean_iters | mean_style | mean_func | scope_pass_rate | h3_note |
|-----|-------|------|---|------|--------------|------------|------------|-----------|-----------------|---------|
| SteamPunk_3dCartoonSimple | SteamPunk | theme_swap | 63 | 0.873 | 0.127 | 1.59 | 8.99 | 8.82 | 1.0 | optional_demo |
| cat_3dCartoonSimple | cat | theme_swap | 63 | 0.921 | 0.079 | 1.67 | 8.92 | 8.71 | 0.929 | aligns_secondary_Pet |
| fruit_3dCartoonSimple | Alien | theme_swap | 63 | 1.0 | 0.0 | 1.43 | 9.46 | 9.43 | 1.0 | mismatch_theme_field_Alien_folder_fruit — retrospective only |
| ocean_3dCartoonSimple | ocean | theme_swap | 63 | 0.937 | 0.063 | 1.54 | 8.71 | 8.54 | 1.0 | optional_demo |
