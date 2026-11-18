"""Machine-learning extensions (code plan v1.2, 06-Nghien-cuu/codeplan-rq5-rq6-ml.md).

RQ5  risk_model: learn KPI risk from the outputs of the DQ checks.
RQ6  detectors:  ML detectors for silent errors (planned).

Nothing in this package is imported by the pipeline, the experiment runner or the v1.0 /
v1.1 analyses, so their results are unchanged.
"""

from dqk import CONFIG_DIR, RESULTS_DIR

ML_DIR = RESULTS_DIR / "ml"
ML_CONFIG = CONFIG_DIR / "ml.yaml"
