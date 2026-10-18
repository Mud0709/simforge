# Bundled synthetic datasets

Invented for testing and teaching; they describe no real people or measurements. Their
profiles are worked out by hand in `backend/tests/quant/test_samples.py`.

* `lab_measurements.csv`: a clean table (12 rows, 5 columns, no missing values).
* `messy_survey.csv`: deliberately awkward. Missing values written three ways (empty, `NA`,
  and an unrecognised lower-case `n/a`), an exact duplicate row, a blank line, identifiers
  with leading zeros, a number with a thousands separator, ambiguous dd/mm dates, a cell
  with surrounding spaces, and `NA` used as the country code for Namibia, which the default
  missing-value markers read as missing.
