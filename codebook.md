# Health & Help dataset codebook

Health & Help (สุขภาพและความช่วยเหลือ in Thai) is an open dataset of organisations in Thailand that serve sex workers and provide sexual health screening, treatment or referral, or mental health support. The dataset has two files. The file `health_and_help_sites.csv` has one row for each site where an organisation provides services, and the file `evidence.csv` records, for each value in `health_and_help_sites.csv`, the source page and the passage that support the value. An organisation with branches in several provinces has one row per branch, and all branches of the organisation share one `org_id`. A nationwide hotline, online service or LINE Official Account (a business account on the LINE messaging app) has one row with `coverage` set to `national`. The dataset records nothing about individual sex workers.

## Inclusion rule

A site is shown in the Health & Help app only when two conditions hold. First, a source names sex workers as people the organisation serves. Second, the site provides at least one of the nine core services marked in Table 1, which are HIV testing, testing for sexually transmitted infections (STIs), STI treatment, HIV treatment, pre-exposure prophylaxis (PrEP), post-exposure prophylaxis (PEP), condoms and lubricant, referral to sexual health or mental health services, and mental health support. Government facilities are included only when the facility's own pages name sex workers. Private for-profit clinics are excluded. Candidates that fail either condition remain in the file with `meets_inclusion` set to `no` and an `exclusion_reason`, so that a reader can see which organisations were checked and why each one was excluded.

Table 1 lists the 19 service types with their Thai labels. The nine core services decide inclusion, and the other ten describe further support that a site offers.

**Table 1. Service types**

| Code | English | Thai | Core |
|---|---|---|---|
| hiv_testing | HIV testing | ตรวจเอชไอวี | yes |
| sti_testing | STI testing | ตรวจโรคติดต่อทางเพศสัมพันธ์ | yes |
| sti_treatment | STI treatment | รักษาโรคติดต่อทางเพศสัมพันธ์ | yes |
| hiv_treatment | HIV treatment | รักษาเอชไอวีด้วยยาต้านไวรัส | yes |
| prep | PrEP (pre-exposure prophylaxis) | เพร็พ ยาป้องกันก่อนสัมผัสเชื้อเอชไอวี | yes |
| pep | PEP (post-exposure prophylaxis) | เป๊ป ยาป้องกันหลังสัมผัสเชื้อเอชไอวี | yes |
| condoms_lubricants | Condoms and lubricant | ถุงยางอนามัยและสารหล่อลื่น | yes |
| referral | Referral to sexual health or mental health services | ส่งต่อบริการสุขภาพทางเพศหรือสุขภาพจิต | yes |
| mental_health | Mental health support | สุขภาพจิตและการให้คำปรึกษา | yes |
| cervical_screening | Cervical cancer screening | ตรวจคัดกรองมะเร็งปากมดลูก | no |
| contraception_pregnancy | Contraception and pregnancy services | คุมกำเนิดและบริการด้านการตั้งครรภ์ | no |
| violence_support | Support after violence | ช่วยเหลือผู้ถูกกระทำความรุนแรง | no |
| legal_aid | Legal aid | ช่วยเหลือทางกฎหมาย | no |
| labour_rights | Labour rights | สิทธิแรงงาน | no |
| shelter | Shelter | ที่พักพิง | no |
| education_livelihood | Education and livelihood | การศึกษาและอาชีพ | no |
| migrant_support | Support for migrant workers | ช่วยเหลือแรงงานข้ามชาติ | no |
| harm_reduction | Harm reduction for people who use drugs | ลดอันตรายจากการใช้สารเสพติด | no |
| outreach | Outreach | งานเข้าถึงชุมชนเชิงรุก | no |

## Safety rules

The dataset records only contact details that organisations publish themselves. A street address is recorded only when the organisation publishes the address, and the address of a shelter or safe house is never recorded, even when published. The dataset excludes the names of staff, volunteers and clients, and records location at province and district level with no map coordinates.

## Variables in health_and_help_sites.csv

Tables 2 to 9 describe the variables in `health_and_help_sites.csv` in the order of the columns. Cells with several values separate the values with a semicolon and a space, as in `hiv_testing; prep`. Identifiers are assigned once and are never reused, so that a site keeps the same `site_id` across monthly updates.

Table 2 shows that each row is identified at two levels, the organisation and the site.

**Table 2. Identity**

| Variable | Type | Values | Description |
|---|---|---|---|
| org_id | text | O followed by eight characters | Identifier of the organisation, shared by all of its sites |
| site_id | text | org_id, a hyphen and six characters | Identifier of the site |
| name_en | text | | Name in English as the organisation writes it |
| name_th | text | | Name in Thai as the organisation writes it |
| name_my | text | | Name in Burmese, machine-translated unless the organisation publishes one |
| acronym | text | | Acronym the organisation uses, such as SWING |

Table 3 describes the organisation as a whole. The labels for each code are in `config/taxonomy.json`.

**Table 3. Organisation**

