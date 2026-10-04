# Health & Help (สุขภาพและความช่วยเหลือ)

Jason Hung

Health & Help is an open dataset, and a prototype website built on it, that lists organisations in Thailand which offer sexual health or mental health services to sex workers. Every record carries the web address of its source and a sentence copied word for word from that source, so that a reader can check each record. The project was built for the World Bank Small AI for Development challenge, health track, at the Hack-Nation 7th Global AI Hackathon in October 2026.

The project serves two groups. The first group is sex workers in Thailand who look for a nearby service such as an HIV test, pre-exposure prophylaxis (PrEP, a medicine taken before possible exposure to HIV) or counselling. The second group is the organisations, researchers and funders who need to know which provinces have such services and which have none.

The live site is at https://healthnhelp.aiinsocietyhub.com.

## Contents

1. [Terms used in this repository](#terms-used-in-this-repository)
2. [The pipeline](#the-pipeline)
3. [Headline figures](#headline-figures)
4. [Repository layout](#repository-layout)
5. [Quick start](#quick-start)
6. [Further documents](#further-documents)
7. [Limitations](#limitations)
8. [Safety rules](#safety-rules)
9. [Licence](#licence)
10. [How to cite](#how-to-cite)

## Terms used in this repository

The terms below are used in the same sense in every document of the repository.

| Term | Meaning |
|---|---|
| Record | One candidate that the model returned in one discovery job, stored as one line of `data/discovery/round1.jsonl`, `round2.jsonl` or `round3.jsonl` |
| Organisation | A group of records that share a website or social media page, identified by `org_id` |
| Candidate site | One place, branch or nationwide service of an organisation, identified by `site_id`, and one row of `data/candidates.csv` or `data/candidates_checked.csv` |
| Copied sentence | The passage, under 300 characters, that the model copied from the evidence page of a record, stored in the field `evidence_quote` and in the column `evidence_quotes` |
| Core service | One of the nine services marked as core in Table 1 of `codebook.md`, namely HIV testing, testing for sexually transmitted infections (STIs), STI treatment, HIV treatment, PrEP, post-exposure prophylaxis (PEP), condoms and lubricant, referral, and mental health support |
| Inclusion rule | The rule in `codebook.md` that a site is shown in the app only when a source names sex workers as people the organisation serves and the site offers at least one core service |
| Job | One task sent to the model, such as a search of one group of provinces, with its own limit on web searches |
| Round | One of the three sets of discovery jobs |

## The pipeline

The pipeline has three steps, run in the order below. Only the first step uses a large language model, and it was run once. The second and third steps use no model and cost nothing.

1. **Discovery with a large model, run once.** The script `scripts/discover.py` sends 51 jobs in three rounds to the model `claude-sonnet-5-5` through the Anthropic API, with the provider's web search tool. Round 1 has 5 national jobs, round 2 has 24 jobs that together cover all 77 provinces, and round 3 has 22 follow-up jobs built from the records of rounds 1 and 2. The model returns each candidate with the web address of its evidence page and a copied sentence from that page. The option `--merge` then groups the records into organisations and candidate sites and writes `data/candidates.csv`. The merge itself makes no API call.
2. **Source check, with no AI.** The script `scripts/check_sources.py` applies the corrections in `config/corrections.csv`, downloads each evidence page and tests whether the copied sentence appears on that page. A sentence counts as found when at least 90 percent of its overlapping pieces of eight characters appear on the page, with spacing, punctuation and case ignored. Pages on Facebook, LINE and X need a login, so the check lists them for a person to read. The script writes `data/source_check.csv` and `data/candidates_checked.csv`.
3. **Site build.** The script `scripts/build_site_data.py` reads the checked sites, the source check, the province lists and the taxonomy, and writes `site/data/sites.json`, the public file `site/data/health_and_help_candidates.csv` and a copy of `codebook.md`. The folder `site/` is a static website in HTML, CSS and JavaScript with no build step.

The earlier design of the project also planned an extraction step that fills every variable of `codebook.md` Tables 2 to 11 with its own source passage, a monthly recheck of the sources, a small classifier that runs on the phone, an offline version of the web app and an SMS service. None of these components is in the repository yet, and the files `health_and_help_sites.csv` and `evidence.csv` that `codebook.md` describes do not exist yet.

## Headline figures

Every figure below is counted from a file in this repository, named after the figure.

| Figure | Value | What it counts | Source |
|---|---|---|---|
| Discovery records | 56 records | Candidates returned by the model, 36 in round 1, 13 in round 2 and 7 in round 3 | Lines of `data/discovery/round1.jsonl`, `round2.jsonl` and `round3.jsonl` |
| Candidate sites after the merge | 53 candidate sites | Rows after the merge, before any correction | Rows of `data/candidates.csv` |
| Candidate sites after the source check | 50 candidate sites of 34 organisations | Rows after one record was moved to an existing site and two records were excluded by `config/corrections.csv` | Rows and distinct `org_id` values of `data/candidates_checked.csv` |
| Sites meeting the inclusion rule | 29 of the 50 candidate sites, belonging to 23 organisations | Sites with `sex_worker_mention` equal to yes and at least one core service | Column `meets_inclusion` of `site/data/health_and_help_candidates.csv`, and `meta.included` in `site/data/sites.json` |
| Copied sentences found, all records | 46 of the 56 copied sentences | Sentences that the source check found on their evidence page, before exclusions. One more was partly found and 9 could not be checked | Column `quote_check` of `data/source_check.csv` |
| Copied sentences found, records kept | 45 of the 54 copied sentences | The same count after the two excluded records are removed, which is the figure the website reports | `meta.quotes_found` and `meta.records` in `site/data/sites.json` |
| Provinces with a candidate site | 26 of 77 provinces | Provinces with at least one candidate site | `meta.provinces_with_candidate` in `site/data/sites.json` |
| Provinces with a source naming sex workers | 23 of 77 provinces | Provinces with at least one site whose source names sex workers | `meta.provinces_covered` in `site/data/sites.json` |
| Discovery cost | $8.69 for 58 requests and 249 web searches | All requests to the model, in US dollars at the prices set in `scripts/discover.py` | Column `cost_usd` of `data/discovery/cost_log.csv` |

Of the 50 candidate sites, 35 have a source that names sex workers, 6 of these 35 have no core service recorded, and 15 sites have a source that does not clearly name sex workers. The command `python scripts/inclusion_report.py` prints these counts from `data/candidates_checked.csv`.

## Repository layout

| Path | Contents |
|---|---|
| `.claude/launch.json` | Local launch setting that serves `site/` on port 8722 |
| `.claude/settings.json` | Local tool setting that adds no attribution lines to commits or pull requests |
| `.env.example` | Template of the `.env` file, with one empty variable for the API key that discovery needs |
| `.github/workflows/tests.yml` | GitHub Actions workflow that runs the unit tests on every push, with no secrets |
| `.gitignore` | Files that are never committed, namely `.env`, `.venv/`, `__pycache__/`, `data/raw/` and `.DS_Store` |
| `CITATION.cff` | Citation metadata in the Citation File Format |
| `DATA.md` | Every data file with its rows, columns, origin and meaning |
| `LICENSE` | MIT licence for the code |
| `README.md` | This overview |
| `REPLICATION.md` | How to repeat the study for another country or a later date |
| `REPRODUCE.md` | Step by step reproduction from a clean machine |
| `codebook.md` | Variables, inclusion rule and safety rules of the dataset |
| `config/corrections.csv` | Three corrections written after a person read the sources, each with its reason |
| `config/province_points.csv` | An approximate point for the capital of each of the 77 provinces, used for the map pins |
| `config/provinces.csv` | The 77 provinces with Thai names, other spellings, region, search group and main towns |
| `config/taxonomy.json` | Codes and English and Thai labels for services, populations, organisation types and other categories, and the search terms |
| `data/candidates.csv` | Candidate sites after the merge, one row per site |
| `data/candidates_checked.csv` | Candidate sites after the corrections and the source check |
| `data/discovery/cost_log.csv` | One row per request to the model, with tokens, searches and cost |
| `data/discovery/jobs_round1.jsonl` | One line per round 1 job with its status, searches, requests and cost |
| `data/discovery/jobs_round2.jsonl` | One line per round 2 job, in the same layout |
| `data/discovery/jobs_round3.jsonl` | One line per round 3 job, in the same layout |
| `data/discovery/province_counts.csv` | Candidate sites per province after the merge |
| `data/discovery/round1.jsonl` | One line per record returned in round 1 |
| `data/discovery/round2.jsonl` | One line per record returned in round 2 |
| `data/discovery/round3.jsonl` | One line per record returned in round 3 |
| `data/source_check.csv` | One row per record with the result of the source check |
| `requirements.txt` | The two Python packages the scripts need, with exact versions |
| `scripts/build_site_data.py` | Site build, which writes the data files of the website |
| `scripts/check_sources.py` | Source check, which downloads evidence pages and looks for each copied sentence |
| `scripts/discover.py` | Discovery in three rounds, the dry run and the merge |
| `scripts/inclusion_report.py` | Read-only report of the sites that meet the inclusion rule and of coded values the codebook does not allow |
| `site/css/site.css` | Styles of the website |
| `site/data/codebook.md` | Copy of `codebook.md` offered for download on the website |
| `site/data/health_and_help_candidates.csv` | Public file of the 50 candidate sites, described in Table 12 of `codebook.md` |
| `site/data/sites.json` | Data that the website reads |
| `site/index.html` | The single page of the website |
| `site/js/app.js` | Map, list, filters and site profiles of the website, in English and Thai |
| `tests/test_build_site_data.py` | Offline tests of the site build |
| `tests/test_check_sources.py` | Offline tests of the source check |
| `tests/test_discover.py` | Offline tests of discovery, the spending guard and the merge |
| `tests/test_documentation.py` | Tests that the figures and file lists in the documentation match the files |

The folder `data/raw/` is created by the scripts and is never committed. `DATA.md` describes what it holds.

## Quick start

The commands below need Python 3.13 and use no API key. `REPRODUCE.md` gives each step in full.

```bash
git clone https://github.com/newlivehung123123/health_and_help.git
cd health_and_help
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests
python scripts/build_site_data.py
python -m http.server 8722 --directory site
```

The last command serves the website at http://localhost:8722 until it is stopped with Ctrl+C.

## Further documents

`REPRODUCE.md` rebuilds every output from the committed data and explains the paid discovery step. `REPLICATION.md` explains how to repeat the study for another country or a later date. `DATA.md` describes every data file. `codebook.md` defines the variables and the inclusion rule.

## Limitations

1. The dataset covers 26 of the 77 provinces, and 51 provinces have no candidate site. A province with no candidate site may still have services that the web searches did not find.
2. Every record was written by the model. The repository records three corrections made after a person read the sources, and no file records that a person has compared every site with its sources. The value `human_checked` of the variable `verification` in `codebook.md` is not used yet.
3. The source check confirms that a copied sentence appears on its page, but not that the page attributes the sentence to the organisation recorded. One record that the check found word for word was excluded for this reason, as `config/corrections.csv` explains.
4. Nine of the 54 copied sentences kept were not checked, 5 because their pages could not be read and 4 because they are on Facebook or X pages that need a login.
5. The column `meets_inclusion` tests only the two computable conditions of the inclusion rule. The rule in `codebook.md` also admits government facilities only when their own pages name sex workers and excludes private for-profit clinics, and these two clauses are left to a person. `scripts/inclusion_report.py` lists the 4 government sites that pass the computed test for that review.
6. The value `sex_worker_mention` is the model's reading of the source. Of the 35 sites recorded as naming sex workers, 29 cite a page on which the source check found a specific term for sex workers, 3 cite pages that use only the Thai term พนักงานบริการ, which can also mean service staff, and 3 cite pages that could not be read.
7. Discovery cannot be repeated exactly, because the model's output and the web search results change between runs. The source check also depends on the pages as they stand on the day it runs.

## Safety rules

1. The dataset records only contacts that organisations publish themselves. The record that discovery asks the model to fill has no field for a street address or a phone number, and its contact fields hold only the organisation's own website, Facebook or LINE page and other official pages. The model is told never to record the address of a drop-in centre, shelter or safe house that the organisation does not publish, and `codebook.md` adds that the address of a shelter or safe house is never recorded even when published.
2. Location is recorded at province level and, when a source states it, at district or town level in the column `city`. No coordinates of individual sites are recorded. Each pin on the map marks the approximate point for the provincial capital in `config/province_points.csv`, and never the address of a service.
3. The dataset records no names of staff, volunteers or clients, and nothing about individual sex workers. The model is told not to record the names of individual people. The model's free-text notes stay in the working files in `data/`, and the site build leaves them out of `site/data/sites.json` and `site/data/health_and_help_candidates.csv`, because notes can name people.
4. The website asks for no personal data and does not use the browser's location. It loads the map library Leaflet 1.9.4 from cdnjs, map tiles from Esri and fonts from Google Fonts, so a browser that opens the site contacts those three services.

## Licence

The code is released under the MIT licence in `LICENSE`, copyright 2026 Jason H. The data files, meaning the files in `data/` and `config/` and the files `site/data/sites.json` and `site/data/health_and_help_candidates.csv`, are released under the Creative Commons Attribution 4.0 International licence (CC BY 4.0, https://creativecommons.org/licenses/by/4.0/). The copied sentences in those files, held in the field `evidence_quote` and the columns `evidence_quotes` and `evidence_quote`, remain under the terms of their source pages and are not covered by either licence.

## How to cite

The file `CITATION.cff` holds the citation metadata, which GitHub shows under "Cite this repository". A plain citation reads as below.

```text
Hung, J. (2026). Health & Help. Open dataset of sexual and mental health services for sex workers in Thailand, with code and prototype website. https://github.com/newlivehung123123/health_and_help
```

```bibtex
@misc{hung2026healthandhelp,
  author = {Hung, Jason},
  title  = {Health \& Help. Open dataset of sexual and mental health services for sex workers in Thailand},
  year   = {2026},
  url    = {https://github.com/newlivehung123123/health_and_help},
  note   = {Live site https://healthnhelp.aiinsocietyhub.com}
}
```
