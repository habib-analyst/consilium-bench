# consilium-bench comparison: rubric scores vs resolved diagnosis

Scores are transparent rule-based rubric proxies (0-3 per criterion), NOT physician ratings and NOT a physician-calibrated judge. `dx match` = the final report's leading assessment names the resolved diagnosis.

| case | condition | roles | rounds | consensus | C1 C2 C3 C4 C5 C6 C7 C8 | mean | dx match | reference diagnosis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CB-001 | freeform | 1 | 2 | yes | 3 | 0 | 3 | 0 | 2 | 0 | 3 | 3 | 1.75 | no | Acute anterior ST-elevation myocardial infarction |
| CB-001 | structured | 1 | 2 | yes | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 3 | 2.75 | yes | Acute anterior ST-elevation myocardial infarction |
| CB-002 | freeform | 1 | 2 | yes | 3 | 0 | 3 | 0 | 2 | 0 | 3 | 3 | 1.75 | no | Aneurysmal subarachnoid hemorrhage |
| CB-002 | structured | 1 | 2 | yes | 3 | 3 | 3 | 2 | 2 | 0 | 3 | 3 | 2.38 | no | Aneurysmal subarachnoid hemorrhage |
| CB-003 | freeform | 2 | 2 | yes | 3 | 0 | 3 | 0 | 2 | 0 | 3 | 3 | 1.75 | no | Acute pulmonary embolism |
| CB-003 | structured | 2 | 2 | yes | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3.00 | yes | Acute pulmonary embolism |
| CB-004 | freeform | 2 | 2 | yes | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 1.88 | no | Diabetic ketoacidosis |
| CB-004 | structured | 2 | 2 | yes | 3 | 3 | 3 | 3 | 3 | 0 | 3 | 3 | 2.62 | no | Diabetic ketoacidosis |
| CB-005 | freeform | 3 | 2 | yes | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 1.88 | no | Legionella pneumonia |
| CB-005 | structured | 3 | 2 | yes | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3.00 | yes | Legionella pneumonia |
| CB-006 | freeform | 1 | 2 | yes | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 1.88 | no | Acute pancreatitis |
| CB-006 | structured | 1 | 2 | yes | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 2.88 | yes | Acute pancreatitis |
| CB-007 | freeform | 1 | 2 | yes | 3 | 0 | 3 | 0 | 2 | 0 | 3 | 3 | 1.75 | no | Membranous nephropathy with nephrotic syndrome |
| CB-007 | structured | 1 | 2 | yes | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 3 | 2.75 | yes | Membranous nephropathy with nephrotic syndrome |
| CB-008 | freeform | 1 | 2 | yes | 3 | 1 | 3 | 0 | 3 | 0 | 3 | 3 | 2.00 | no | Stevens-Johnson syndrome |
| CB-008 | structured | 1 | 2 | yes | 3 | 3 | 3 | 2 | 3 | 0 | 3 | 3 | 2.50 | no | Stevens-Johnson syndrome |