| Variable | Type | Values | Description |
|---|---|---|---|
| org_type | category | ngo, community_group, network, international, government, university, other | Type of organisation |
| level | category | international, national, provincial, local, grassroots | Level at which the organisation works |
| sex_worker_led | category | yes, no, unclear | yes when the organisation describes itself as led by sex workers |
| approach | category | rights_based, rescue_or_exit, not_stated | Approach to sex work as the organisation describes the approach |

Table 4 shows that every row has the country code TH and, unless the service is national, a province code.

**Table 4. Location**

| Variable | Type | Values | Description |
|---|---|---|---|
| country | text | TH | Country code under ISO 3166-1, always TH |
| province_code | text | TH-10 to TH-96 | Province code under ISO 3166-2, such as TH-10 for Bangkok, empty for a national service with no physical site |
| province_en | text | | Province name in English |
| province_th | text | | Province name in Thai |
| city | text | | District (amphoe) or town in English, when a source states one |
| region | category | North, Northeast, Central, East, West, South | Region in the six-region geographic system |
| address_public | text | | Street address as the organisation publishes it, under the safety rules above |
| coverage | category | site, provincial, national | site for a single location, provincial for outreach across one or more provinces, national for a service open to the whole country |
| provinces_served | list | province codes | Provinces covered when coverage is provincial |

Table 5 records whether the site meets the inclusion rule and, when the site fails the rule, why.

**Table 5. Inclusion**

| Variable | Type | Values | Description |
|---|---|---|---|
| serves_sex_workers | category | yes, no | yes when a source names sex workers as people the organisation serves |
| meets_inclusion | category | yes, no | yes when the site meets both conditions of the inclusion rule |
| exclusion_reason | category | sex_workers_not_named, no_core_service, for_profit_clinic, closed, outside_thailand, duplicate | Reason the site fails the rule, empty when meets_inclusion is yes |
| populations | list | codes in Table 10 | Groups the site serves, as named in the sources |

Table 6 describes what the site offers, how the services are delivered and in which languages.

**Table 6. Services**

| Variable | Type | Values | Description |
|---|---|---|---|
| service_types | list | codes in Table 1 | Services the site provides or refers people to |
| direct_service | category | yes, referral_only | yes when the site provides at least one core service itself, referral_only when the site only refers people to other providers |
| service_mode | list | in_person, outreach, mobile_clinic, online, phone | How the services are delivered |
| fee | category | free, low_cost, paid, not_stated | Cost to the user as a source states the cost |
| languages | list | th, en, my, shn, lo, km, zh | Languages in which the site serves people, namely Thai, English, Burmese, Shan, Lao, Khmer and Chinese |
| hours | text | | Opening hours as published |

Table 7 lists the contact variables. Each contact is copied from the organisation's own pages, and a contact found only on a third-party site is not recorded.

**Table 7. Contacts**

| Variable | Type | Values | Description |
|---|---|---|---|
| phone | list | | Phone numbers as published |
| line_id | text | | LINE ID or LINE link as published |
| email | text | | Email address as published |
| website | text | | Official website |
| facebook | text | | Official Facebook page |

Table 8 shows that each site has a short description in Thai, English and Burmese. Claude Sonnet 5.5 writes the English and Thai descriptions from the quoted passages only, and the Burmese description is a machine translation of the English one.

**Table 8. Descriptions**

| Variable | Type | Values | Description |
|---|---|---|---|
| services_summary_en | text | | Two sentences in plain English on what the site offers and to whom |
| services_summary_th | text | | The same description in Thai |
| services_summary_my | text | | The same description in Burmese, machine-translated and not yet checked by a Burmese speaker |

Table 9 records where each row comes from, whether a person has checked the row, and whether the site still operates.

**Table 9. Evidence and record status**

| Variable | Type | Values | Description |
|---|---|---|---|
| source_urls | list | | Pages that support the values in the row |
| verification | category | ai_extracted, human_checked | human_checked once a person has compared every value with its source passage |
| last_checked | date | YYYY-MM-DD | Date of the latest check of the sources |
| status | category | active, reduced, closed, unknown | active when the sources show recent activity, reduced when the sources report fewer services or shorter hours, closed when the sources report closure |
| found_in_round | list | 1, 2, 3 | Discovery rounds in which the site was found |

Table 10 lists the population codes used in `populations`.

**Table 10. Populations**

| Code | English | Thai |
|---|---|---|
| female_sex_workers | Female sex workers | พนักงานบริการหญิง |
| male_sex_workers | Male sex workers | พนักงานบริการชาย |
| transgender_sex_workers | Transgender sex workers | พนักงานบริการข้ามเพศ |
| migrant_sex_workers | Migrant sex workers | พนักงานบริการข้ามชาติ |
| young_people | Young people | เยาวชน |
| men_who_have_sex_with_men | Men who have sex with men | ชายที่มีเพศสัมพันธ์กับชาย |
| transgender_people | Transgender people | คนข้ามเพศ |
| people_living_with_hiv | People living with HIV | ผู้อยู่ร่วมกับเชื้อเอชไอวี |
| people_who_use_drugs | People who use drugs | ผู้ใช้สารเสพติด |
| general_public | General public | ประชาชนทั่วไป |

