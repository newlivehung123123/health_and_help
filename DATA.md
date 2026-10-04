# Data files of Health & Help

Jason Hung

This document describes every data file in the repository, with its number of rows and columns, the script that writes it and what one row means. It also describes the folder `data/raw/`, which the scripts create and which is never committed. The variables of the published dataset are defined in `codebook.md`, and each section below names the tables of `codebook.md` that apply.

## Conventions

A row of a CSV file (comma-separated values) is one line after the header line. A row of a JSONL file (JSON Lines, one JSON object per line) is one line, and its columns are the keys of the object. All CSV files that the scripts write are encoded in UTF-8 with a byte order mark, except `data/discovery/cost_log.csv`, which is UTF-8 without one. In the CSV files, a cell with several values separates them with a semicolon and a space, except the copied sentences in `evidence_quotes`, which are separated by a space, a vertical bar and a space. A copied sentence is the passage, under 300 characters, that the model copied word for word from an evidence page.

## Summary

The table gives every data file in the order in which the pipeline uses or writes it. The counts were taken from the committed files. "Not tabular" marks a file that has no rows and columns.

| File | Rows | Columns | Written by |
|---|---|---|---|
| `config/provinces.csv` | 77 | 8 | No script, edited by hand |
| `config/province_points.csv` | 77 | 3 | No script, edited by hand |
| `config/taxonomy.json` | Not tabular | Not tabular | No script, edited by hand |
| `config/corrections.csv` | 3 | 6 | No script, written by a person after reading a source |
| `data/discovery/round1.jsonl` | 36 | 22 | `scripts/discover.py --round 1` |
| `data/discovery/round2.jsonl` | 13 | 22 | `scripts/discover.py --round 2` |
| `data/discovery/round3.jsonl` | 7 | 22 | `scripts/discover.py --round 3` |
| `data/discovery/jobs_round1.jsonl` | 5 | 15 | `scripts/discover.py --round 1` |
| `data/discovery/jobs_round2.jsonl` | 24 | 15 | `scripts/discover.py --round 2` |
| `data/discovery/jobs_round3.jsonl` | 22 | 15 | `scripts/discover.py --round 3` |
| `data/discovery/cost_log.csv` | 58 | 14 | `scripts/discover.py`, every paid request |
| `data/candidates.csv` | 53 | 24 | `scripts/discover.py --merge` |
| `data/discovery/province_counts.csv` | 77 | 6 | `scripts/discover.py --merge` |
| `data/source_check.csv` | 56 | 16 | `scripts/check_sources.py` |
| `data/candidates_checked.csv` | 50 | 27 | `scripts/check_sources.py` |
| `site/data/sites.json` | Not tabular | Not tabular | `scripts/build_site_data.py` |
| `site/data/health_and_help_candidates.csv` | 50 | 25 | `scripts/build_site_data.py` |
| `site/data/codebook.md` | Not tabular | Not tabular | `scripts/build_site_data.py`, a copy of `codebook.md` |

## Files described in codebook.md that do not exist yet

Tables 2 to 11 of `codebook.md` describe two files, `health_and_help_sites.csv` and `evidence.csv`, which a planned extraction step will write. Neither file is in the repository, and no script writes either of them yet. The files below use some of the same variable names and codes, and each section says which.

## Configuration files

### config/provinces.csv

There is one row for each of the 77 provinces of Thailand. The columns are `code` (the ISO 3166-2 code, a standard code for a country subdivision, such as TH-10 for Bangkok), `name_en`, `aliases_en` (other English spellings), `name_th`, `region` (one of the six regions in Table 4 of `codebook.md`), `cluster` (one of the 24 search groups of round 2, such as BKK or NE1), `towns_en` and `towns_th` (main towns, in English and Thai). The lists in `aliases_en`, `towns_en` and `towns_th` are separated by semicolons. `scripts/discover.py` uses the file to build the prompts and the jobs of round 2 and round 3, and to check that every province code the model returns is valid. `scripts/build_site_data.py` uses the names and regions.

### config/province_points.csv

