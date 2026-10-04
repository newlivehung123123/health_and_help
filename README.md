# Health & Help (สุขภาพและความช่วยเหลือ)

Health & Help is an offline assistant that helps sex workers in Thailand find sexual health and mental health services near them, together with the open dataset of organisations that the assistant uses. The design follows one principle, big model once and small model every day. Claude Sonnet 5.5 is used once, upstream, to find organisations, extract each fact with the source passage that supports the fact, translate the records and write example questions. A small classifier of a few hundred kilobytes then runs on the phone with no connection and answers only with checked records. The same classifier answers by SMS for phones without mobile data.

Health & Help was built for the World Bank Small AI for Development challenge, health track, at the Hack-Nation 7th Global AI Hackathon in October 2026.

## Status

The discovery step, the source check, the prototype website, their offline tests and the dataset codebook are written. The steps still to come are extraction and translation, the monthly recheck, the classifier, the offline version of the web app and the SMS simulator.

## Setup

Python 3.13 and an Anthropic API key are needed. The requirements are the Anthropic Python SDK and pypdf, which reads source pages published as PDF files.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Add the key to `.env`. The file `.env` is listed in `.gitignore` and is never committed.

## API budget

The project has $27.30 of Anthropic API credit in all, which the hackathon provides, and no other money for API calls. The table below shows how the credit is divided among the steps that call the model. The reserve is spent last, on whichever step needs more.

| Step | Share |
|---|---|
| Discovery of organisations, test runs included | $13.00 |
| Extraction of each fact with its source passage, through the Message Batches API at half price | $6.00 |
| Descriptions and translation | $1.50 |
| Example questions for the classifier | $1.50 |
| Demonstration of the monthly recheck | $0.50 |
| Reserve, spent last | $4.80 |
| Total | $27.30 |

Discovery uses Claude Sonnet 5.5 at medium effort, which costs half as much per token as Claude Opus 5.5. The search tool is the basic version, which shows the model every result. The version with dynamic filtering makes the model write code to read the results, and in the first paid job that code failed, so the model ran one query three times and stopped after five of its ten searches.

## Finding organisations

The dry run is free. The dry run prints the prompts, the jobs, the spending so far and a cost estimate without calling the API.

```bash
.venv/bin/python scripts/discover.py --round 1 --dry-run
```

The first paid command runs one real job of round 1, the national search for organisations led by sex workers, with up to ten searches. The job checks the key and the setup, and its logged cost calibrates the estimates for the remaining jobs. The records of this job count toward round 1, so the job is not paid for twice.

```bash
.venv/bin/python scripts/discover.py --round 1 --only r1_a_sex_worker_led
```

The rest of the three rounds then run in order, and the merge groups the records into organisations and sites. Running a command again resumes the round and skips jobs already done. Round 3 does not start until every job of rounds 1 and 2 has finished, because round 3 searches what the first two rounds have not covered.

```bash
.venv/bin/python scripts/discover.py --round 1
.venv/bin/python scripts/discover.py --round 2
.venv/bin/python scripts/discover.py --round 3
.venv/bin/python scripts/discover.py --merge
```

Every command adds up the cost of all earlier requests in `data/discovery/cost_log.csv`, test runs included, and stops before the next request could take discovery past its $13.00 share. Before each request, the command holds back a margin for every request in progress, $0.40 at first and then the cost of the dearest request so far, and stops when the money already spent plus those margins would pass the limit. A command that finds too little of the share left does not start, and says how to give discovery more of the credit with `--share`.

Each job also has limits of its own. One request may use all of a job's searches, and each time the model records candidates it is told how many searches have run and how many are left. A job stops when its searches reach one and a half times its search limit, when its cost reaches $0.10 for each search allowed, or after 14 requests. Such a job is marked capped, keeps its records and is skipped when the round runs again, so that no job is paid for twice.

