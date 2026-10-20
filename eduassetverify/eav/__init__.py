"""EduAssetVerify experiments: benchmark generation, verifiers, and evaluation.

Layout
    eav.styles, eav.render      appearance: styles and the matplotlib renderer
    eav.domains.*               scene sampling, constraints, error operators, spec-level truth
    eav.build                   seeded benchmark build with splits, validation, leakage guards
    eav.validate                independent label recomputation from pixels
    eav.measure, eav.rules      measurement operators and the three-valued rule engine
    eav.methods.*               EduAssetVerify, baselines, oracle grounding
    eav.vlm.*                   cached VLM clients, prompts, validity battery
    eav.metrics, eav.run        scoring and experiment runs
"""