There is one row for each of the 77 provinces. The columns are `code`, `lat` and `lon`, an approximate latitude and longitude of the provincial capital in decimal degrees. `scripts/build_site_data.py` places one map pin per province at this point and stops with an error when a province has no point or when a point lies outside the box from 5.5 to 20.5 degrees north and from 97.3 to 105.7 degrees east. The file holds no coordinates of any service.

### config/taxonomy.json

The file is a JSON object with 11 keys. The key `service_types` holds the 19 service codes of Table 1 of `codebook.md`, each with an English label, a Thai label and the flag `core`, which is true for the 9 core services. The keys `populations` (10 codes, Table 10), `org_types` (7 codes, Table 3), `levels` (5 codes, Table 3), `approach` (3 codes, Table 3), `service_modes` (5 codes, Table 6), `fees` (4 codes, Table 6), `languages` (7 codes, Table 6), `status` (4 codes, Table 9) and `verification` (2 codes, Table 9) hold the other codes with their labels. The key `search_terms` holds four lists of search terms, for sex workers and for services, in Thai and in English, which `scripts/discover.py` writes into the instructions for the model. The scripts read only `service_types`, `org_types`, `levels` and `search_terms`, and the other keys serve the planned files.

### config/corrections.csv

Each row is one correction that a person wrote after reading the evidence page of a record. The columns are `round`, `job_id` and `name`, which together identify the record by its round, its job and its English name (or Thai name when no English name was recorded), `field`, the name of the field to change, `value`, the new value, and `reason`. The field `exclude` with the value `yes` excludes the record. `scripts/check_sources.py` applies the corrections to copies of the discovery records, so the files in `data/discovery/` never change. The three rows move one round 3 record of the Bangrak STIs Center from Bang Rak to Sathorn, which the evidence page gives as the district of its address, and exclude two round 2 records of SWING (Service Workers in Group Foundation) in Nakhon Pathom and Hat Yai, whose evidence page lists those branches under another organisation.

## Discovery files

### data/discovery/round1.jsonl, round2.jsonl and round3.jsonl

Each line is one record, meaning one candidate that the model returned in one job. The three files hold 36, 13 and 7 records, 56 in all. The first 18 keys are the fields that the model fills, as defined by the tool schema in `scripts/discover.py`, namely `name_en`, `name_th`, `acronym`, `website`, `facebook_or_line`, `other_urls` (a list), `org_type` (codes of Table 3), `level` (codes of Table 3), `province_codes` (a list of codes from `config/provinces.csv`, or `nationwide` for a service open to the whole country), `city`, `sex_worker_mention` (yes, no or unclear), `evidence_url`, `evidence_quote` (the copied sentence), `services_mentioned` (a list of codes of Table 1), `sex_worker_led` (yes, no or unclear), `partner_list_url`, `latest_activity_seen` and `notes`. The script adds four keys, `round`, `job_id`, `recorded_at` (the time in UTC) and `model`. When a job is run again, the script removes the earlier records of that job before it saves the new ones.

### data/discovery/jobs_round1.jsonl, jobs_round2.jsonl and jobs_round3.jsonl