Rounds 1 and 2 cost $4.46 for 125 searches, or $0.036 for each search including tokens, and the dry run uses the logged cost per search for its estimates. Requests logged before the switch to basic search are not used in the estimate, because they cost less for each search. Round 2 ran 85 of its 152 searches, for two reasons. The prompt told the model that each search costs money, so every job ended after one request. The model also searched the word พนักงานบริการ on its own, which also means service staff, so about one result in five was a job advertisement. The prompt now asks the model to use every search, to name one province in each query and to use the specific Thai terms for sex workers.

Round 3 runs four kinds of job. The first searches for known organisations not yet found. The second reads the Love Foundation clinic list and the partner lists found in earlier rounds. The gap jobs search every province where no record has a source that names sex workers, in jobs of up to three provinces with two searches for each province, and look again for sources on the organisations recorded there without such a source. The last job confirms organisations known only from Facebook or LINE. After rounds 1 and 2, round 3 has 22 jobs with up to 128 searches, which the dry run estimates at about $4.57, so discovery would spend about $9.14 of its $13.00 share. The estimate does not include page reads, because rounds 1 and 2 read no pages. Each round 3 job may read up to five pages in each request, and a page of the maximum length, 12,000 tokens, costs about as much as one search, so round 3 may cost more than the estimate. Each job still ends once its cost reaches $0.10 for each search allowed, and the spending guard still halts discovery before it passes its share.

Round 3 ran all 22 jobs for $4.12 and 119 searches, or $0.035 for each search, and read 5 pages. The gap jobs used all 110 of their searches. Round 3 added 7 records. Two of the 7 records give the first source that names sex workers in Udon Thani and in Lampang. After the three rounds, 26 of the 77 provinces have at least one candidate and 24 have a source that names sex workers. Discovery spent $8.69 of its $13.00 share in all.

The merge groups records into organisations by shared website or social page, and into sites by province and city. A record without a city joins the organisation's only site in the same provinces. The merge lists every organisation that still has more than one site in the same provinces, so that possible duplicates can be checked.

The options in the table below select jobs and control cost.

| Option | Effect |
|---|---|
| `--only r2_cnx,TH-83` | Runs only the listed jobs, province groups or provinces |
| `--force` | Runs jobs again even when already done, replacing the records of those jobs |
| `--share 15` | Raises the total that discovery may spend over all commands from $13.00, for example with money from the reserve |
| `--budget 2` | Sets a lower limit in US dollars for this command only |
| `--effort low` | Lowers the model's effort from medium, which cuts cost and may find fewer organisations |
| `--workers 1` | Runs one job at a time instead of three, for when the API reports rate limit errors (HTTP 429) |
| `--test` | Runs one job with three searches and at most $1.00, into separate files whose records do not count toward the round |
| `--show-all` | With `--dry-run`, prints every job prompt |

## Checking sources

The source check downloads the page that each record cites as its evidence and confirms that the recorded quote appears on that page. The check makes no API calls, needs no key and costs nothing.

```bash
.venv/bin/python scripts/check_sources.py
```

Each page is saved with its text in `data/raw/pages`, so a second run downloads only the pages that could not be read before, and the extraction step reads the same text. The option `--refetch` downloads every page again, and `--workers` sets how many pages are downloaded at the same time, eight by default. The check reads web pages and PDF files, and decodes each page as UTF-8 before trying the encoding that the page declares, because many Thai sites declare the wrong encoding. A quote counts as found when at least 90 percent of its overlapping pieces of eight characters appear on the page, with spacing, punctuation and case ignored, and as partly found from 50 percent. A page with fewer than 200 letters and digits is reported as having little text, and a quote on such a page that is not found counts as not checked, because the page shows too little to judge. A short page that a site sends to programs instead of the page asked for, such as a request to enable JavaScript or to prove that the reader is human, counts as a bot check. A bot check is reported as not read and is not saved, so the next run tries the page again. Pages on Facebook, LINE and X need a login, so the check lists them for a person to read. The check also lists the terms for sex workers that each page uses. The bare term พนักงานบริการ also means service staff, so the check reports the bare term apart from the qualified terms such as พนักงานบริการหญิง.

