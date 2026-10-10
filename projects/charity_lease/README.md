# Charity property and lease pipeline

Match a prepared charity register to CCOD property-ownership records and
registered leases. The pipeline selects property records at a charity's address,
assigns tenure, estimates remaining lease years, and saves one row per charity.

**A match is an address-based association, not proof of ownership or tenancy.**
A charity can match both sources. The output keeps both sets of evidence.

## Quick start

You need Python 3.14 or newer, uv, and the three input datasets.
Run commands from the repository root.

**If the files are already in the input folders, use:**

```powershell
uv run --package charity-lease charity-lease-match
```

This runs every stage: preparation, matching, tenure selection, lease estimates
and deduplication. It prints the selected input paths and saves a new output.

### Where to put the inputs

All folders below are inside `projects/charity_lease/`.

| Input | Folder | Filename for automatic selection |
| --- | --- | --- |
| Prepared charity register | `datasets/charity_register_inputs/` | `charity_register_YYYYMMDD_HHMMSS_microsecondsZ.parquet` |
| CCOD ownership records | `datasets/` | `CCOD_FULL_YYYY_MM.csv` |
| Registered leases | `datasets/` | `LEASES_FULL_YYYY_MM.csv` |

The pipeline picks the newest matching filename for each input. It uses the
**date in the filename**, not the file's modification time. Property filenames
must use a four-digit year and a two-digit month from `01` to `12`.
For the register, `charity_register.parquet` is a fallback when no timestamped
register exists. The three selected inputs can have different dates.

Files must already exist locally. If an input is missing or has a different
filename, supply its path manually.

### Choose an input manually

Use `--charity-input`, `--ccod-input` or `--leases-input` to override that source.
For example, to choose a lease file:

```powershell
uv run --package charity-lease charity-lease-match --leases-input "datasets/my_leases.csv"
```

Replace the example path with your file. You can combine all three input flags.
Sources whose flags are omitted still use automatic selection.

Every relative input and output path starts from `projects/charity_lease/`,
even when the command runs from the repository root. Absolute paths also work,
but must stay inside this project.

### Other options

| Option | What it does | Default |
| --- | --- | --- |
| `--charity-input` | Choose a register Parquet file | Automatic selection above |
| `--ccod-input` | Choose an ownership CSV | Automatic selection above |
| `--leases-input` | Choose a registered-leases CSV | Automatic selection above |
| `--output-dir` | Choose the output folder | `datasets/output/` |
| `--as-of YYYY-MM-DD` | Fix the reference date for remaining-year estimates | Date the command runs |
| `--min-score` | Set the minimum matching score, from 0 to 100 | 72 |
| `--exact-only` | Compare only identical cleaned address-and-postcode keys | Disabled |
| `--format` | Choose `parquet` or `csv` output | `parquet` |
| `--allow-incomplete-leases` | Allow complete records before an unfinished final lease record | Disabled |

For reproducible lease estimates, set `--as-of` explicitly. Changing the reference
date changes remaining years, even when the inputs are unchanged.
Use `--help` to see the command's options.

## What the inputs must contain

The pipeline uses an **already prepared register**. It does not build the register
or its postcode lookups. Size and geographic fields are carried through from that
input.

| Dataset | Required fields |
| --- | --- |
| Charity register | `registered_charity_number`, `charity_name` |
| CCOD | `Property Address` |
| Registered leases | `Associated Property Description` or `Register Property Description` |

Charity numbers must be nonmissing. Duplicate charity numbers are allowed at
input and resolved at the final stage. Other missing property fields become null.
Property CSV values are read as strings so identifiers retain leading zeros.
The loader accepts `easeUnique Identifier` and `leaseUnique Identifier` as
alternative headings for `Unique Identifier`.

Matching also needs a usable address and full postcode. A row can pass the
required-field checks but remain unmatched if those values are unavailable.

## What you get

Each run creates:

```text
datasets/output/<UTC timestamp>/charity_register_with_property.parquet
```

With `--format csv`, the filename ends in `.csv`. Previous runs are preserved.
The output retains the selected register rows and adds:

| Fields | Meaning |
| --- | --- |
| `property_match_address`, `property_match_postcode`, `property_match_address_source` | Administrative address and postcode selected for matching, and the address's source |
| `ccod_*` | Selected ownership record, matching score, confidence, type, candidate count and review flag |
| `lease_*`, `registered_lease_*` | Selected lease record, matching evidence, identifiers and lease estimates |
| `ccod_matched`, `registered_lease_matched` | Independent source flags; both can be true |
| `charity_is_freeholder` | Whether the selected freehold record passes the charity/proprietor name check |
| `lease_status` | Selected tenure: usually `freehold`, `leasehold` or null |
| `review` | True when either selected source requires manual review |
| `lease_source_incomplete` | Whether the incomplete-lease exception was used |
| `lease_term_as_of_date` | Reference date used for the lease estimates |

For an unmatched source, its match flag is false, candidate count is zero and
selected-record fields are null. Parquet preserves register field types.
The output saves selected matches; it does not save every alternative candidate,
cleaned variant or internal component score.

## Methodology

The pipeline follows the same rules for every run. Matching happens separately
for each input charity row and property source. Deduplication later produces one
row per registered charity number.

### 1. Keep eligible charity rows

If `date_of_removal` exists, rows with a removal date are excluded. If it is absent,
no removal filter is applied. Calling the result an active-charity population
therefore depends on the register's removal information.

Nulls and these placeholders are treated as missing: empty string, `-`, `?`,
`N/A`, `NA`, `NONE`, `NULL` and `NAN`.

### 2. Choose the matching address

The charity address is the first usable address from this order:

1. Companies House registered-address components (`RegAddress.*`).
2. Charity registered-address fields.
3. Charity contact-address fields.

Components within each address group are joined in their defined order.
`property_match_address_source` records `companies_house`, `registered_address`
or `charity_commission` respectively.

The postcode is chosen separately, using the first available value from
`RegAddress.PostCode`, `registered_postcode`, `postcode`, `charity_postcode`
and `charity_contact_postcode`. Address and postcode can therefore come from
different upstream sources. An inconsistent postcode can prevent a match.

For CCOD, the pipeline uses `Property Address` and the supplied postcode.
Its matching-owner name is the first usable cleaned proprietor name in slots
1 to 4. Proprietor correspondence addresses are not used as property addresses.

For leases, it uses `Associated Property Description`, falling back to
`Register Property Description`, and extracts postcodes from that text.
No leaseholder name is supplied to the matching process.

### 3. Clean and expand addresses

Both sides use the same cleaning functions. They standardise case and spaces,
remove postcodes from address text, shorten common street words, and remove
selected legal wording, plan references, directions and floor descriptions.
Owner names have company suffixes and selected council phrases standardised.

Postcodes are formatted consistently and checked against a pattern. This checks
syntax, not whether the postcode exists in an official directory. For a description
split into multiple postcode sections, each section uses its embedded postcode.
Otherwise, a valid supplied postcode takes priority over the last postcode found
in the address. Text after the final postcode in a multi-section description is
not kept as a separate section.

Supported leading number lists and ranges become separate address variants.
For example, a simple numbered range can create one variant per number.
Odd/even qualifiers restrict the expansion. The implementation:

- Expands ranges when the numeric endpoints differ by 1 to 250, inclusive.
  This can produce 251 variants because both endpoints are included.
- Drops letter suffixes on range endpoints during numeric expansion.
- Expands lists of at most 250 entries.
- Leaves an address with exactly two numeric groups and `UNIT` unchanged.
- Keeps unsupported expressions as one variant.

Each variant gets an address-and-postcode key and, when a name exists, an
owner-address key. The charity name provides the charity-side owner name.
These cleaning rules can remove useful distinctions between units or interests.

### 4. Generate candidate pairs

Only variants with the **same full postcode** are compared. Property records are
first filtered to charity postcodes, then matching runs in batches of 500 charity
rows, keeping each row's variants together. Missing or incompatible postcodes
prevent matching.

The pipeline does not search by charity number, company number, title number,
UPRN or name alone. Those identifiers are retained as evidence where available.
It also does not join CCOD records directly to lease records.

`--exact-only` adds a filter for identical cleaned address-and-postcode keys.
Otherwise, different addresses within the same postcode are also scored.

### 5. Score each candidate

Two string comparisons produce the initial address score:

```text
address_score = 0.75 * token_set_similarity + 0.25 * ordered_string_similarity
```

Both use Python's `difflib.SequenceMatcher`, on a scale of 0 to 100.
The token-set comparison uses sorted unique words and their intersection,
taking the highest similarity. It ignores selected filler/location words such
as `THE`, `OF` and `LONDON`. The ordered comparison considers the normalised
string's order. Owner similarity is the higher of these two comparisons applied
to the names.

The final score applies these rules:

| Condition | Effect |
| --- | --- |
| Identical owner-address keys | Set score to 100 |
| Otherwise, identical address keys | Set score to at least 96 |
| Otherwise, any shared number token | Add 6 to the address score |
| For nonexact keys, owner similarity at least 92 | Add 5 |
| For nonexact keys, owner similarity at least 80 but below 92 | Add 3 |
| For nonexact keys, both addresses contain numbers but none overlap | Subtract 12 and cap at 68 |

Scores are limited to 0 to 100 and rounded to two decimals. Candidates below
`--min-score` are removed. The default is 72, so nonexact number-conflicting
candidates fail that threshold. Number tokens include all digit groups with an
optional letter, such as `12A`; they are not necessarily street numbers.

**Important scoring limitation:** if one owner name is missing, the scorer uses
the other side's name. Lease candidates often compare the charity name with
itself and receive the owner bonus. This is not independent evidence of a
leaseholder match. CCOD candidates without a usable proprietor name are also
affected. The freeholder check in step 7 does not use this fallback.

Token-set similarity can also be high when one address or name is contained in
a longer one. Scores and confidence labels are rules of thumb, not probabilities
that a match is correct.

### 6. Select a match and flag uncertainty

For each charity row and source, candidates are sorted by final score, then
owner score, then address score, all highest first. The top ten candidate pairs
are retained. Duplicate charity-row/target-variant pairs are then removed,
ranks are recalculated, and the first candidate is selected.

Candidate counts refer to this retained set, not every property in the postcode.
Different expanded variants of the same raw property can remain separate
candidates. Several charities can select the same property.

| Confidence | Score |
| --- | --- |
| `high` | At least 95 |
| `medium` | At least 84 but below 95 |
| `review` | Below 84 |

A selected match needs manual review if any of these applies:

- Confidence is not high.
- Its score is less than 3 points above the second retained candidate, including
  a tie. If there is no second candidate, the second score is treated as zero.
- Both addresses contain number tokens but none overlap, even on an exact key.
- Neither key is exact, owner similarity is below 50, and final score is below 98.

Match type is `exact_owner_address` or `exact_address` for equal keys.
Otherwise it is `near_exact_address` when final score is at least 96 and address
score is at least 94, or `postcode_ranked_similarity`.
Exact matches can still need review. Flags mark uncertainty; they do not remove
matches automatically or verify unflagged matches.

### 7. Combine evidence and choose tenure

Selected records are joined back using the input row identifier, with one-to-one
join checks. Both sources remain available and may refer to different legal
interests at an address.

Tenure is selected in this order:

| Evidence | `lease_status` |
| --- | --- |
| Qualifying charity-freeholder match | `freehold`, even if a lease also matches |
| Otherwise, a registered-lease match | `leasehold` |
| Otherwise, a CCOD match | CCOD tenure, trimmed and converted to lowercase |
| Neither source matches | null |

A charity-freeholder match requires all three conditions: CCOD matched, the
selected CCOD record's tenure is freehold, and the cleaned charity name scores
at least 92 against a usable name in any of its four proprietor slots.
Missing names never qualify. This check considers the selected record only.

The output records `ccod_best_matching_proprietor_name`,
`ccod_proprietor_name_match_score` and `charity_is_freeholder`.
Name containment can still produce a high score, so this remains a heuristic
check. CCOD-only freehold tenure describes the property's tenure; the additional
name flag indicates whether the implemented charity/proprietor check passed.
The combined `review` flag includes both sources, even when freehold wins.

### 8. Estimate lease duration and remaining years

Estimates are calculated only when a registered lease matched and the selected
tenure is `leasehold`. Freeholders keep raw lease evidence, but their estimates
are null. The package uses one shared eligibility rule for this decision.

The term parser looks for a numeric duration followed by `YEAR` or `YEARS`,
including decimals. If absent, it tries `YR` or `YRS`. It takes the first match
within the successful pattern. It does not interpret spelled-out durations,
month-only terms, renewals or break clauses.

The start date comes from **`Date of Lease`**, not the commencement date written
inside the term. Accepted date formats are `YYYY-MM-DD`, `DD-MM-YYYY`,
`DD/MM/YYYY`, `DD.MM.YYYY`, and a day followed by a full or abbreviated English
month and year. Ordinal day suffixes are removed. Invalid dates remain null.

Whole years are added as calendar years. If an anniversary day does not exist,
it is adjusted to the month's last day. Fractional years are converted to days
using 365.25 and truncated to a whole number of days:

```text
expiry = calendar_anniversary(start, int(years))
         + int((years - int(years)) * 365.25) days
remaining_years = max(0, (expiry - reference_date).days / 365.25)
```

Missing inputs, zero duration or date overflow prevent an expiry estimate.
Remaining years cannot be negative: an estimate at or before the reference date
becomes zero. The reference date is saved in `lease_term_as_of_date`.

| `lease_term_parse_status` | Meaning |
| --- | --- |
| `estimated_from_deed_date` | Duration and deed date produced an expiry estimate |
| `missing` | No expiry estimate and the term is absent or empty |
| `unparsed` | A term exists, but expiry could not be estimated, including when the deed date is unusable |
| `unmatched` | Estimation was skipped: no eligible lease match, including a matched charity freeholder |

**These are estimates of duration, not legal expiry.** The deed date may differ
from the legal commencement date. Renewals, variations and surrenders are not
modelled. Zero remaining years does not prove occupation ended; positive years
do not prove the lease remains effective.

### 9. Keep one row per charity

When several rows share a charity number, the pipeline prefers, in order:

1. A qualifying charity-freeholder row.
2. A row with a non-null remaining-year estimate.
3. A row with more populated fields.
4. The earlier input row.

Completeness counts non-null values across all columns, excluding blank strings.
False and zero count as populated. Higher match scores and unflagged matches are
not separate tie-breakers. The selected rows return to input order, and charity
numbers are checked for nonmissing, unique values before saving.

Other rows are discarded rather than combined. The output therefore does not
capture every property associated with a charity.

### 10. Check source completeness and save safely

Before matching, the lease CSV is checked with a strict reader that understands
quoted fields and embedded newlines. A file ending inside a quoted field is
rejected by default.

With `--allow-incomplete-leases`, the pipeline uses a temporary copy containing
only complete records before the unfinished record. It leaves the source intact
and sets `lease_source_incomplete=True` on every output row. Other malformed
CSV records raise errors.

This check detects that particular truncation, not every form of incomplete data.
A valid-looking partial extract can pass. Missing records can affect coverage,
especially if file order relates to geography or property type.

The completed result is written to a staging folder, then published in a new
run folder using a filesystem hard link. The destination must support hard links;
publication failures raise an error. Previous outputs are preserved.

## How to interpret the output

The output identifies candidate property records at administrative addresses.
It does not establish a charity's legal rights, complete portfolio or lack of
property when unmatched. Shared offices, advisers' addresses, cleaning losses
and missing postcodes can produce false or missed matches.

Differences between charity groups or areas may reflect source coverage, address
quality, source dates and parsing success as well as actual property differences.
The pipeline produces no causal estimates, calibrated error rates or statistical
confidence intervals.

For substantive use, inspect a documented sample of matches and plausible
nonmatches, especially shared addresses, close scores and freeholder-name checks.
Consider sensitivity to exact-only matching, score thresholds and review flags.
These checks are recommendations, not automatic pipeline stages.

To reproduce a run, retain the selected source paths and hashes, input provenance,
command options, fixed reference date, code revision and dependency environment.
The output records the reference date and incomplete-source flag. A full input
manifest, file hashes and alternative-candidate audit are not generated automatically.

## Code and tests

| File | Responsibility |
| --- | --- |
| [pyproject.toml](pyproject.toml) | Package metadata, dependencies and command |
| [data.py](src/charity_lease/data.py) | Paths, automatic input selection, output reading and shared validation |
| [core.py](src/charity_lease/pipeline/core.py) | Preparation, property loading, matching, merging and deduplication |
| [address_cleaning.py](src/charity_lease/pipeline/address_cleaning.py) | Address and owner-name cleaning |
| [address_matching.py](src/charity_lease/pipeline/address_matching.py) | Candidate scores, ranking and review flags |
| [lease_terms.py](src/charity_lease/pipeline/lease_terms.py) | Tenure selection and lease estimates |
| [run_charity_pipeline.py](src/charity_lease/cli/run_charity_pipeline.py) | Runs the complete workflow and publishes its output |

The runtime dependency is Polars. Run the tests from the repository root:

```powershell
uv run --package charity-lease python -m unittest discover -s projects/charity_lease/tests
```

Tests cover automatic input selection, missing identifiers, tenure precedence,
proprietor names, evidence retention, suppressed freeholder estimates,
deduplication, empty inputs and CSV/Parquet publication with small synthetic
sources. They check software behaviour, not population-level matching accuracy.