Each line summarises one job. The three files hold 5, 24 and 22 jobs, and every one of the 51 jobs has the status `complete`. The keys are `job_id`, `round`, `status`, `note`, `requests` (requests sent to the model), `continuations` (paused turns that were resumed), `searches` (web searches run), `fetches` (pages read with the web fetch tool, used only in round 3), `cost_usd`, `candidates` (records saved), `searches_run` (the queries that the model reported), `provinces_without_findings`, `comments` (the model's notes on coverage), `citations` (empty in every committed line) and `finished_at`. The status is `complete`, `capped` when the job reached one of its own limits, `stopped` when the spending guard or an interruption ended it, `no_record`, `refused` or `failed`. A later run skips jobs whose status is `complete`, `capped`, `no_record` or `refused`.

### data/discovery/cost_log.csv

Each row is one request to the model, test runs included. The columns are `timestamp` (UTC), `round`, `job_id`, `model`, `request` (the number of the request within its job), `stop_reason`, `input_tokens`, `cache_write_tokens`, `cache_read_tokens`, `output_tokens`, `web_searches`, `web_fetches`, `cost_usd` and `test` (1 for a test run, 0 otherwise). The cost is computed by `request_cost` in `scripts/discover.py` from the prices set in that script, which for `claude-sonnet-5-5` are $2.00 per million input tokens, $10.00 per million output tokens, $2.50 per million tokens written to the prompt cache, $0.20 per million tokens read from it and $0.01 per web search. The spending guard of `scripts/discover.py` adds up this column before every command and every request.

The 58 committed rows were logged on 4 October 2026 between 02:48 and 03:42 UTC, all with `claude-sonnet-5-5` and none as a test run. They add up to $8.69 for 249 web searches and 5 page fetches. By round, round 1 has 8 requests, 45 searches and $1.67, round 2 has 24 requests, 85 searches and $2.90, and round 3 has 26 requests, 119 searches, 5 fetches and $4.12. The first row, at 02:48, is a first attempt at job `r1_a_sex_worker_led` with the earlier version of the search tool. That job was run again at 03:07, which replaced its records and its job summary, so the job summaries of round 1 count 7 requests, 40 searches and $1.55, while the cost log keeps all 8 requests.

### data/candidates.csv

Each row is one candidate site, the result of grouping the 56 records without any correction. The merge in `scripts/discover.py` joins records into one organisation when they share a website or social media page, and into one site when they also share the same provinces and city. A record without a city joins the organisation's only site in the same provinces. The file holds 53 sites of 34 organisations. The `org_id` is the letter O and the first eight characters of a SHA-1 hash of the organisation's grouping key, and the `site_id` adds a hyphen and six characters of a hash of that key, the provinces and the city, so the same records always give the same identifiers.

The 24 columns are `org_id`, `site_id`, `name_en`, `name_th`, `acronym`, `org_type`, `level`, `province_codes`, `province_en`, `city`, `sex_worker_mention`, `sex_worker_led`, `services_mentioned`, `website`, `facebook_or_line`, `other_urls`, `partner_list_urls`, `evidence_urls`, `evidence_quotes`, `latest_activity_seen`, `notes`, `found_in_rounds`, `job_ids` and `n_records`. The first 20 of these, all but the last four, have the meaning given in Table 12 of `codebook.md`. The column `notes` joins the model's notes, `found_in_rounds` and `job_ids` list the rounds and jobs that produced the site's records, and `n_records` counts those records. Within a site, most single values are the most frequent value among its records, `latest_activity_seen` is the latest date, a list joins the values of all its records, and `sex_worker_mention` and `sex_worker_led` are yes when any record says yes.

### data/discovery/province_counts.csv

There is one row for each of the 77 provinces, written by the same merge. The columns are `code`, `name_en`, `name_th`, `region`, `candidates`, the number of sites in `data/candidates.csv` with that province among their `province_codes`, and `candidates_sex_worker_named`, the number of those sites whose `sex_worker_mention` is yes. The file is counted before the corrections, so 26 provinces have a candidate and 24 have a site whose source names sex workers, compared with 23 after the corrections.

## Source check files

### data/source_check.csv

Each row is one of the 56 discovery records after the corrections, numbered in the column `record` in the order of round 1, round 2 and round 3. The columns are `record`, `round`, `job_id`, `name`, `province_codes`, `city`, `sex_worker_mention`, `evidence_url`, `page` (whether the page was read, and why not when it was not), `quote_check` (found, partly found, not found or not checked), `quote_share_found` (the share of the sentence's overlapping pieces of eight characters that appear on the page, from 0 to 1), `sex_work_terms_on_page` (the terms for sex workers that the page uses, from the list in `scripts/check_sources.py`), `excluded` (the reason, for a record excluded by `config/corrections.csv`), `evidence_quote`, `final_url` (the address after redirects) and `text_file` (the path of the saved page text under `data/raw/pages/`, which is not committed).

The committed file records that 46 of the 56 copied sentences were found on their page, 1 was partly found and 9 were not checked. The 56 records cite 43 distinct pages, of which 35 were read, 5 could not be read and 3 are Facebook or X pages that need a login. The columns from `record` to `evidence_url`, together with `excluded` and `evidence_quote`, come from the records and the corrections. The columns `page`, `quote_check`, `quote_share_found`, `sex_work_terms_on_page`, `final_url` and `text_file` depend on the pages as they were downloaded.

### data/candidates_checked.csv

Each row is one candidate site after the corrections, built by the same merge as `data/candidates.csv` from the records that were not excluded. The file holds 50 sites of 34 organisations. The 27 columns are the 24 columns of `data/candidates.csv` followed by `quotes_found` (k of n sentences found), `sex_work_terms_on_pages` and `pages_not_read`, all three defined in Table 12 of `codebook.md`. For 42 of the 50 sites every copied sentence was found.

## Website files

### site/data/health_and_help_candidates.csv

This is the public file of the dataset, offered for download on the website, with one row for each of the 50 sites of `data/candidates_checked.csv`. Its 25 columns are those of Table 12 of `codebook.md`, in the same order. Compared with `data/candidates_checked.csv`, the build removes `notes`, `found_in_rounds`, `job_ids` and `n_records`, adds `region` and `meets_inclusion`, and removes the bold markers `**` that the model sometimes put in a copied sentence. The column `meets_inclusion` is yes for 29 sites, those whose `sex_worker_mention` is yes and whose `services_mentioned` includes at least one core service of Table 1.

### site/data/sites.json

This is the file that the website reads. It is a JSON object with seven keys.

| Key | Contents |
|---|---|
| `meta` | 19 summary figures, namely `built` (the date of the build), `sites` (50), `orgs` (34), `included` (29), `named` (35), `unconfirmed` (6), `unclear` (15), `led` (8), `nationwide` (2), `provinces` (77), `provinces_with_candidate` (26), `provinces_covered` (23), `records` (54), `quotes_found` (45), `pages` (42), `pages_read` (34), `search_cost` (8.69), `searches` (249) and `credit` (27.3, the API credit in US dollars) |
| `services` | The 19 service types of Table 1 with labels, the core flag and the number of sites offering each |
| `org_types` | English and Thai labels of the 7 organisation types |
| `levels` | English and Thai labels of the 5 levels |
| `provinces` | The 77 provinces with code, names, region, the point of the capital, the numbers of sites `n`, `n_named` and `n_included`, and a `status` of covered (23), unclear (3) or gap (51) |
| `sites` | The 50 sites, each with its evidence pages, copied sentences and the result of the source check for each sentence, and a `status` of included (29), unconfirmed (6) or unclear (15) |
| `columns` | The 25 column names of the public CSV |

The figures `records`, `quotes_found`, `pages` and `pages_read` count only the 54 records that were not excluded. The figures `search_cost` and `searches` add up `data/discovery/cost_log.csv`. Like the public CSV, the file leaves out the model's notes and the bookkeeping columns of the discovery runs.

### site/data/codebook.md

An exact copy of `codebook.md`, written by the build so that the website can offer it for download.

## data/raw, which is not committed

The scripts write two folders under `data/raw/`, and `.gitignore` excludes the whole folder from the repository.

| Folder | Written by | Contents |
|---|---|---|
| `data/raw/discovery/` | `scripts/discover.py` | One file per job, named after the job (with the prefix `test_` for a test run), holding the full API response of every request in that job, including the search results and the model's output |
| `data/raw/pages/` | `scripts/check_sources.py` | For each evidence page that was downloaded and was not a bot check, three files named after the first 16 characters of the SHA-1 hash of its address, namely the page as downloaded (`.html` or `.pdf`), its extracted text (`.txt`) and its metadata (`.json`, with the address, the final address, the time of download, the content type, the size and the page state) |

The repository does not state a reason for the exclusion beyond the entry in `.gitignore`. One property of these files bears on it. The saved pages are copies of third-party web pages whose rights belong to their publishers, so the licences of this repository could not cover them, and the API responses hold the search results that the provider returned from those pages. Without `data/raw/pages/`, a new run of `scripts/check_sources.py` downloads every page again, and `REPRODUCE.md` explains what that means for its results.