A person who reads a source and finds a record wrong writes a correction in `config/corrections.csv`, with the round, the job, the organisation's name as recorded, the field, the new value and the reason. The check applies the corrections to copies of the discovery records, so the discovery files stay unchanged, and the values of a list field are separated by semicolons. The field `exclude` with the value `yes` excludes a record that its own source does not support, and the reason is written with the record in `data/source_check.csv`. Excluded records are removed before the records are grouped into sites. A correction that matches no record is reported.

The first run of the check, on the 56 records of the three rounds, found 41 quotes on their pages, partly found 1, did not find 4 and could not check 10. Every change since then came from the check and not from the records. The World Vision Thailand site sent an old copy of its pages to programs that do not ask for compressed pages, so three quotes were missing from the copy received. The check now asks for compressed pages as browsers do, and the same change gave the full text of two articles on PubMed Central that had shown little text. The fourth quote not found was on a bot check that the first version counted as a page read.

After those fixes, 46 of the 56 quotes are on their pages and none is missing. The 56 records cite 43 pages, of which 35 were read. Five pages could not be read, because one server refused the request, one server could not be found, one page no longer exists, one server did not answer within 30 seconds and one site sent a bot check. The 9 quotes not checked are the 5 on those pages and 4 on three Facebook and X pages, which a person must read.

Two records are excluded. Both are round 2 records of SWING, in Nakhon Pathom and in Hat Yai, and both cite the same Department of Disease Control page. That page lists SWING branches in Silom, Saphan Khwai and Pattaya only, and lists Nakhon Pathom and Hat Yai under the Rainbow Sky Association of Thailand, which round 1 already records in both provinces. The Nakhon Pathom quote joins words from two places on that page and was partly found. The Hat Yai quote is on the page word for word, so the check found the Hat Yai quote even though the page gives the Hat Yai details to another organisation. The check therefore confirms that a quote is on its page but not that the page attributes the quote to the organisation recorded. The same page also lists a SWING branch at Saphan Khwai in Bangkok that discovery did not record.

The merge flagged one possible duplicate, the Bangrak STIs Center, which round 1 records in Sathorn and round 3 in Bang Rak. The evidence page gives the centre's address on South Sathorn Road in Sathorn district, and Bang Rak is only the centre's name, so a correction moves the round 3 record to Sathorn, and the centre becomes one site with both quotes found.

After the corrections, `data/candidates_checked.csv` holds 50 sites, compared with 53 in `data/candidates.csv`, and every quote is found for 42 of the 50 sites. Of the 35 sites recorded as naming sex workers, 29 cite at least one page that uses a qualified term for sex workers. Three sites cite pages that use only the bare term พนักงานบริการ, and on all three pages the bare term appears in a list of key populations for HIV next to men who have sex with men and transgender people, where the term means sex workers. The other three sites cite pages that could not be read. The 50 sites cover 26 of the 77 provinces, and 23 provinces have a source that names sex workers, one fewer than after discovery, because the excluded SWING record was the only such source in Nakhon Pathom.

## Prototype website

The folder `site` holds the prototype website, a static page in HTML, CSS and JavaScript with no build step. The website shows the checked candidate sites on a map of Thailand, in a list and in a grid, with a search box and filters by service, region, evidence and leadership by sex workers. Each site has a profile with the sentences that the model copied from the evidence pages and the result of the source check. A board of the 77 provinces, grouped by region, shows which provinces have a source that names sex workers, and the download section offers the public CSV and the codebook.

The website reads `site/data/sites.json`. The script `scripts/build_site_data.py` writes that file from `data/candidates_checked.csv`, `data/source_check.csv`, `config/provinces.csv`, `config/province_points.csv` and `config/taxonomy.json`, together with the public file `site/data/health_and_help_candidates.csv` and a copy of `codebook.md`. The script makes no API calls and costs nothing.

