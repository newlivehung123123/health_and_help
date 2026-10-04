# Reproducing Health & Help

Jason Hung

This document rebuilds every output of the repository from the committed data, step by step, starting from a machine with no copy of the project. The free steps need no API key and make no paid call. The paid discovery step, which produced the committed records, is explained in its own section at the end and does not need to be run to reproduce the dataset or the website.

Every command below was run as written, on Linux with Python 3.13.14, on 4 October 2026, and the outputs quoted below are those it printed.

## Contents

1. [What is deterministic](#what-is-deterministic)
2. [Requirements](#requirements)
3. [Step 1. Get the code](#step-1-get-the-code)
4. [Step 2. Create a virtual environment](#step-2-create-a-virtual-environment)
5. [Step 3. Install the requirements](#step-3-install-the-requirements)
6. [Step 4. Run the tests](#step-4-run-the-tests)
7. [Step 5. Rebuild the candidate sites](#step-5-rebuild-the-candidate-sites)
8. [Step 6. Run the source check](#step-6-run-the-source-check)
9. [Step 7. Build the website data](#step-7-build-the-website-data)
10. [Step 8. Check the result](#step-8-check-the-result)
11. [Step 9. Serve the website locally](#step-9-serve-the-website-locally)
12. [Step 10. Deploy the website to a static host](#step-10-deploy-the-website-to-a-static-host)
13. [The paid discovery step](#the-paid-discovery-step)

## What is deterministic

An output is deterministic when the same inputs always give the same file, byte for byte. The table lists every step.

| Step | Outputs | Deterministic |
|---|---|---|
| Tests | Printed result only | Yes. The tests use temporary folders, download nothing and call no API |
| Merge, `scripts/discover.py --merge` | `data/candidates.csv`, `data/discovery/province_counts.csv` | Yes. A run on the committed records gives files identical to the committed ones |
| Source check, `scripts/check_sources.py` | `data/source_check.csv`, `data/candidates_checked.csv` | In part. The columns that come from the records and the corrections, and the list of sites with their identifiers, are always the same. The columns that describe the downloaded pages depend on the pages as they stand on the day of the run and on the network the machine can reach |
| Site build, `scripts/build_site_data.py` | `site/data/sites.json`, `site/data/health_and_help_candidates.csv`, `site/data/codebook.md` | Yes, apart from one field. `meta.built` in `sites.json` holds the date of the run, so `sites.json` matches the committed file only when it is built on 4 October 2026. The other two files are identical to the committed ones |
| Inclusion report, `scripts/inclusion_report.py` | Printed result only | Yes |
| Discovery, `scripts/discover.py --round 1`, `2` or `3` | `data/discovery/` files | No. The model's output and the web search results change between runs |

## Requirements

1. Python 3.13. The commands were tested with Python 3.13.14, and the GitHub Actions workflow in `.github/workflows/tests.yml` uses Python 3.13.
2. git, to clone the repository.
3. A connection to the Python Package Index, to install the requirements.
4. For Step 6 only, a connection that can reach the evidence pages on the open web.

No API key is needed for any step before the paid discovery step.

The commands are written for a shell on macOS or Linux. On Windows, the command that activates the virtual environment is `.venv\Scripts\activate` in place of `source .venv/bin/activate`, and `python` replaces `python3.13`.

## Step 1. Get the code

```bash
git clone https://github.com/newlivehung123123/health_and_help.git
cd health_and_help
```

Every later command is run from this folder.

## Step 2. Create a virtual environment

A virtual environment is a folder that holds its own copy of Python and of the packages installed into it, so that the project does not change the system's Python. The folder `.venv` is listed in `.gitignore`.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

After activation, the command `python` runs the Python of `.venv`. The command `deactivate` leaves the environment.

## Step 3. Install the requirements

```bash
pip install -r requirements.txt
```

The file `requirements.txt` pins two packages, `anthropic==1.11.0`, the client library for the Anthropic API, which the tests import and which discovery uses, and `pypdf==6.19.0`, which the source check uses to read evidence pages published as PDF files. pip also installs their dependencies.

## Step 4. Run the tests

```bash
python -m unittest discover -s tests
```

The run ends with the lines below. The tests make no API call, download no page and need no key.

```text
Ran 96 tests in 3.760s

OK
```

The time varies between machines. The test `test_dry_runs_need_no_key` in `tests/test_discover.py` runs the dry run of each discovery round as a separate process, which reads the committed files and writes nothing.

## Step 5. Rebuild the candidate sites

The merge groups the 56 committed discovery records into organisations and candidate sites. It reads `data/discovery/round1.jsonl`, `round2.jsonl` and `round3.jsonl`, makes no API call and costs nothing.

```bash
python scripts/discover.py --merge
```

It prints the lines below, the first with the full path of the file, and the second with the names of the 51 provinces that have no candidate site, shortened here.

```text
56 records, 34 organisations, 53 sites written to .../data/candidates.csv
Nationwide services 2. Provinces with no candidates 51 of 77: TH-14 Phra Nakhon Si Ayutthaya, ...
Sites of one organisation in the same provinces, to check for duplicates: Bangrak STIs Center (Bangrak Medical Center), Department of Disease Control (Sathorn); Bangrak STIs Center (Bangrak Medical Center), Department of Disease Control (Bang Rak)
```

The outputs are `data/candidates.csv` and `data/discovery/province_counts.csv`. The command `git status` then shows no change, because the files are identical to the committed ones. The possible duplicate that the last line names is resolved by the first correction in `config/corrections.csv`, which Step 6 applies.

## Step 6. Run the source check

The source check applies `config/corrections.csv` to the records, downloads each evidence page and tests whether each copied sentence appears on its page. It uses no AI, needs no key and costs nothing, but it needs a connection to the evidence pages.

```bash
python scripts/check_sources.py
```

The outputs are `data/source_check.csv` and `data/candidates_checked.csv`, and the script overwrites the committed copies. Each page that is read is saved in `data/raw/pages/`, which is not committed, so a second run downloads only the pages it could not read before. The option `--refetch` downloads every page again, and `--workers` sets how many pages are downloaded at the same time, 8 by default.

The committed results were produced by a run that printed the summary below, shortened here where it lists the 9 sentences not checked.

```text
56 records with 43 evidence pages. Pages read 35, not read 5, little text 0, social pages needing a login 3.
Quotes found on their page 46 of 56, partly found 1, not found 0, not checked because the page was not read 9.
  ...
Records excluded by config/corrections.csv 2
  ...
Sites recorded as naming sex workers whose evidence pages show none of the terms for sex workers 0 of 35
Sites recorded as naming sex workers whose evidence pages show only พนักงานบริการ without a qualifier, which can also mean service staff, 3: ...
Written data/source_check.csv (56 records) and data/candidates_checked.csv (50 sites)
```

A new run will give these figures only if every page is still online and unchanged. Two cases need care.

1. A machine that cannot reach the evidence pages, for example behind a proxy that blocks them, reports every page as not read and every sentence as not checked. In a test of this kind on 4 October 2026, the run still wrote 56 records and 50 sites with the same identifiers, names, provinces, services, evidence addresses and copied sentences as the committed files, while the columns `page`, `quote_check`, `quote_share_found`, `sex_work_terms_on_page`, `final_url`, `text_file`, `quotes_found`, `sex_work_terms_on_pages` and `pages_not_read` differed.
2. Step 7 reads the files that Step 6 writes. To build the website from the committed check results rather than from a new run, restore them first.

```bash
git diff --stat
git checkout -- data/source_check.csv data/candidates_checked.csv
```

The first command shows which files the run changed, and the second returns the two files to their committed state.

## Step 7. Build the website data

The site build reads `data/candidates_checked.csv`, `data/source_check.csv`, `data/discovery/cost_log.csv`, `config/provinces.csv`, `config/province_points.csv`, `config/taxonomy.json` and `codebook.md`. It makes no API call and costs nothing.

```bash
python scripts/build_site_data.py
```

With the committed files, it prints the lines below.

```text
50 sites of 34 organisations. 29 meet the inclusion rule, 6 name sex workers with no core service recorded, 15 do not clearly name sex workers.
26 of 77 provinces have a candidate and 23 a source naming sex workers; 2 services are nationwide.
Quotes found on their source page 45 of 54. Discovery spent $8.69 of $27.30 on 249 web searches.
Wrote site/data/sites.json, health_and_help_candidates.csv and codebook.md
```

The outputs are `site/data/sites.json`, `site/data/health_and_help_candidates.csv` and `site/data/codebook.md`. On any date other than 4 October 2026, `git diff` reports a change in `site/data/sites.json`, and the only difference is the value of `built`.

## Step 8. Check the result

The inclusion report applies the inclusion rule of `codebook.md` to the checked sites and checks their coded values. It reads files only.

```bash
python scripts/inclusion_report.py
```

With the committed files, it prints the lines below, shortened where it names the four government sites, and exits with status 0. It exits with status 1 when a coded value is not allowed by the codebook.

```text
29 of 50 sites, of 23 organisations, meet the inclusion rule, out of 34 organisations in the file.
Sites whose sources name sex workers 35, of which 6 have no core service recorded. Sites whose sources do not clearly name sex workers 15.
Government sites that meet the rule 4. Confirm for each that the facility's own pages name sex workers: ...
Coded values not allowed by the codebook 0
```

Given the public file as its argument, as in `python scripts/inclusion_report.py site/data/health_and_help_candidates.csv`, it also reports how many rows of the column `meets_inclusion` disagree with the rule, which is 0 for the committed file.

## Step 9. Serve the website locally

The page loads `data/sites.json` with a fetch request, which browsers commonly block for a page opened directly from disk, so the folder is served over HTTP.

```bash
python -m http.server 8722 --directory site
```

The website is then at http://localhost:8722 until the server is stopped with Ctrl+C. The browser also needs a connection to the internet, because the page loads the map library Leaflet 1.9.4 from cdnjs, map tiles from Esri and fonts from Google Fonts. Without that connection, the page shows a notice in place of the map, because `site/js/app.js` checks that Leaflet has loaded before it draws the map, and the fonts from Google Fonts do not load.

## Step 10. Deploy the website to a static host

The folder `site/` is the whole website. It has no server code and no build step, so any host that serves static files can publish it. The live copy is at https://healthnhelp.aiinsocietyhub.com.

1. Run Step 7, so that `site/data/` holds the current data.
2. Upload the contents of `site/`, not the folder itself, so that `index.html` sits at the root of the address. The upload must keep the folders `css/`, `js/` and `data/`.
3. Open the address and confirm that the map, the list and the download links load.

Any static host works this way, for example GitHub Pages through a workflow that publishes `site/`, Netlify, Cloudflare Pages or a web server such as nginx. With a server reachable over SSH, one command copies the folder, where the host name and path are those of the server.

```bash
rsync -av --delete site/ user@example.org:/var/www/health-and-help/
```

The upload contains only the files in `site/`, and never `.env` or anything in `data/raw/`.

## The paid discovery step

Discovery is the only step that calls a large language model, and it is the only step that costs money. It produced the committed files in `data/discovery/`. Nothing in this section needs to be run to reproduce the dataset or the website. Discovery cannot be repeated exactly, because the model's output and the results of its web searches change between runs.

### What the step does

`scripts/discover.py` sends each job to the model `claude-sonnet-5-5` through the Anthropic API, at medium effort with adaptive thinking. Each request in rounds 1 and 2 carries two tools, the provider's basic web search tool (`web_search_20250305`) and the tool `record_candidates`, through which the model returns candidates in the layout of `data/discovery/round1.jsonl`. Requests in round 3 also carry the provider's web fetch tool (`web_fetch_20250910`), which reads up to 5 pages per request with at most 12,000 tokens each. The instructions to the model are the constant `SYSTEM` and the function `job_prompt` in `scripts/discover.py`.

The three rounds run in order, and round 3 does not start until every job of rounds 1 and 2 has finished.

| Round | Jobs | Searches allowed per job | Searches allowed in all | What the jobs search |
|---|---|---|---|---|
| 1 | 5 | 10 | 50 | The whole country, by type of organisation |
| 2 | 24 | 6, or 8 for the groups of Bangkok, Chon Buri, Chiang Mai and Phuket | 152 | One group of provinces each, covering all 77 provinces |
| 3 | 22, built from the records of rounds 1 and 2 | 4 or 6 | 128 | Known organisations not yet found, clinic and partner lists, provinces where no source names sex workers, and organisations known only from Facebook or LINE |

A job stops when its searches reach one and a half times its allowance, when its cost reaches $0.10 for each search allowed, or after 14 requests. The spending guard adds up `data/discovery/cost_log.csv` before every command and holds back a margin for every request in progress, $0.40 at first and then the cost of the most expensive request so far. It stops before the total could pass the discovery share of $13.00, out of the $27.30 of API credit that the project has. The option `--share` raises that share.

### Cost recorded in the repository

`data/discovery/cost_log.csv` records 58 requests, all with `claude-sonnet-5-5`, logged on 4 October 2026 between 02:48 and 03:42 UTC. They cost $8.69 in all, for 249 web searches and 5 page fetches.

| Round | Requests | Web searches | Page fetches | Cost |
|---|---|---|---|---|
| 1 | 8 | 45 | 0 | $1.67 |
| 2 | 24 | 85 | 0 | $2.90 |
| 3 | 26 | 119 | 5 | $4.12 |
| All | 58 | 249 | 5 | $8.69 |

Round 1 includes a first attempt at the job `r1_a_sex_worker_led`, one request for $0.11, made with an earlier version of the search tool and replaced when the job ran again. `DATA.md` explains the difference between the cost log and the job summaries.

### The dry run

The dry run prints the instructions to the model, the jobs, the spending so far and a cost estimate, and makes no API call. It needs no key.

```bash
python scripts/discover.py --round 1 --dry-run
python scripts/discover.py --round 2 --dry-run
python scripts/discover.py --round 3 --dry-run
```

With the committed files, each dry run ends with lines like those below, here for round 3. The estimate is the logged cost per search, $0.035 including tokens, times the searches allowed. It counts only the 57 requests made after the switch to the basic search tool, which cost $8.58 together.

```text
Discovery has spent $8.69 of its $13.00 share, so $4.31 is left.
Cost estimate: About $4.50 for 22 jobs with up to 128 searches, at $0.035 for each search including tokens, from 57 logged requests costing $8.58. The upper figure is more than the $4.31 this command may spend, so some jobs may not run.
No API calls were made.
```

The option `--show-all` prints the prompt of every job, not only the first.

### Running discovery

A paid run needs an Anthropic API key. Copy `.env.example` to `.env` and write the key after `ANTHROPIC_API_KEY=`. The file `.env` is listed in `.gitignore` and must never be committed or shared.

```bash
cp .env.example .env
python scripts/discover.py --round 1 --only r1_a_sex_worker_led
python scripts/discover.py --round 1
python scripts/discover.py --round 2
python scripts/discover.py --round 3
python scripts/discover.py --merge
```

The first paid command runs one job, to check the key and the cost. In this repository every job of the three rounds is already marked complete, so each `--round` command above skips all its jobs, prints "Nothing to run." and makes no request. The option `--force` runs jobs again and replaces their records, and every new request adds to the spending already in `data/discovery/cost_log.csv`. A new study from empty discovery files is described in `REPLICATION.md`.

The other options are `--test`, which runs one job with 3 searches and at most $1.00 into separate files that start with `test_`, `--budget`, a lower limit in US dollars for one command, `--effort`, which sets the model's effort, `--model`, which accepts `claude-sonnet-5-5` (the default) or `claude-opus-5-5`, `--max-tokens`, the output limit of each request, 32,000 by default, `--workers`, the number of jobs run at the same time, 3 by default, and `--only`, which selects jobs by job, province group or province code. The command `python scripts/discover.py --help` lists them all.
