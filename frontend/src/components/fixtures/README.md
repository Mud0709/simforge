# Test fixtures

`messySurveyProfile.json` is the API's response for the bundled `messy_survey` sample with
default options, with run metadata (id, time, versions) replaced by fixed values. UI tests
use it to check _where_ things are shown; the numbers themselves are checked against
hand-derived answers in `backend/tests/quant/test_samples.py`. Regenerate it if the
profile schema changes.