```bash
.venv/bin/python scripts/build_site_data.py
```

The public CSV excludes the model's notes, which can name people, and the bookkeeping columns of the discovery runs. Table 12 of the codebook describes the 25 columns of the public CSV. A pin on the map marks the capital of the province, from `config/province_points.csv`, and never the address of a service. After the two exclusions, 45 of the 54 remaining quotes are on their pages, and the website reports that count.

The website can be viewed on a computer by serving the folder `site` and opening [https://healthnhelp.aiinsocietyhub.com/](https://healthnhelp.aiinsocietyhub.com/).

```bash
python3 -m http.server 8722 --directory site
```

The map uses Leaflet 1.9.4 from cdnjs and the World Dark Gray Canvas tiles from Esri, and the fonts come from Google Fonts. The browser therefore requests map tiles from Esri and fonts from Google, and the website needs a connection to show the map and the fonts.

## Output files

Each round writes records, job summaries and costs to `data/discovery`, and the source check writes the last three files, as the table below shows. The test run writes to files that start with `test_`, so the test records never mix with the full rounds.

| Path | Contents |
|---|---|
| `data/discovery/round1.jsonl` (and rounds 2 and 3) | One line per candidate, with the job, the round and the time |
| `data/discovery/jobs_round1.jsonl` (and rounds 2 and 3) | One line per job with its status, searches, requests and cost. The status is complete, capped when the job reached one of its own limits, stopped when the spending guard or an interruption ended the job, no_record when the job ended without recording a candidate, refused when the model declined the job, or failed. A rerun skips complete, capped, no_record and refused jobs |
| `data/discovery/cost_log.csv` | One row per API request with the model, tokens, searches and cost, which the spending guard adds up |
| `data/discovery/province_counts.csv` | Candidates per province after the merge, and how many of them name sex workers |
| `data/raw/discovery/` | Full API responses for checking, never committed |
| `data/candidates.csv` | Merged candidates with one row per site |
| `data/raw/pages/` | Each evidence page as downloaded, with its text and the time of download, never committed |
| `data/source_check.csv` | One row per record with its evidence page, whether the page was read, whether the quote was found and what share of the quote was found, the terms for sex workers on the page and the reason for any exclusion |
| `data/candidates_checked.csv` | The sites of `data/candidates.csv` after the corrections and exclusions, with the quotes found, the terms for sex workers on the evidence pages and the pages not read |

## Tests

The tests make no API calls, download no page and need no key.

```bash
.venv/bin/python -m unittest discover -s tests
```

## Files

| Path | Contents |
|---|---|
| `.claude/launch.json` | Settings that start the local web server for the prototype website on port 8722 |
| `codebook.md` | Variables, inclusion rule and safety rules of the published dataset |
| `config/corrections.csv` | Corrections and exclusions written after reading a source, each with its reason |
| `config/provinces.csv` | The 77 provinces with Thai names, other spellings, region, search group and main towns |
| `config/province_points.csv` | An approximate point for the capital of each of the 77 provinces, which places the pins on the map |
| `config/taxonomy.json` | Codes for services, populations, organisation types and the other categories, with English and Thai labels |
| `scripts/build_site_data.py` | Build of the data files that the prototype website reads |
| `scripts/check_sources.py` | Download of evidence pages and the check that each quote is on its page |
| `scripts/discover.py` | Discovery of candidate organisations in three rounds |
| `site/` | The prototype website, with its data files in `site/data` |
| `tests/test_build_site_data.py` | Offline tests of the website data build |
| `tests/test_check_sources.py` | Offline tests of the source check |
| `tests/test_discover.py` | Offline tests of discovery and merging |

## Data safety

The dataset records only contacts that organisations publish themselves, never the address of a shelter or safe house, and no names of staff, volunteers or clients. The app is designed to run on the phone and to send nothing about what a user asks.
