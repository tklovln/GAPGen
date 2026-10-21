# Frozen configuration (set on the dev split only, before any test run)

Frozen: 2026-10-20, git commit recorded in the commit that adds this file.

- Backbones: `gemini-3.5-flash` (thinking budget 1024, temperature 0.7, boxes in 0-1000 units)
  and `global.anthropic.claude-sonnet-5` (AWS Bedrock; provider-default sampling because the
  model rejects `temperature`; boxes in image pixels). Both pass the five-check battery in
  both roles (`results/battery/`).
- EduAssetVerify: m = 3 grounding readings; tau = 0.6; equal_area zones (0.10, 0.20);
  symmetry IoU zones (0.92, 0.82); relation margin 0.25 of mean object size.
  tau sweep on dev: tau in [0.34, 0.6] gives identical results on both backbones; tau >= 0.67
  only adds abstentions (FAR is 0 at every tau).
- Evaluation: 3 independent passes per configuration; numbers are mean +- sd over passes.
- CLIPScore threshold 0.7969, chosen on dev.

Dev-split findings that changed the pipeline before test (kept for the paper's account):
1. Claude answered boxes in image pixels in 84% of readings although asked for 0-1000
   units, which moved every crop for the semantic re-reading to the wrong place
   (EduAssetVerify dev accuracy 63%). Fix: ask each model in its native frame, and check
   the frame as part of protocol compliance in the battery. Discarded runs are kept in
   `results/discarded_frame_bug/`.
2. Witness boxes for relation reversal and broken symmetry were unions or difference
   blobs; they now name the misplaced object.