## Variables in evidence.csv

Table 11 describes `evidence.csv`. Each row links one value in `health_and_help_sites.csv` to the page and passage that support the value, so that every value can be traced to its source.

**Table 11. Evidence**

| Variable | Type | Values | Description |
|---|---|---|---|
| site_id | text | | Site the value belongs to |
| variable | text | | Name of the variable in health_and_help_sites.csv |
| value | text | | The value as recorded in health_and_help_sites.csv |
| source_url | text | | Page the passage comes from |
| quote | text | | Passage copied word for word from the page, in its original language |
| quote_language | category | th, en, my, other | Language of the passage |
| retrieved_at | date and time | YYYY-MM-DDThh:mm:ssZ | Time the page was downloaded, in UTC |
| quote_found | category | yes, no | yes when the passage appears word for word in the stored copy of the page |

## Variables in health_and_help_candidates.csv

The prototype website publishes the file `health_and_help_candidates.csv`, which has one row for each candidate site that the web search found, including candidates that fail the inclusion rule. The file also records the result of the source check for each candidate. In the source check, a script with no AI downloads each evidence page and searches the page for the passage that the model copied. A passage counts as found when at least 90 percent of its overlapping pieces of eight characters appear on the page, with spacing, punctuation and case ignored. Cells with several values separate the values with a semicolon and a space, except `evidence_quotes`, which separates the passages with a vertical bar between two spaces. Table 12 describes the variables in the order of the columns, and the service codes are those in Table 1.

**Table 12. Candidate sites**

| Variable | Type | Values | Description |
|---|---|---|---|
| org_id | text | O followed by eight characters | Identifier of the organisation, shared by all sites of the organisation |
| site_id | text | org_id, a hyphen and six characters | Identifier of the site |
| name_en | text | | Name in English as the organisation writes the name |
| name_th | text | | Name in Thai as the organisation writes the name |
| acronym | text | | Acronym that the organisation uses, such as SWING |
| org_type | category | ngo, community_group, network, international, government, university, other | Type of organisation |
| level | category | international, national, provincial, local, grassroots | Level at which the organisation works |
| province_codes | text | ISO 3166-2:TH codes, or nationwide | Provinces of the site. The code nationwide marks a hotline or online service that serves the whole country |
| province_en | text | | English names of the provinces in the order of `province_codes`, or Nationwide |
| region | text | Central, East, North, Northeast, South, West, Nationwide | Regions of the provinces |
| city | text | | District (amphoe) or town in English, when a source states one |
| sex_worker_mention | category | yes, no, unclear | yes when a source names sex workers as people that the organisation serves |
| sex_worker_led | category | yes, no, unclear | yes when the organisation describes itself as led by sex workers |
| services_mentioned | text | codes in Table 1 | Services that the sources mention for the site |
| meets_inclusion | category | yes, no | yes when `sex_worker_mention` is yes and `services_mentioned` includes at least one core service |
| website | text | | Official website |
| facebook_or_line | text | | Official Facebook page, LINE URL or LINE ID |
| other_urls | text | URLs | Other official pages of the organisation, such as a branch page |
| partner_list_urls | text | URLs | Pages that list partner or member organisations |
| evidence_urls | text | URLs | Pages that the model cited as evidence for the candidate |
| evidence_quotes | text | passages | Passages that the model copied from the evidence pages, in the original language |
| quotes_found | text | k of n | Number of the site's passages that the source check found on their pages, of all passages recorded for the site |
| sex_work_terms_on_pages | text | terms | Terms for sex workers that the source check found on the evidence pages. The entry "พนักงานบริการ without a qualifier" marks the bare Thai term, which can also mean service staff in general |
| pages_not_read | text | URLs | Evidence pages that the source check could not read, including Facebook, LINE and X pages that need a login |
| latest_activity_seen | text | YYYY or YYYY-MM | Most recent date of activity that the model saw on the sources |

## How records are produced

Claude Sonnet 5.5, with web search, first finds candidate organisations in three rounds. Round 1 searches the whole country by type of organisation in five jobs. Round 2 searches province by province, in 24 groups that cover all 77 provinces. Round 3 follows known organisations that the first two rounds missed, provinces with no findings, partner and member lists, and Facebook and LINE pages. Each candidate is recorded with the URL and a verbatim passage that support the candidate.

Each source page is then downloaded and stored with its retrieval date. Claude Sonnet 5.5 reads each stored page and fills the variables, giving a passage for each value. A script confirms that each passage appears word for word in the stored page and removes any value whose passage is not found. A person then reviews each site against its passages before `verification` changes to `human_checked`.

Each month, a script downloads every source page again and compares the page with the stored copy. Only pages that changed are read again by the model, and each changed value is listed for a person to approve before the dataset is updated. Facebook and LINE pages are checked by a person, because those platforms restrict automated access.

## Missing values

An empty cell means that the sources do not state the value. For `fee` and `approach` the code `not_stated`, and for `status` the code `unknown`, mark the same absence. A value is never inferred from the type or location of an organisation.
