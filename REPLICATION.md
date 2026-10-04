# Replicating Health & Help

Jason Hung

This document explains how another team could repeat the study, either for Thailand at a later date or for another country. A replication runs the whole pipeline again, the paid discovery step included, and so produces new records. It differs from a reproduction, which `REPRODUCE.md` describes, and which rebuilds the outputs from the committed records without any paid call.

## Contents

1. [What a replication involves](#what-a-replication-involves)
2. [Replication for Thailand at a later date](#replication-for-thailand-at-a-later-date)
3. [Replication for another country](#replication-for-another-country)
4. [Checking new results against the inclusion rule](#checking-new-results-against-the-inclusion-rule)
5. [Reporting a replication](#reporting-a-replication)

## What a replication involves

A replication repeats the three steps of the pipeline in `README.md`, discovery with a large language model, the source check with no AI and the site build. Discovery needs an Anthropic API key and costs money. The committed run cost $8.69 for 58 requests and 249 web searches, according to `data/discovery/cost_log.csv`, and the dry run of each round prints an estimate before any money is spent. The results of a replication will differ from the committed results even for the same country on the same day, because the model's output and the web search results change between runs.

The scripts read and write fixed paths. Discovery writes to `data/discovery/`, the source check writes to `data/source_check.csv` and `data/candidates_checked.csv`, and the site build writes to `site/data/`. A replication therefore works in its own clone or fork of the repository, and moves the committed results aside before it starts.

## Replication for Thailand at a later date

A replication for Thailand keeps every configuration file except the corrections, which refer to the records of the committed run.

### 1. Prepare a clean copy

```bash
git clone https://github.com/newlivehung123123/health_and_help.git health_and_help_replication
cd health_and_help_replication
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Move the committed results aside

The spending guard of `scripts/discover.py` adds up every row of `data/discovery/cost_log.csv`, and a later run skips every job that the job summaries mark as complete. The committed discovery files are therefore moved to a separate folder, together with a copy of the checked sites for the comparison in the last step.

```bash
mkdir -p earlier/discovery
cp data/candidates_checked.csv earlier/candidates_checked.csv
mv data/discovery/* earlier/discovery/
```

### 3. Empty the corrections

Each correction in `config/corrections.csv` names a round, a job and an organisation of the committed run. The command below keeps only the header line. A correction that matches no record would otherwise be reported and ignored.

```bash
printf 'round,job_id,name,field,value,reason\n' > config/corrections.csv
```

### 4. Review the configuration

The files below define what discovery searches for. A replication at a later date may keep them as they are, and any change should be reported with the results.

| File | What to review |
|---|---|
| `config/provinces.csv` | Province names, other spellings, search groups (column `cluster`) and main towns, which are written into the prompts of rounds 2 and 3 |
| `config/taxonomy.json` | The search terms for sex workers and for services, in Thai and in English, under the key `search_terms` |
| `config/province_points.csv` | Only if a province's capital has moved |

Some settings of discovery are constants in `scripts/discover.py` rather than configuration files. They are the model and its prices (`MODEL` and `PRICES`), the credit and the share that discovery may spend (`CREDIT` and `DISCOVERY_SHARE`), the searches allowed per job (`ROUND_CAPS` and `BIG_CLUSTER_CAP`), the organisations that round 1 checks first (`ROUND1`), the organisations that round 3 looks for again if they were not found (`LEADS`) and the clinic list that round 3 reads (`CLINIC_LISTS`). If the model `claude-sonnet-5-5` is no longer offered, or its prices have changed, `MODEL` and `PRICES` must be changed before a paid run, and the change reported, because the spending guard computes the cost from `PRICES`.

### 5. Run the dry runs

```bash
python scripts/discover.py --round 1 --dry-run
python scripts/discover.py --round 2 --dry-run
python scripts/discover.py --round 3 --dry-run
```

With empty discovery files, the dry run of round 1 reports that discovery has spent $0.00 of its $13.00 share and gives a rough range of $1.88 to $3.50 for 5 jobs with up to 50 searches, because no requests are logged yet. Since rounds 1 and 2 have no records yet, the dry run of round 3 lists 28 jobs, namely the lead job, one job that reads the clinic list and 26 gap jobs that cover all 77 provinces, and it reports that a paid run of round 3 will not start until rounds 1 and 2 have finished. After the first paid job, the estimates use the logged cost per search.

### 6. Run discovery

```bash
cp .env.example .env
python scripts/discover.py --round 1 --only r1_a_sex_worker_led
python scripts/discover.py --round 1
python scripts/discover.py --round 2
python scripts/discover.py --round 3
python scripts/discover.py --merge
```

The key goes after `ANTHROPIC_API_KEY=` in `.env`, which `.gitignore` keeps out of the repository. The first paid command runs one job, to check the key and calibrate the cost. A command that stops early, because of the spending guard or an interruption, resumes when it is run again and skips the jobs already finished. Round 3 does not start until every job of rounds 1 and 2 has finished. The merge writes `data/candidates.csv` and `data/discovery/province_counts.csv` and lists the sites of one organisation in the same provinces, which may be duplicates.

### 7. Run the source check and write corrections

```bash
python scripts/check_sources.py
```

The source check needs a connection to the evidence pages. A person then reads the pages behind every record that the check could not confirm, every page that needs a login, and every possible duplicate from the merge. Each record found wrong gets one row in `config/corrections.csv`, with the round, the job, the name as recorded, the field, the new value and the reason. The field `exclude` with the value `yes` excludes a record that its own source does not support. The source check is then run again, and it applies the corrections.

### 8. Build the website data and check the result

```bash
python scripts/build_site_data.py
python scripts/inclusion_report.py
python scripts/inclusion_report.py site/data/health_and_help_candidates.csv --compare earlier/candidates_checked.csv
```

The last command compares the new sites with the committed ones, as the section on checking explains.

### 9. Update the documentation

The test file `tests/test_documentation.py` compares the figures in `README.md`, the row and column counts in `DATA.md` and the number of tests in `REPRODUCE.md` with the files. After a replication those tests fail until the documents carry the new figures, and the failure messages show which figure to change. The other tests do not depend on the committed records. A run of the full suite on a copy with empty discovery files passed every test outside `tests/test_documentation.py`.

## Replication for another country

A study of another country needs new configuration files and also changes to constants in the scripts and to the website, because the committed code was written for Thailand. These changes alter the behaviour of the scripts, so they belong in the replicating team's own fork, and the inclusion rule should stay as `codebook.md` defines it so that the results remain comparable.

### Configuration files

| File | Change |
|---|---|
| `config/provinces.csv` | One row per first-level subdivision of the country. `code` is the ISO 3166-2 code, a standard code for a country subdivision. `name_en`, `aliases_en` and `towns_en` are in English. `name_th` and `towns_th` hold names in the main local language, because the scripts read those column names. `region` holds the regions that the website will group subdivisions by, and `cluster` puts the subdivisions into search groups for round 2 |
| `config/province_points.csv` | One approximate point, in decimal degrees, for the capital of each subdivision |
| `config/taxonomy.json` | New search terms under `search_terms` in the local language and in English, and local-language labels in the fields `th`, which the scripts and the website read. The 19 service codes and the 9 core services should stay as they are, so that the inclusion rule is unchanged |
| `config/corrections.csv` | Only the header line, as in step 3 above |

### Constants in the scripts

| File | Constant | Why it must change |
|---|---|---|
| `scripts/discover.py` | `SYSTEM` | The instructions to the model name Thailand, the Thai terms for sex workers and the rule on the ambiguous Thai term พนักงานบริการ |
| `scripts/discover.py` | `ROUND1` and `LEADS` | They name organisations and networks in Thailand |
| `scripts/discover.py` | `ROUND2_TASK`, `GAP_TASK` and `LEADS_TASK` | They name Thailand, ask for searches with Thai names or give Thai search terms |
| `scripts/discover.py` | `CLINIC_LISTS` | A list of clinics in Thailand that round 3 reads |
| `scripts/discover.py` | `BIG_CLUSTERS` | The four search groups of round 2 that receive 8 searches instead of 6, given by their codes in the column `cluster` |
| `scripts/discover.py` | `MULTI_UNIT_DOMAINS` | The Thai domains `go.th`, `ac.th`, `or.th` and `mi.th`, which the merge treats as hosts of many separate units |
| `scripts/check_sources.py` | `SEX_WORK_TERMS` and `BARE_TERM` | The terms for sex workers that the check looks for on each page, in English and Thai |
| `scripts/check_sources.py` | `CODECS` and the `Accept-Language` header in `download` | Thai text encodings and the Thai language preference |
| `scripts/build_site_data.py` | `THAILAND` and `BARE_MARK` | The box of latitude and longitude that every province point must lie in, and the label of the ambiguous Thai term |
| `site/js/app.js` | `THAILAND`, `BOUNDS` and `REGIONS`, and the English and Thai interface text | The map's extent, the six regions of Thailand and the two interface languages |
| `site/index.html` | The page text | It describes Thailand |

The tests also hold figures for Thailand. In `tests/test_discover.py`, the class `ConfigTests` expects 77 provinces in 24 search groups, the number of provinces in each of the six regions, round sizes of 5 jobs with 50 searches and 24 jobs with 152 searches, and 28 round 3 jobs when there are no records. In `tests/test_build_site_data.py`, the class `ProvincePointTests` expects 77 points. These expected values change with the new configuration.

After these changes, the steps are those of the replication for Thailand, from step 2 onwards.

## Checking new results against the inclusion rule

The inclusion rule in `codebook.md` admits a site to the app only when a source names sex workers as people the organisation serves and the site offers at least one of the nine core services of Table 1. It also admits government facilities only when the facility's own pages name sex workers, and it excludes private for-profit clinics. The checks below apply the rule to new results.

1. **Apply the computable test.** The command `python scripts/inclusion_report.py` reads `data/candidates_checked.csv` and counts the sites whose `sex_worker_mention` is yes and whose `services_mentioned` includes a core service. This is the test that `scripts/build_site_data.py` uses for the column `meets_inclusion`.
2. **Check the public file.** The command `python scripts/inclusion_report.py site/data/health_and_help_candidates.csv` also reports how many rows of `meets_inclusion` disagree with the rule. The count should be 0.
3. **Check the coded values.** The same report lists every service code, province code, organisation type, level and yes, no or unclear value that the codebook does not allow, and exits with status 1 when it finds one.
4. **Confirm the clauses that cannot be computed.** The report lists the government sites that pass the computed test. A person confirms for each that the facility's own pages name sex workers. No column records whether a clinic is private and for profit, so a person also reads the evidence of every included site and excludes private for-profit clinics with a correction.
5. **Confirm the evidence.** For every included site, the column `quotes_found` of `data/candidates_checked.csv` should show every copied sentence found. The summary of `scripts/check_sources.py` lists the sites recorded as naming sex workers whose pages show none of the terms for sex workers, or only the ambiguous Thai term, and the column `pages_not_read` lists the pages a person must read.
6. **Record every decision.** Each change goes into `config/corrections.csv` with its reason, after which the source check and the site build are run again, so that every published value can be traced to a source or to a recorded correction.
7. **Compare with the committed run.** The option `--compare` of `scripts/inclusion_report.py` joins two files of candidate sites on `site_id`. The merge computes `site_id` from the organisation's web address key, its provinces and its city, so a site recorded alike in both runs keeps the same identifier, while a site whose recorded web addresses change receives a new one. The report counts the sites in both files, in only one of them, and those that gained or lost inclusion.

## Reporting a replication

A report of a replication should give the date of the run, the model and its prices, every change to the configuration files and to the constants in the scripts, the cost from `data/discovery/cost_log.csv`, and the figures of the headline table in `README.md` for the new run, namely the discovery records, the candidate sites before and after the source check, the sites that meet the inclusion rule, the copied sentences found, and the provinces with a candidate site and with a source that names sex workers. The committed run gives the figures for Thailand on 4 October 2026 against which a later replication can be compared.
