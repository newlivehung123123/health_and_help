/* Health & Help finder. Reads data/sites.json, which scripts/build_site_data.py builds,
   and renders the filters, the map, list and grid views, the profiles, the province board and the method panels. */
(() => {
  "use strict";

  const BATCH = 30;                 // results shown per step in the list and grid views
  const GAP = 18;                   // hover card offset from the pointer
  const EDGE = 8;                   // minimum distance from the viewport edge
  const THAILAND = [[5.6, 97.3], [20.5, 105.7]];
  const BOUNDS = [[3, 95], [23, 108.5]];
  const REGIONS = ["North", "Northeast", "Central", "East", "West", "South"];
  const EVIDENCE = ["included", "named", "all"];
  const SITE_RANK = { included: 0, unconfirmed: 1, unclear: 2 };
  const PROV_RANK = { covered: 0, unclear: 1, gap: 2 };
  const WIDE = matchMedia("(min-width: 900px)");
  const FINE = matchMedia("(hover: hover) and (pointer: fine)");
  const RAIL = matchMedia("(min-width: 821px)");
  const CALM = matchMedia("(prefers-reduced-motion: reduce)");
  const TH_RE = /[฀-๿]/;
  const TH_RUN = /[฀-๿]+/g;
  const STEMS = { prostitut: 1 };   // terms the source check matched as word stems
  // Esri Dark Gray Canvas needs no API key; CARTO basemaps now return a watermark without one.
  const TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_";
  const ATTR = 'Tiles &copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors and the GIS user community';
  const PATH = { close: "M4 4l8 8M12 4l-8 8", back: "M10 3.5 5.5 8l4.5 4.5", check: "M4 8.5l2.5 2.5L12 5.5", dash: "M4.5 8h7" };
  const FOCUSABLE = 'a[href], button:not([disabled]), input, select, [tabindex]:not([tabindex="-1"])';

  // English for the static page is read from index.html at start-up; these are the strings the script builds.
  const STR = {
    en: {
      u_updated: "Data updated {date}",
      all: "All",
      all_services: "All services",
      core_services: "Core health services",
      other_services: "Other services",
      ev_included: "Meets the rule",
      ev_named: "Names sex workers",
      ev_all: "All candidates",
      filters: "Filters",
      filters_n: "Filters ({n})",
      count: "Showing {n} of {total} sites",
      count_prov: "Showing {n} sites in {province}",
      count_prov_1: "Showing {n} site in {province}",
      count_nw: ", including {k} nationwide",
      clear_prov: "Clear {province}",
      empty: "No site matches these filters.",
      reset: "Reset filters",
      show_all_n: "Show all candidates ({k})",
      show_here: "Show every site here",
      more: "Show more · {n} remaining",
      st_covered: "Covered",
      st_unclear: "Unclear",
      st_gap: "Gap",
      n_sites: "{n} sites",
      n_sites_1: "{n} site",
      of: "{k} of {n}",
      hc_match: "Matching the filters",
      hc_gap: "The search found no candidate in this province. A province without a record may still have services that the search did not find.",
      hc_unclear: "No source here clearly names sex workers.",
      hc_hint: "Click the pin to list the organisations",
      pin_aria: "{province}, {status}, {m} of {n} sites match the filters",
      pin_gap: "{province}, no candidate yet",
      map_offline: "The map needs an internet connection. The list and grid views work without one.",
      thailand: "Thailand",
      panel_summary: "{local} sites in {p} provinces and {k} available nationwide match the filters. Click a pin to list the organisations in that province.",
      top_provinces: "Provinces with the most matching sites",
      nw_title: "Available nationwide",
      nw_also: "Also available nationwide",
      nw_none: "No nationwide service matches the filters.",
      hidden_n: "{h} more sites here are hidden by the filters",
      hidden_n_1: "{h} more site here is hidden by the filters",
      none_here: "No site here matches the filters.",
      to_list: "Show these in the list",
      back_to: "Back to {place}",
      close: "Close",
      st_included: "Meets the rule",
      st_unconfirmed: "Names sex workers, no core service recorded",
      st_unclear_src: "Source unclear",
      st_led: "Led by sex workers",
      short_included: "Meets the rule",
      short_unconfirmed: "Names sex workers",
      short_unclear: "Source unclear",
      nationwide: "Nationwide",
      plus_n: "+{n} more",
      no_services: "No service recorded yet.",
      no_services_short: "None recorded yet",
      evidence: "Evidence",
      ev_found_lbl: "Sentence found on the page",
      ev_notread: "Page could not be downloaded, so the sentence is unchecked",
      ev_social: "Social media page requires a login, so the sentence is unchecked",
      ev_notfound: "Sentence not found on the page",
      terms_h: "Terms for sex workers on the source pages",
      terms_bare: "Only the term พนักงานบริการ appears, which can also mean service staff.",
      terms_none: "No term for sex workers was found on the pages that the script downloaded.",
      contact: "Contact",
      website: "Website",
      social: "Facebook or LINE",
      other_pages: "Other pages",
      no_contact: "No contact page recorded yet.",
      latest: "Latest activity seen {latest}",
      safety_note: "Contact details are those the organisation publishes. Check with the organisation before travelling.",
      ts_ngo: "NGO or foundation",
      ts_community_group: "Community group",
      ts_network: "Network",
      ts_international: "International",
      ts_government: "Government",
      ts_university: "University",
      ts_other: "Other",
      region_North: "North",
      region_Northeast: "Northeast",
      region_Central: "Central",
      region_East: "East",
      region_West: "West",
      region_South: "South",
      rs_North: "North",
      rs_Northeast: "Northeast",
      rs_Central: "Central",
      rs_East: "East",
      rs_West: "West",
      rs_South: "South",
      slat: "{covered} of {total} provinces with a source naming sex workers",
      pop_h: "What the evidence levels mean",
      pop_included: "A source names sex workers and the site offers at least one of nine core services, HIV and STI testing and treatment, PrEP, PEP, condoms and lubricant, referral and mental health support.",
      pop_named: "Adds {unconfirmed} sites whose source names sex workers but records no core service yet.",
      pop_all: "Adds {unclear} sites whose source does not clearly name sex workers.",
      pop_foot: "{bare} sites show only the term พนักงานบริการ, which can also mean service staff. A script found {found} of the {records} copied sentences on the cited web pages. The other {rest} sentences are on pages that could not be downloaded or that require a login.",
      gaps_h: "{gaps} of {provinces} provinces have no candidate yet",
      gaps_p: "{covered} provinces have a source naming sex workers and {unclearProv} have only candidates whose sources do not clearly name sex workers. A province without a record may still have services that the search did not find.",
      gaps_nw: "The {nw} services available nationwide are not counted in any province.",
      bl_covered: "Source names sex workers ({covered})",
      bl_unclear: "Source does not clearly name sex workers ({unclearProv})",
      bl_gap: "No candidate yet ({gaps})",
      p1_f: "{searches} searches · {sites} sites · {orgs} organisations · ${cost} of a ${credit} budget",
      p2_l1: "{found} sentences found on the page",
      p2_l2: "{notread} sentences on pages that could not be downloaded",
      p2_l3: "{social} sentences on social media pages that require a login",
      p2_f: "{records} copied sentences · {pages} web pages · {pagesRead} downloaded",
      p3_f: "{included} of {sites} sites meet the rule",
      dl1_p: "One row for each of the {sites} sites that the search found, in {ncols} columns.",
      foot_built: "Data built {date}",
      load_error: "The data file could not be loaded. Open the page through a web server.",
      lh_org: "Organisation",
      lh_where: "Province",
      lh_svc: "Services",
      lh_ev: "Evidence",
      s_hiv_testing: "HIV testing",
      s_sti_testing: "STI testing",
      s_sti_treatment: "STI treatment",
      s_hiv_treatment: "HIV treatment",
      s_prep: "PrEP",
      s_pep: "PEP",
      s_condoms_lubricants: "Condoms",
      s_referral: "Referral",
      s_mental_health: "Mental health",
      s_cervical_screening: "Cervical screening",
      s_contraception_pregnancy: "Contraception",
      s_violence_support: "Violence support",
      s_legal_aid: "Legal aid",
      s_labour_rights: "Labour rights",
      s_shelter: "Shelter",
      s_education_livelihood: "Education",
      s_migrant_support: "Migrant support",
      s_harm_reduction: "Harm reduction",
      s_outreach: "Outreach",
    },
    th: {
      skip: "ข้ามไปยังเนื้อหา",
      u_label: "ข้อมูลเปิด · ประเทศไทย",
      u_dataset: "ชุดข้อมูล",
      u_method: "วิธีการ",
      strap: "บริการสุขภาพทางเพศและสุขภาพจิต · ประเทศไทย",
      nav_aria: "เมนูหลัก",
      nav_find: "ค้นหาบริการ",
      nav_gaps: "ช่องว่างรายจังหวัด",
      nav_how: "วิธีการ",
      nav_data: "ชุดข้อมูล",
      nav_about: "เกี่ยวกับ",
      menu: "เมนู",
      hero_kicker: "ชุดข้อมูลเปิด · ต้นแบบ · ประเทศไทย",
      hero_h1: "บริการสุขภาพทางเพศและสุขภาพจิต <span class='soft'>สำหรับพนักงานบริการทางเพศในประเทศไทย</span>",
      hero_lede: "สุขภาพและความช่วยเหลือเป็นชุดข้อมูลเปิดขององค์กรในประเทศไทยที่ให้บริการสุขภาพทางเพศหรือสุขภาพจิต และมีหน้าเว็บขององค์กรเองหรือแหล่งข้อมูลที่เผยแพร่อื่น ๆ ระบุว่าพนักงานบริการทางเพศเป็นกลุ่มที่องค์กรให้บริการ โครงการของเราใช้โมเดลภาษาขนาดใหญ่เพียงครั้งเดียวเพื่อค้นหาบนเว็บ และบันทึกแต่ละองค์กรพร้อมประโยคที่คัดลอกจากหน้าเว็บเป็นหลักฐาน จากนั้นสคริปต์ที่ไม่ใช้ AI ตรวจว่าประโยคที่คัดลอกแต่ละประโยคปรากฏอยู่บนหน้าเว็บที่โมเดลอ้างอิงหรือไม่ โมเดลขนาดเล็กที่กำลังพัฒนาจะตอบคำถามแบบออฟไลน์บนโทรศัพท์ที่ผู้คนใช้อยู่แล้ว",
      cta_find: "ค้นหาบริการ",
      cta_csv: "ดาวน์โหลดข้อมูล (CSV)",
      find_k: "เครื่องมือค้นหา",
      find_h: "ค้นหาบริการ",
      find_sub: "หมุดแต่ละหมุดอยู่ที่ตัวเมืองของจังหวัด โปรดติดต่อองค์กรเพื่อสอบถามที่อยู่ของจุดบริการก่อนเดินทาง",
      search_aria: "ค้นหา",
      search_ph: "ค้นหาองค์กร จังหวัด หรือบริการ",
      service_aria: "บริการ",
      view_aria: "มุมมอง",
      view_map: "แผนที่",
      view_list: "รายการ",
      view_grid: "การ์ด",
      g_region: "ภาค",
      g_evidence: "หลักฐาน",
      info_aria: "ความหมายของระดับหลักฐาน",
      led: "นำโดยพนักงานบริการทางเพศ",
      map_aria: "แผนที่ประเทศไทย หมุดละหนึ่งจังหวัด",
      lg_covered: "แหล่งข้อมูลระบุถึงพนักงานบริการทางเพศ",
      lg_unclear: "แหล่งข้อมูลไม่ได้ระบุถึงพนักงานบริการทางเพศอย่างชัดเจน",
      lg_gap: "ยังไม่พบองค์กร",
      lg_hidden: "ซ่อนโดยตัวกรอง",
      lg_size: "ขนาดหมุดแสดงจำนวนจุดบริการที่ตรงกับตัวกรอง",
      gaps_k: "ความครอบคลุม",
      how_k: "วิธีการ",
      how_h: "ชุดข้อมูลสร้างขึ้นอย่างไร",
      dev: "กำลังพัฒนา",
      how_p: "โมเดลภาษาขนาดใหญ่ค้นหาบนเว็บเพียงครั้งเดียว ขั้นตอนต่อจากนั้นทั้งหมดใช้สคริปต์หรือโมเดลขนาดเล็กที่ไม่มีค่าใช้จ่ายต่อการใช้งาน",
      p_done: "เสร็จแล้ว",
      p1_v: "การค้นหาบนเว็บ",
      p1_t: "โมเดลขนาดใหญ่ค้นหาบนเว็บเพียงครั้งเดียว",
      p1_p: "Claude Sonnet 5.5 ค้นหาบนเว็บสามรอบ และบันทึกแต่ละองค์กรพร้อมประโยคที่คัดลอกจากหน้าเว็บเป็นหลักฐาน",
      p1_l1: "รอบที่ 1 · รายภาค",
      p1_l2: "รอบที่ 2 · รายกลุ่มจังหวัด",
      p1_l3: "รอบที่ 3 · จังหวัดที่ยังไม่พบองค์กร",
      p1_go: "เปิดเครื่องมือค้นหา →",
      p2_v: "การตรวจแหล่งที่มา",
      p2_t: "สคริปต์ตรวจประโยคที่คัดลอกทุกประโยค",
      p2_p: "แต่ละรายการในชุดข้อมูลมีประโยคที่โมเดลขนาดใหญ่คัดลอกจากหน้าเว็บเป็นหลักฐานว่าองค์กรให้บริการพนักงานบริการทางเพศ สคริปต์ที่ไม่ใช้ AI ดาวน์โหลดหน้าเว็บเหล่านั้นทีละหน้าแล้วค้นหาประโยคที่คัดลอกบนหน้าเว็บ",
      p2_go: "ดาวน์โหลดผลการตรวจ →",
      p3_v: "เกณฑ์การคัดเลือก",
      p3_t: "เงื่อนไขสองข้อกำหนดว่าจุดบริการใดผ่านเกณฑ์",
      p3_p: "แหล่งข้อมูลที่เผยแพร่ระบุว่าพนักงานบริการทางเพศเป็นกลุ่มที่องค์กรให้บริการ และจุดบริการให้บริการหลักอย่างน้อยหนึ่งในเก้าบริการด้านล่าง ตัวเลขหลังแต่ละบริการคือจำนวนจุดบริการที่การค้นหาพบซึ่งให้บริการนั้น",
      p3_go: "ดูช่องว่างรายจังหวัด →",
      p4_v: "ความเป็นส่วนตัว",
      p4_s: "ใช้กับทุกรายการ",
      p4_t: "สิ่งที่ชุดข้อมูลไม่บันทึก",
      p4_p: "ชุดข้อมูลบันทึกเฉพาะช่องทางติดต่อที่องค์กรเผยแพร่เอง",
      p4_l1: "ไม่มีที่อยู่ของที่พักพิงหรือบ้านพักปลอดภัย",
      p4_l2: "ไม่มีชื่อของเจ้าหน้าที่ อาสาสมัคร หรือผู้รับบริการ",
      p4_l3: "ตำแหน่งระดับจังหวัดและอำเภอเท่านั้น",
      p4_l4: "หมุดอยู่ที่ตัวเมืองของจังหวัด",
      p4_f: "ไม่มีพิกัดบนแผนที่ · เฉพาะช่องทางติดต่อที่เผยแพร่",
      p5_v: "คำตอบแบบออฟไลน์",
      p5_t: "โมเดลขนาดเล็กจะตอบคำถามบนโทรศัพท์",
      p5_p: "ตัวจำแนกขนาดเล็กที่ทำงานในเบราว์เซอร์จะจับคู่คำถามกับรายการที่ตรวจสอบแล้ว และตอบจากรายการเหล่านั้นเท่านั้น โดยไม่ต้องใช้อินเทอร์เน็ต",
      p5_l1: "ภาษาไทย",
      p5_l2: "ภาษาอังกฤษ",
      p5_l3: "ภาษาพม่า",
      p5_l4: "เครื่องจำลอง SMS สำหรับโทรศัพท์พื้นฐาน",
      p5_f: "ไม่ต้องเชื่อมต่ออินเทอร์เน็ต · ไม่มีค่าใช้จ่ายต่อคำถาม",
      dl_k: "ดาวน์โหลด",
      dl_h: "นำข้อมูลฉบับเดือนตุลาคม 2026 ไปใช้",
      dl1_t: "รายชื่อจุดบริการ",
      dl1_m: "CSV · UTF-8",
      dl2_t: "คู่มือรหัสข้อมูล",
      dl2_p: "นิยามของทุกคอลัมน์ในไฟล์ CSV เกณฑ์การคัดเลือก และหมวดหมู่บริการ",
      dl2_m: "Markdown · เปิดในแท็บใหม่",
      foot_about: "สุขภาพและความช่วยเหลือเป็นต้นแบบที่ Jason Hung พัฒนาขึ้นสำหรับโจทย์ Small AI for Development ของ Hack-Nation Global AI Hackathon ครั้งที่ 7 เดือนตุลาคม 2026",
      foot_limits_h: "ข้อจำกัด",
      foot_l1: "จังหวัดที่ไม่มีรายการอาจยังมีบริการที่การค้นหาไม่พบ",
      foot_l3: "หมุดแสดงตำแหน่งตัวเมืองของจังหวัดโดยประมาณ",
      foot_l4: "บริการอาจเปลี่ยนแปลง โปรดติดต่อองค์กรก่อนเดินทาง",
      noscript: "เครื่องมือค้นหาต้องใช้ JavaScript แต่ยังดาวน์โหลดชุดข้อมูลได้ที่ data/health_and_help_candidates.csv",
      u_updated: "ปรับปรุงข้อมูล {date}",
      all: "ทั้งหมด",
      all_services: "ทุกบริการ",
      core_services: "บริการสุขภาพหลัก",
      other_services: "บริการอื่น ๆ",
      ev_included: "ตรงตามเกณฑ์",
      ev_named: "ระบุถึงพนักงานบริการทางเพศ",
      ev_all: "รายการทั้งหมด",
      filters: "ตัวกรอง",
      filters_n: "ตัวกรอง ({n})",
      count: "แสดง {n} จาก {total} จุดบริการ",
      count_prov: "แสดง {n} จุดบริการใน{province}",
      count_nw: " รวมบริการระดับประเทศ {k} แห่ง",
      clear_prov: "ล้างตัวกรอง {province}",
      empty: "ไม่พบจุดบริการที่ตรงกับตัวกรอง",
      reset: "ล้างตัวกรอง",
      show_all_n: "แสดงรายการทั้งหมด ({k})",
      show_here: "แสดงทุกจุดบริการในจังหวัดนี้",
      more: "แสดงเพิ่ม · เหลืออีก {n} รายการ",
      st_covered: "ครอบคลุม",
      st_unclear: "ไม่ชัดเจน",
      st_gap: "ช่องว่าง",
      n_sites: "{n} จุดบริการ",
      of: "{k} จาก {n}",
      hc_match: "ตรงกับตัวกรอง",
      hc_gap: "การค้นหายังไม่พบองค์กรในจังหวัดนี้ จังหวัดที่ไม่มีรายการอาจยังมีบริการที่การค้นหาไม่พบ",
      hc_unclear: "ไม่มีแหล่งข้อมูลในจังหวัดนี้ที่ระบุถึงพนักงานบริการทางเพศอย่างชัดเจน",
      hc_hint: "คลิกหมุดเพื่อดูรายชื่อองค์กร",
      pin_aria: "{province} {status} ตรงกับตัวกรอง {m} จาก {n} จุดบริการ",
      pin_gap: "{province} ยังไม่พบองค์กร",
      map_offline: "แผนที่ต้องใช้อินเทอร์เน็ต มุมมองรายการและการ์ดใช้งานได้โดยไม่ต้องเชื่อมต่อ",
      thailand: "ประเทศไทย",
      panel_summary: "จุดบริการ {local} แห่งใน {p} จังหวัด และบริการระดับประเทศ {k} แห่งตรงกับตัวกรอง คลิกหมุดเพื่อดูรายชื่อองค์กรในจังหวัดนั้น",
      top_provinces: "จังหวัดที่มีจุดบริการตรงกับตัวกรองมากที่สุด",
      nw_title: "ให้บริการทั่วประเทศ",
      nw_also: "ให้บริการทั่วประเทศด้วย",
      nw_none: "ไม่มีบริการระดับประเทศที่ตรงกับตัวกรอง",
      hidden_n: "มีอีก {h} จุดบริการในจังหวัดนี้ที่ถูกซ่อนโดยตัวกรอง",
      none_here: "ไม่มีจุดบริการในจังหวัดนี้ที่ตรงกับตัวกรอง",
      to_list: "แสดงในมุมมองรายการ",
      back_to: "กลับไปที่{place}",
      close: "ปิด",
      st_included: "ตรงตามเกณฑ์",
      st_unconfirmed: "ระบุถึงพนักงานบริการทางเพศ ยังไม่พบบริการหลัก",
      st_unclear_src: "แหล่งข้อมูลไม่ชัดเจน",
      st_led: "นำโดยพนักงานบริการทางเพศ",
      short_included: "ตรงตามเกณฑ์",
      short_unconfirmed: "ระบุถึงพนักงานบริการทางเพศ",
      short_unclear: "แหล่งข้อมูลไม่ชัดเจน",
      nationwide: "ทั่วประเทศ",
      plus_n: "+{n} จังหวัด",
      no_services: "ยังไม่มีข้อมูลบริการ",
      no_services_short: "ยังไม่มีข้อมูล",
      evidence: "หลักฐาน",
      ev_found_lbl: "พบประโยคนี้บนหน้าแหล่งที่มา",
      ev_notread: "ดาวน์โหลดหน้าเว็บไม่ได้ จึงยังไม่ได้ตรวจสอบประโยคนี้",
      ev_social: "หน้าโซเชียลมีเดียต้องเข้าสู่ระบบ จึงยังไม่ได้ตรวจสอบประโยคนี้",
      ev_notfound: "ไม่พบประโยคนี้บนหน้าแหล่งที่มา",
      terms_h: "คำที่ใช้เรียกพนักงานบริการทางเพศบนหน้าแหล่งที่มา",
      terms_bare: "พบเพียงคำว่า พนักงานบริการ ซึ่งอาจหมายถึงพนักงานในธุรกิจบริการทั่วไป",
      terms_none: "ไม่พบคำดังกล่าวบนหน้าเว็บที่ตรวจสอบได้",
      contact: "ช่องทางติดต่อ",
      website: "เว็บไซต์",
      social: "Facebook หรือ LINE",
      other_pages: "หน้าอื่น ๆ",
      no_contact: "ยังไม่มีข้อมูลช่องทางติดต่อ",
      latest: "กิจกรรมล่าสุดที่พบ {latest}",
      safety_note: "ช่องทางติดต่อเป็นข้อมูลที่องค์กรเผยแพร่เอง โปรดติดต่อองค์กรก่อนเดินทาง",
      ts_ngo: "มูลนิธิหรือเอ็นจีโอ",
      ts_community_group: "กลุ่มชุมชน",
      ts_network: "เครือข่าย",
      ts_international: "องค์กรระหว่างประเทศ",
      ts_government: "หน่วยงานรัฐ",
      ts_university: "มหาวิทยาลัย",
      ts_other: "อื่น ๆ",
      region_North: "ภาคเหนือ",
      region_Northeast: "ภาคตะวันออกเฉียงเหนือ",
      region_Central: "ภาคกลาง",
      region_East: "ภาคตะวันออก",
      region_West: "ภาคตะวันตก",
      region_South: "ภาคใต้",
      rs_North: "เหนือ",
      rs_Northeast: "อีสาน",
      rs_Central: "กลาง",
      rs_East: "ตะวันออก",
      rs_West: "ตะวันตก",
      rs_South: "ใต้",
      slat: "{covered} จาก {total} จังหวัดมีแหล่งข้อมูลระบุถึงพนักงานบริการทางเพศ",
      pop_h: "ความหมายของระดับหลักฐาน",
      pop_included: "มีแหล่งข้อมูลระบุถึงพนักงานบริการทางเพศ และจุดบริการให้บริการหลักอย่างน้อยหนึ่งในเก้าบริการ ได้แก่ การตรวจและรักษาเอชไอวีและโรคติดต่อทางเพศสัมพันธ์ เพร็พ เป๊ป ถุงยางอนามัยและสารหล่อลื่น การส่งต่อ และการดูแลสุขภาพจิต",
      pop_named: "เพิ่มอีก {unconfirmed} จุดบริการที่แหล่งข้อมูลระบุถึงพนักงานบริการทางเพศ แต่ยังไม่พบบริการหลัก",
      pop_all: "เพิ่มอีก {unclear} จุดบริการที่แหล่งข้อมูลไม่ได้ระบุถึงพนักงานบริการทางเพศอย่างชัดเจน",
      pop_foot: "มี {bare} จุดบริการที่ใช้เพียงคำว่า พนักงานบริการ ซึ่งอาจหมายถึงพนักงานในธุรกิจบริการทั่วไป สคริปต์พบประโยคที่คัดลอก {found} จาก {records} ประโยคบนหน้าเว็บที่อ้างอิง ส่วนอีก {rest} ประโยคอยู่บนหน้าที่ดาวน์โหลดไม่ได้หรือต้องเข้าสู่ระบบ",
      gaps_h: "{gaps} จาก {provinces} จังหวัดยังไม่พบองค์กร",
      gaps_p: "{covered} จังหวัดมีแหล่งข้อมูลระบุถึงพนักงานบริการทางเพศ และ {unclearProv} จังหวัดมีเพียงองค์กรที่แหล่งข้อมูลไม่ได้ระบุถึงพนักงานบริการทางเพศอย่างชัดเจน จังหวัดที่ไม่มีรายการอาจยังมีบริการที่การค้นหาไม่พบ",
      gaps_nw: "บริการระดับประเทศ {nw} แห่งไม่ถูกนับรวมในจังหวัดใด",
      bl_covered: "แหล่งข้อมูลระบุถึงพนักงานบริการทางเพศ ({covered})",
      bl_unclear: "แหล่งข้อมูลไม่ชัดเจน ({unclearProv})",
      bl_gap: "ยังไม่พบองค์กร ({gaps})",
      p1_f: "ค้นหา {searches} ครั้ง · {sites} จุดบริการ · {orgs} องค์กร · ${cost} จากงบประมาณ ${credit}",
      p2_l1: "พบบนหน้าเว็บ {found} ประโยค",
      p2_l2: "อยู่บนหน้าที่ดาวน์โหลดไม่ได้ {notread} ประโยค",
      p2_l3: "อยู่บนหน้าโซเชียลมีเดียที่ต้องเข้าสู่ระบบ {social} ประโยค",
      p2_f: "ประโยคที่คัดลอก {records} ประโยค · หน้าเว็บ {pages} หน้า · ดาวน์โหลดได้ {pagesRead} หน้า",
      p3_f: "{included} จาก {sites} จุดบริการตรงตามเกณฑ์",
      dl1_p: "หนึ่งแถวต่อหนึ่งจุดบริการที่การค้นหาพบ รวม {sites} จุดบริการใน {ncols} คอลัมน์",
      foot_built: "สร้างข้อมูลเมื่อ {date}",
      load_error: "โหลดไฟล์ข้อมูลไม่ได้ โปรดเปิดหน้านี้ผ่านเว็บเซิร์ฟเวอร์",
      lh_org: "องค์กร",
      lh_where: "จังหวัด",
      lh_svc: "บริการ",
      lh_ev: "หลักฐาน",
      s_hiv_testing: "ตรวจเอชไอวี",
      s_sti_testing: "ตรวจโรคติดต่อทางเพศ",
      s_sti_treatment: "รักษาโรคติดต่อทางเพศ",
      s_hiv_treatment: "ยาต้านไวรัส",
      s_prep: "เพร็พ",
      s_pep: "เป๊ป",
      s_condoms_lubricants: "ถุงยางอนามัย",
      s_referral: "ส่งต่อบริการ",
      s_mental_health: "สุขภาพจิต",
      s_cervical_screening: "คัดกรองมะเร็งปากมดลูก",
      s_contraception_pregnancy: "คุมกำเนิด",
      s_violence_support: "ช่วยเหลือหลังความรุนแรง",
      s_legal_aid: "ช่วยเหลือทางกฎหมาย",
      s_labour_rights: "สิทธิแรงงาน",
      s_shelter: "ที่พักพิง",
      s_education_livelihood: "การศึกษาและอาชีพ",
      s_migrant_support: "แรงงานข้ามชาติ",
      s_harm_reduction: "ลดอันตราย",
      s_outreach: "งานเชิงรุก",
    },
  };

  const state = { lang: "en", view: "map", q: "", service: "", region: "", evidence: "included", led: false, province: "", shown: BATCH, panel: null };
  let DATA = null, V = {}, PROV = {}, SITE = {}, SVC = {}, ORDER = {}, MAXN = 1;
  let map = null;                   // null before the first map view, false when Leaflet did not load
  const markers = {}, iconKey = {};
  let sheet = null;                 // {code, site} while the profile sheet is open
  let sheetReturn = null, panelKey = "", tiltCard = null, collator = null, qTimer = 0;

  /* ---------- helpers ---------- */

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const ico = (d) => `<svg class="ico" viewBox="0 0 16 16" aria-hidden="true"><path d="${d}"/></svg>`;
  const smooth = () => (CALM.matches ? "auto" : "smooth");
  const isTh = () => state.lang === "th";

  const tpl = (key) => {
    const own = STR[state.lang];
    if (own && key in own) return own[key];
    return key in STR.en ? STR.en[key] : key;
  };
  // Plain text: {name} comes from vars, then from the dataset figures in V.
  const t = (key, vars) => tpl(key).replace(/\{(\w+)\}/g, (m, k) =>
    vars && k in vars ? String(vars[k]) : k in V ? String(V[k]) : m);
  // HTML: the template is escaped and vars are inserted as given.
  const T = (key, vars) => esc(tpl(key)).replace(/\{(\w+)\}/g, (m, k) =>
    vars && k in vars ? String(vars[k]) : k in V ? esc(V[k]) : m);
  const pick = (key, n) => (n === 1 && (key + "_1") in (STR[state.lang] || {}) ? key + "_1" : key);
  const langOf = (s) => (TH_RE.test(s) ? "th" : "en");
  // Thai words inside English text get their own lang so screen readers switch voice.
  const markTh = (html) => (isTh() ? html : html.replace(TH_RUN, (w) => `<span lang="th">${w}</span>`));
  const coll = () => collator || (collator = new Intl.Collator(isTh() ? "th" : "en", { sensitivity: "base", numeric: true }));

  const siteName = (s) => (isTh() && s.name_th) || s.name_en || s.name_th;
  const siteOther = (s) => {
    const o = isTh() ? s.name_en : s.name_th;
    return o && o !== siteName(s) ? o : "";
  };
  const pname = (code) => (PROV[code] ? (isTh() ? PROV[code].name_th : PROV[code].name_en) : code);
  const pother = (code) => (PROV[code] ? (isTh() ? PROV[code].name_en : PROV[code].name_th) : "");
  const regionName = (r) => t("region_" + r);
  const regionShort = (r) => t("rs_" + r);
  const fromTable = (table, k) => {
    const o = DATA[table][k];
    return o ? (isTh() ? o.th : o.en) : k;
  };
  const typeName = (k) => fromTable("org_types", k);
  const typeShort = (k) => (("ts_" + k) in STR.en ? t("ts_" + k) : typeName(k));
  const levelName = (k) => fromTable("levels", k);
  const svcName = (id) => (SVC[id] ? (isTh() ? SVC[id].th : SVC[id].en) : id);
  const svcShort = (id) => (("s_" + id) in STR.en ? t("s_" + id) : svcName(id));
  const isCore = (id) => Boolean(SVC[id] && SVC[id].core);
  const nSites = (n) => t(pick("n_sites", n), { n });
  const homeTitle = () => (state.region ? regionName(state.region) : t("thailand"));
  const cityText = (s) => (s.city && !s.provinces.some((c) => PROV[c] && PROV[c].name_en.toLowerCase() === s.city.toLowerCase()) ? s.city : "");
  const whereText = (s) => (s.nationwide ? t("nationwide")
    : s.provinces.slice(0, 3).map(pname).join(", ") + (s.provinces.length > 3 ? " " + t("plus_n", { n: s.provinces.length - 3 }) : ""));

  const safeUrl = (u) => {
    try {
      const x = new URL(u);
      return x.protocol === "https:" || x.protocol === "http:" ? x.href : "";
    } catch {
      return "";
    }
  };
  const clip = (s, max) => {
    let parts;
    try {
      parts = Array.from(new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(s), (g) => g.segment);
    } catch {
      parts = Array.from(s);
    }
    return parts.length > max ? parts.slice(0, max - 1).join("") + "…" : s;
  };
  const shortUrl = (u, max = 48) => {
    let s = u;
    try {
      const x = new URL(u);
      let path = x.pathname;
      try { path = decodeURIComponent(path); } catch { /* keep the encoded path */ }
      s = x.hostname.replace(/^www\./, "") + path.replace(/\/$/, "") + x.search;
    } catch { /* not a URL, show as given */ }
    return clip(s, max);
  };
  const trimSlash = (u) => u.replace(/\/+$/, "");
  const extLink = (u) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(shortUrl(u))}</a>`;

  const mb = (label, value, frac) => {
    const w = frac > 0 ? Math.max(4, Math.round(Math.min(1, frac) * 100)) : 0;
    return `<span class="mb"><span class="mb__row"><span>${esc(label)}</span><b>${esc(value)}</b></span>` +
      `<span class="mb__track"><span class="mb__fill" style="width:${w}%"></span></span></span>`;
  };

  const load = (k) => {
    try { return sessionStorage.getItem(k); } catch { return null; }
  };
  const save = (k, v) => {
    try { sessionStorage.setItem(k, v); } catch { /* storage blocked */ }
  };

  const statusBadge = (s, short) => {
    const key = short ? "short_" + s.status : s.status === "unclear" ? "st_unclear_src" : "st_" + s.status;
    return `<span class="badge badge--${s.status}">${esc(t(key))}</span>`;
  };
  const ledBadge = (s) => (s.led === "yes" ? `<span class="badge badge--led">${esc(t("st_led"))}</span>` : "");
  const chips = (s, max) => {
    const ids = s.services.filter(isCore).concat(s.services.filter((id) => !isCore(id)));
    if (!ids.length) return `<span class="chip chip--more">${esc(t("no_services_short"))}</span>`;
    return ids.slice(0, max).map((id) => `<span class="chip${isCore(id) ? " chip--core" : ""}">${esc(svcShort(id))}</span>`).join("") +
      (ids.length > max ? `<span class="chip chip--more">+${ids.length - max}</span>` : "");
  };
  const closeBtn = () => `<button class="x" type="button" data-act="close" aria-label="${esc(t("close"))}">${ico(PATH.close)}</button>`;

  /* ---------- filtering ---------- */

  const matches = (s, anyProvince, ev = state.evidence) => {
    if (ev === "included" && s.status !== "included") return false;
    if (ev === "named" && s.sw !== "yes") return false;
    if (state.led && s.led !== "yes") return false;
    if (state.service && !s.services.includes(state.service)) return false;
    if (state.region && !s.nationwide && !s.regions.includes(state.region)) return false;
    if (state.province && !anyProvince && !s.nationwide && !s.provinces.includes(state.province)) return false;
    if (state.q && !state.q.split(/\s+/).every((w) => s._hay.includes(w))) return false;
    return true;
  };
  const inProv = (s, code) => !s.nationwide && s.provinces.includes(code);
  // Sites that light a province pin. A site that spans regions lights only the provinces in the chosen region.
  const provMatches = (code) => (state.region && PROV[code].region !== state.region ? []
    : DATA.sites.filter((s) => inProv(s, code) && matches(s, true)));
  const sortSites = (list) => list.slice().sort((a, b) =>
    (state.province ? Number(a.nationwide) - Number(b.nationwide) : 0) ||
    SITE_RANK[a.status] - SITE_RANK[b.status] ||
    coll().compare(siteName(a), siteName(b)));

  /* ---------- start-up ---------- */

  const harvest = () => {
    const en = STR.en;
    const put = (k, v) => { if (k && !(k in en)) en[k] = v; };
    $$("[data-i18n]").forEach((el) => put(el.dataset.i18n, el.textContent.replace(/\s+/g, " ").trim()));
    $$("[data-i18n-html]").forEach((el) => put(el.dataset.i18nHtml, el.innerHTML.trim()));
    $$("[data-i18n-ph]").forEach((el) => put(el.dataset.i18nPh, el.getAttribute("placeholder") || ""));
    $$("[data-i18n-aria]").forEach((el) => put(el.dataset.i18nAria, el.getAttribute("aria-label") || ""));
  };

  const prepare = () => {
    DATA.provinces.forEach((p) => { PROV[p.code] = p; });
    DATA.services.forEach((s, i) => { SVC[s.id] = s; ORDER[s.id] = i; });
    MAXN = Math.max(1, ...DATA.provinces.map((p) => p.n));
    const th = STR.th, en = STR.en;
    DATA.sites.forEach((s) => {
      SITE[s.id] = s;
      const hay = [s.name_en, s.name_th, s.acronym, s.city];
      s.provinces.forEach((c) => { if (PROV[c]) hay.push(PROV[c].name_en, PROV[c].name_th); });
      s.regions.forEach((r) => hay.push(r, th["region_" + r], th["rs_" + r]));
      s.services.forEach((id) => {
        if (SVC[id]) hay.push(SVC[id].en, SVC[id].th);
        hay.push(en["s_" + id], th["s_" + id]);
      });
      const ty = DATA.org_types[s.type];
      if (ty) hay.push(ty.en, ty.th);
      hay.push(en["ts_" + s.type], th["ts_" + s.type]);
      if (s.nationwide) hay.push("nationwide ทั่วประเทศ");
      s._hay = hay.filter(Boolean).join(" ").toLowerCase();
    });
    const m = DATA.meta;
    const ev = DATA.sites.flatMap((s) => s.evidence);
    V = {
      sites: m.sites, orgs: m.orgs, included: m.included, named: m.named, unconfirmed: m.unconfirmed,
      unclear: m.unclear, led: m.led, nw: m.nationwide, provinces: m.provinces,
      covered: m.provinces_covered, with: m.provinces_with_candidate,
      unclearProv: m.provinces_with_candidate - m.provinces_covered,
      gaps: m.provinces - m.provinces_with_candidate,
      found: m.quotes_found, records: m.records, rest: m.records - m.quotes_found,
      notread: ev.filter((e) => e.page === "not read").length, social: ev.filter((e) => e.page === "social").length,
      pages: m.pages, pagesRead: m.pages_read,
      cost: m.search_cost.toFixed(2), credit: m.credit.toFixed(2), searches: m.searches,
      bare: DATA.sites.filter((s) => s.bare_term && !s.terms.length).length,
      ncols: DATA.columns.length, date: m.built,
    };
  };

  const applyLang = () => {
    document.documentElement.lang = state.lang;
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-html]").forEach((el) => { el.innerHTML = tpl(el.dataset.i18nHtml); });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    const btn = $(".lang");
    btn.textContent = isTh() ? "English" : "ไทย";
    btn.lang = isTh() ? "en" : "th";
    btn.setAttribute("aria-label", isTh() ? "Read in English" : "อ่านเป็นภาษาไทย");
    collator = null;
    const off = $(".map__offline");
    if (off) off.textContent = t("map_offline");
    closePop(false);
    if (!DATA) return;
    try {
      V.date = new Intl.DateTimeFormat(isTh() ? "th-TH" : "en-GB", { day: "numeric", month: "long", year: "numeric" })
        .format(new Date(DATA.meta.built + "T00:00:00"));
    } catch {
      V.date = DATA.meta.built;
    }
    $$("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
    const bold = {};
    Object.keys(V).forEach((k) => { bold[k] = `<b>${esc(V[k])}</b>`; });
    $$("[data-fig]").forEach((el) => { el.innerHTML = T(el.dataset.fig, bold); });
    fillCore();
    buildServiceSelect();
    renderFilters();
    renderBoard();
    render();
    renderSheet();
  };

  // The inclusion panel lists the nine core services with the number of candidate sites that offer each service.
  const fillCore = () => {
    $("#plate-core").innerHTML = DATA.services.filter((s) => s.core)
      .map((s) => `<li>${esc(svcShort(s.id))}<span class="tag">${s.n}</span></li>`).join("");
  };

  const buildServiceSelect = () => {
    const sel = $("#f-service");
    const used = DATA.services.filter((s) => s.n > 0);
    const opt = (s) => `<option value="${esc(s.id)}">${esc(svcShort(s.id))}</option>`;
    sel.innerHTML = `<option value="">${esc(t("all_services"))}</option>` +
      `<optgroup label="${esc(t("core_services"))}">${used.filter((s) => s.core).map(opt).join("")}</optgroup>` +
      `<optgroup label="${esc(t("other_services"))}">${used.filter((s) => !s.core).map(opt).join("")}</optgroup>`;
    sel.value = state.service;
  };

  const renderFilters = () => {
    const pill = (act, v, label, on, n) => `<button class="filter-btn" type="button" data-act="${act}" data-v="${esc(v)}" aria-pressed="${on}">` +
      `<span>${esc(label)}</span>${n == null ? "" : `<span class="n">${esc(n)}</span>`}</button>`;
    $("#f-region").innerHTML = ["", ...REGIONS].map((r) => pill("region", r, r ? regionShort(r) : t("all"), state.region === r)).join("");
    const counts = { included: V.included, named: V.named, all: V.sites };
    $("#f-evidence").innerHTML = EVIDENCE.map((e) => pill("evidence", e, t("ev_" + e), state.evidence === e, counts[e])).join("");
    $("#f-led").setAttribute("aria-pressed", String(state.led));
    $("#n-led").textContent = V.led;
    const n = [state.service, state.region, state.evidence !== "included", state.led].filter(Boolean).length;
    $("#fb-toggle-label").textContent = n ? t("filters_n", { n }) : t("filters");
  };

  /* ---------- rendering ---------- */

  const render = () => {
    if (!DATA) return;
    const list = sortSites(DATA.sites.filter((s) => matches(s, false)));
    renderCount(list);
    updatePins();
    if (state.view === "map") renderPanel();
    else renderResults(list);
  };

  const renderCount = (list) => {
    const n = list.length;
    const k = list.filter((s) => s.nationwide).length;
    const strong = `<strong>${n}</strong>`;
    let html = state.province
      ? T(pick("count_prov", n), { n: strong, province: esc(pname(state.province)) })
      : T("count", { n: strong, total: V.sites });
    if (k) html += T("count_nw", { k });
    let out = `<span>${html}</span>`;
    if (state.province) {
      const name = pname(state.province);
      out += `<button class="xchip" type="button" data-act="clear-province" aria-label="${esc(t("clear_prov", { province: name }))}">` +
        `${esc(name)}<span aria-hidden="true">✕</span></button>`;
    }
    $("#countline").innerHTML = out;
  };

  /* ---------- map ---------- */

  const initMap = () => {
    if (map !== null || !DATA) return;
    const box = $("#map");
    if (!window.L) {
      map = false;
      box.innerHTML = `<p class="map__offline">${esc(t("map_offline"))}</p>`;
      return;
    }
    map = L.map(box, {
      zoomSnap: 0.25, zoomDelta: 0.5, minZoom: 5, maxZoom: 10,
      maxBounds: BOUNDS, maxBoundsViscosity: 0.8, scrollWheelZoom: false,
    });
    L.tileLayer(TILES + "Base/MapServer/tile/{z}/{y}/{x}", { attribution: ATTR, maxNativeZoom: 13, className: "tiles-base" }).addTo(map);
    L.tileLayer(TILES + "Reference/MapServer/tile/{z}/{y}/{x}", { maxNativeZoom: 13, opacity: 0.7, zIndex: 2, className: "tiles-ref" }).addTo(map);
    fitTo(state.region, false);
    for (const p of DATA.provinces) {
      const mk = L.marker([p.lat, p.lon], {
        keyboard: p.n > 0, riseOnHover: true,
        icon: L.divIcon({ className: "pin", html: "", iconSize: [8, 8] }),
      }).addTo(map);
      const el = mk.getElement();
      mk.on("click", () => pickProvince(p.code, el));
      mk.on("mouseover", (e) => showHover(p.code, e.originalEvent));
      mk.on("mousemove", (e) => placeHover(e.originalEvent));
      mk.on("mouseout", hideHover);
      if (p.n) {
        // Leaflet 1.9 makes markers focusable but does not turn Enter or Space into a click.
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickProvince(p.code, el); }
        });
      } else {
        el.setAttribute("aria-hidden", "true");
      }
      markers[p.code] = mk;
    }
    map.on("focus click", () => map.scrollWheelZoom.enable());
    box.addEventListener("mouseleave", () => map.scrollWheelZoom.disable());
    updatePins();
  };

  const fitTo = (region, animate) => {
    if (!map) return;
    const opts = { animate: animate !== false && !CALM.matches };
    if (region) {
      const pts = DATA.provinces.filter((p) => p.region === region).map((p) => [p.lat, p.lon]);
      map.fitBounds(L.latLngBounds(pts).pad(0.15), { ...opts, padding: [30, 30], maxZoom: 8 });
    } else {
      map.fitBounds(THAILAND, { ...opts, padding: [16, 16] });
    }
  };

  const updatePins = () => {
    if (!map) return;
    for (const p of DATA.provinces) {
      const mk = markers[p.code];
      const ms = provMatches(p.code);
      const m = ms.length;
      const kind = m ? (ms.some((s) => s.sw === "yes") ? "covered" : "unclear") : p.n ? "hidden" : "gap";
      const d = m ? Math.round(18 + 22 * Math.log(1 + m) / Math.log(1 + MAXN)) : kind === "hidden" ? 7 : 8;
      const pinned = state.province === p.code;
      const key = `${kind}|${m}|${d}|${pinned}`;
      if (iconKey[p.code] !== key) {
        iconKey[p.code] = key;
        mk.setIcon(L.divIcon({
          className: "pin" + (pinned ? " is-pinned" : ""),
          html: `<span class="bead bead--${kind}">${m || ""}</span>`,
          iconSize: [d, d],
        }));
        const base = { covered: 30000, unclear: 20000, hidden: 10000, gap: 0 }[kind];
        mk.setZIndexOffset(base + (m ? (60 - d) * 100 : 0) + (pinned ? 40000 : 0));
      }
      const el = mk.getElement();
      if (el) {
        el.setAttribute("aria-label", p.n
          ? t("pin_aria", { province: pname(p.code), status: t("st_" + p.status), m, n: p.n })
          : t("pin_gap", { province: pname(p.code) }));
      }
    }
  };

  const pickProvince = (code, opener) => {
    const p = PROV[code];
    if (!p) return;
    if (state.region && p.region !== state.region) {
      state.region = "";
      renderFilters();
    }
    state.province = code;
    state.panel = null;
    state.shown = BATCH;
    hideHover();
    if (map) map.setView([p.lat, p.lon], Math.max(map.getZoom(), 7), { animate: !CALM.matches });
    render();
    if (!WIDE.matches) openSheet({ code, site: "" }, opener);
  };

  const setView = () => {
    $$('.tab[data-act="view"]').forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === state.view)));
    $("#view-map").hidden = state.view !== "map";
    $("#view-list").hidden = state.view !== "list";
    $("#view-grid").hidden = state.view !== "grid";
    if (state.view === "map") {
      if (map === null) initMap();
      else if (map) map.invalidateSize();
    }
    save("hh_view", state.view);
    hideHover();
  };

  /* ---------- hover card ---------- */

  const showHover = (code, ev) => {
    if (!FINE.matches || !ev || sheet) return;
    const p = PROV[code];
    const card = $("#hovercard");
    const m = provMatches(code).length;
    let html = `<div class="hc__top"><div><p class="hc__name">${esc(pname(code))}</p>` +
      `<p class="hc__sub">${esc(regionName(p.region))} · ${esc(nSites(p.n))}</p></div>` +
      `<span class="badge badge--${p.status}">${esc(t("st_" + p.status))}</span></div>`;
    if (!p.n) {
      html += `<p class="hc__p">${esc(t("hc_gap"))}</p>`;
    } else {
      html += mb(t("hc_match"), t("of", { k: m, n: p.n }), m / p.n);
      const count = {};
      DATA.sites.filter((s) => inProv(s, code)).forEach((s) => s.services.forEach((id) => { count[id] = (count[id] || 0) + 1; }));
      const top = Object.entries(count).sort((a, b) => b[1] - a[1] || ORDER[a[0]] - ORDER[b[0]]).slice(0, 5);
      if (top.length) html += `<div class="hc__svc">${top.map(([id, c]) => mb(svcShort(id), String(c), c / p.n)).join("")}</div>`;
      if (p.status === "unclear") html += `<p class="hc__p">${esc(t("hc_unclear"))}</p>`;
      html += `<p class="hc__hint">${esc(t("hc_hint"))}</p>`;
    }
    card.innerHTML = html;
    card.classList.add("is-on");
    placeHover(ev);
  };

  const placeHover = (ev) => {
    const card = $("#hovercard");
    if (!ev || !card.classList.contains("is-on")) return;
    const w = card.offsetWidth, h = card.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    let x = ev.clientX + GAP, y = ev.clientY + GAP;
    if (x + w > vw - EDGE) x = ev.clientX - GAP - w;
    if (y + h > vh - EDGE) y = ev.clientY - GAP - h;
    card.style.left = Math.max(EDGE, Math.min(x, vw - w - EDGE)) + "px";
    card.style.top = Math.max(EDGE, Math.min(y, vh - h - EDGE)) + "px";
  };

  const hideHover = () => $("#hovercard").classList.remove("is-on");

  /* ---------- side panel ---------- */

  const renderPanel = () => {
    if (!DATA || !WIDE.matches || state.view !== "map") return;
    const panel = $("#panel");
    if (state.panel && SITE[state.panel]) panel.innerHTML = siteHTML(state.panel, { back: state.province ? pname(state.province) : homeTitle() });
    else if (state.province) panel.innerHTML = provHTML(state.province, false);
    else panel.innerHTML = homeHTML();
    const key = [state.lang, state.panel, state.province, state.region].join("|");
    if (key !== panelKey) {
      panel.scrollTop = 0;
      panelKey = key;
    }
  };

  const emptyActs = (cls) => {
    const k = state.evidence !== "all" ? DATA.sites.filter((s) => matches(s, false, "all")).length : 0;
    return `<div class="${cls}"><button class="btn btn--ghost" type="button" data-act="reset">${esc(t("reset"))}</button>` +
      (k ? `<button class="btn btn--primary" type="button" data-act="all">${esc(t("show_all_n", { k }))}</button>` : "") + "</div>";
  };

  const rowHTML = (s) => {
    const name = siteName(s);
    const meta = [typeShort(s.type), s.nationwide ? t("nationwide") : cityText(s)].filter(Boolean).join(" · ");
    return `<li><button class="srow" type="button" data-act="site" data-v="${esc(s.id)}">` +
      `<span class="srow__name" lang="${langOf(name)}">${esc(name)}</span>${statusBadge(s, true)}` +
      `<span class="srow__meta">${esc(meta)}</span><span class="srow__chips">${chips(s, 3)}</span></button></li>`;
  };

  const homeHTML = () => {
    const all = DATA.sites.filter((s) => matches(s, true));
    const nw = sortSites(all.filter((s) => s.nationwide));
    const tops = DATA.provinces.map((p) => [p.code, provMatches(p.code).length]).filter((x) => x[1] > 0)
      .sort((a, b) => b[1] - a[1] || coll().compare(pname(a[0]), pname(b[0])));
    let html = `<p class="pp__eyebrow">${esc(t("find_k"))}</p><h3 class="pp__title" tabindex="-1">${esc(homeTitle())}</h3>`;
    if (!all.length) return html + `<p class="pp__p">${esc(t("empty"))}</p>` + emptyActs("pp__acts");
    html += `<p class="pp__p">${esc(t("panel_summary", { local: all.length - nw.length, p: tops.length, k: nw.length }))}</p>`;
    if (tops.length) {
      const max = tops[0][1];
      html += `<h4 class="pp__h">${esc(t("top_provinces"))}</h4><ul class="tops">` + tops.slice(0, 6).map(([code, m]) =>
        `<li><button class="top" type="button" data-act="province" data-v="${code}">${mb(pname(code), nSites(m), m / max)}</button></li>`).join("") + "</ul>";
    }
    html += `<h4 class="pp__h">${esc(t("nw_title"))}</h4>` +
      (nw.length ? `<ul class="srows">${nw.map(rowHTML).join("")}</ul>` : `<p class="pp__p">${esc(t("nw_none"))}</p>`);
    return html;
  };

  const provHTML = (code, inSheet) => {
    const p = PROV[code];
    const ms = sortSites(provMatches(code));
    const hidden = p.n - ms.length;
    const nw = sortSites(DATA.sites.filter((s) => s.nationwide && matches(s, true)));
    const other = pother(code);
    let html = `<div class="pp__head"><div><p class="pp__eyebrow">${esc(regionName(p.region))}</p>` +
      `<h3 class="pp__title"${inSheet ? ' id="sheet-title"' : ""} tabindex="-1">${esc(pname(code))}</h3>` +
      `<p class="pp__sub">${other ? `<span lang="${langOf(other)}">${esc(other)}</span> · ` : ""}${esc(nSites(p.n))}</p></div>${closeBtn()}</div>` +
      `<div class="pp__badges"><span class="badge badge--${p.status}">${esc(t("st_" + p.status))}</span></div>`;
    if (!p.n) {
      html += `<p class="pp__p">${esc(t("hc_gap"))}</p>`;
    } else {
      html += `<h4 class="pp__h">${esc(t("hc_match"))}</h4>` +
        (ms.length ? `<ul class="srows">${ms.map(rowHTML).join("")}</ul>` : `<p class="pp__p">${esc(t("none_here"))}</p>`);
      if (hidden > 0) html += `<p class="pp__p">${esc(t(pick("hidden_n", hidden), { h: hidden }))}</p>`;
    }
    if (nw.length) html += `<h4 class="pp__h">${esc(t("nw_also"))}</h4><ul class="srows">${nw.map(rowHTML).join("")}</ul>`;
    const acts = (hidden > 0 ? `<button class="btn btn--ghost" type="button" data-act="show-here">${esc(t("show_here"))}</button>` : "") +
      (ms.length ? `<button class="btn btn--primary" type="button" data-act="to-list">${esc(t("to_list"))}</button>` : "");
    if (acts) html += `<div class="pp__acts">${acts}</div>`;
    return html;
  };

  /* ---------- profile ---------- */

  const siteHTML = (id, opts) => {
    const s = SITE[id];
    const name = siteName(s);
    const other = siteOther(s);
    const lower = name.toLowerCase();
    const acr = s.acronym && !s.acronym.split("/").some((a) => lower.includes(a.trim().toLowerCase())) ? s.acronym : "";
    const meta = [levelName(s.level), whereText(s), cityText(s)].filter(Boolean).join(" · ");
    const head = opts.back
      ? `<button class="back" type="button" data-act="back">${ico(PATH.back)}<span>${esc(t("back_to", { place: opts.back }))}</span></button>`
      : "<span></span>";
    let html = `<div class="pp__head">${head}${opts.sheet ? closeBtn() : ""}</div>` +
      `<p class="pp__eyebrow">${esc(typeName(s.type))}</p>` +
      `<h3 class="prof__title"${opts.sheet ? ' id="sheet-title"' : ""} lang="${langOf(name)}">${esc(name)}` +
      (acr ? `<span class="acr" lang="${langOf(acr)}">${esc(acr)}</span>` : "") + "</h3>" +
      (other ? `<p class="prof__other" lang="${langOf(other)}">${esc(other)}</p>` : "") +
      `<p class="prof__meta">${esc(meta)}</p>` +
      `<div class="pp__badges">${statusBadge(s, false)}${ledBadge(s)}` +
      (s.nationwide ? `<span class="badge badge--nw">${esc(t("nationwide"))}</span>` : "") + "</div>";

    const core = s.services.filter(isCore), rest = s.services.filter((x) => !isCore(x));
    const list = (ids, cls) => `<ul class="svcs">${ids.map((x) => `<li class="${cls}">${esc(svcName(x))}</li>`).join("")}</ul>`;
    if (core.length) html += `<h4 class="pp__h">${esc(t("core_services"))}</h4>` + list(core, "chip chip--core");
    if (rest.length) html += `<h4 class="pp__h">${esc(t("other_services"))}</h4>` + list(rest, "chip");
    if (!core.length && !rest.length) html += `<h4 class="pp__h">${esc(t("lh_svc"))}</h4><p class="pp__p">${esc(t("no_services"))}</p>`;

    html += `<h4 class="pp__h">${esc(t("evidence"))}</h4>` + s.evidence.map((e) => {
      const url = safeUrl(e.url);
      const found = e.check === "found";
      const label = found ? "ev_found_lbl" : e.page === "social" ? "ev_social" : e.page === "not read" ? "ev_notread" : "ev_notfound";
      return `<blockquote class="quote"${url ? ` cite="${esc(url)}"` : ""}><p lang="${langOf(e.quote)}">${esc(e.quote)}</p>` +
        `<footer><span class="check check--${found ? "found" : "open"}">${ico(found ? PATH.check : PATH.dash)}<span>${esc(t(label))}</span></span>` +
        (url ? extLink(url) : "") + "</footer></blockquote>";
    }).join("");

    html += `<h4 class="pp__h">${esc(t("terms_h"))}</h4>`;
    if (s.terms.length) {
      html += `<div class="terms">${s.terms.map((w) => `<span class="chip" lang="${langOf(w)}">${esc(w)}${STEMS[w] ? "…" : ""}</span>`).join("")}</div>`;
    } else {
      html += `<p class="pp__p">${markTh(esc(t(s.bare_term ? "terms_bare" : "terms_none")))}</p>`;
    }

    const rows = [];
    const web = safeUrl(s.website);
    if (web) rows.push([t("website"), extLink(web)]);
    if (s.social) {
      const su = safeUrl(s.social);
      rows.push([t("social"), su ? extLink(su) : `<bdi>${esc(s.social)}</bdi>`]);
    }
    const others = s.links.map(safeUrl).filter((u) => u && (!web || trimSlash(u) !== trimSlash(web)));
    if (others.length) rows.push([t("other_pages"), `<div>${others.map(extLink).join("<br>")}</div>`]);
    html += `<h4 class="pp__h">${esc(t("contact"))}</h4>` + (rows.length
      ? `<ul class="contact">${rows.map(([k, v]) => `<li><span>${esc(k)}</span>${v}</li>`).join("")}</ul>`
      : `<p class="pp__p">${esc(t("no_contact"))}</p>`);
    if (s.latest) html += `<p class="latest">${esc(t("latest", { latest: s.latest }))}</p>`;
    return html + `<p class="note">${esc(t("safety_note"))}</p>`;
  };

  /* ---------- sheet (profile and province on small screens, profiles from the list and grid) ---------- */

  const openSheet = (mode, opener) => {
    sheet = mode;
    sheetReturn = opener || document.activeElement;
    renderSheet();
    $("#sheet").hidden = false;
    document.body.classList.add("is-locked");
    hideHover();
    $("#sheet-card").focus();
  };

  const renderSheet = () => {
    if (!sheet) return;
    const card = $("#sheet-card");
    card.innerHTML = sheet.site
      ? siteHTML(sheet.site, { sheet: true, back: sheet.code ? pname(sheet.code) : "" })
      : provHTML(sheet.code, true);
    card.scrollTop = 0;
  };

  const closeSheet = () => {
    if (!sheet) return;
    sheet = null;
    $("#sheet").hidden = true;
    $("#sheet-card").innerHTML = "";
    document.body.classList.remove("is-locked");
    const back = sheetReturn;
    sheetReturn = null;
    if (back && document.contains(back)) back.focus({ preventScroll: true });
  };

  const trapTab = (e) => {
    const card = $("#sheet-card");
    const items = $$(FOCUSABLE, card).filter((x) => x.getClientRects().length);
    const cur = document.activeElement;
    if (!items.length) { e.preventDefault(); card.focus(); return; }
    const first = items[0], last = items[items.length - 1];
    if (!card.contains(cur)) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
    else if (e.shiftKey && (cur === first || cur === card)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
  };

  /* ---------- evidence popover ---------- */

  const openPop = () => {
    const pop = $("#popover");
    const rows = [["included", "ev_included", "pop_included"], ["unconfirmed", "ev_named", "pop_named"], ["unclear", "ev_all", "pop_all"]];
    pop.innerHTML = closeBtn() + `<h3 id="pop-h">${esc(t("pop_h"))}</h3>` +
      rows.map(([b, label, text]) => `<div class="pop__row"><span class="badge badge--${b}">${esc(t(label))}</span><p>${esc(t(text))}</p></div>`).join("") +
      `<p class="pop__foot">${markTh(esc(t("pop_foot")))}</p>`;
    pop.hidden = false;
    $(".info").setAttribute("aria-expanded", "true");
    placePop();
    $(".x", pop).focus();
  };

  const placePop = () => {
    const pop = $("#popover");
    if (pop.hidden) return;
    const r = $(".info").getBoundingClientRect();
    const w = pop.offsetWidth, h = pop.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const x = Math.max(16, Math.min(r.left + r.width / 2 - w / 2, vw - w - 16));
    let y = r.bottom + 10;
    if (y + h > vh - 16 && r.top - 10 - h >= 16) y = r.top - 10 - h;
    pop.style.left = x + "px";
    pop.style.top = y + "px";
  };

  const closePop = (refocus) => {
    const pop = $("#popover");
    if (pop.hidden) return;
    pop.hidden = true;
    $(".info").setAttribute("aria-expanded", "false");
    if (refocus) $(".info").focus();
  };

  /* ---------- list and grid ---------- */

  const renderResults = (list) => {
    const box = state.view === "list" ? $("#view-list") : $("#view-grid");
    (state.view === "list" ? $("#view-grid") : $("#view-list")).innerHTML = "";
    tiltCard = null;
    if (!list.length) {
      box.innerHTML = `<div class="empty"><p>${esc(t("empty"))}</p>${emptyActs("empty__acts")}</div>`;
      return;
    }
    const shown = list.slice(0, state.shown);
    const rest = list.length - shown.length;
    box.innerHTML = (state.view === "list" ? listHTML(shown) : gridHTML(shown)) +
      (rest > 0 ? `<button class="btn btn--ghost more" type="button" data-act="more">${esc(t("more", { n: rest }))}</button>` : "");
  };

  const listHTML = (items) => `<div class="list"><div class="list__head" aria-hidden="true">` +
    ["lh_org", "lh_where", "lh_svc", "lh_ev"].map((k) => `<span>${esc(t(k))}</span>`).join("") + "</div>" +
    items.map((s) => {
      const name = siteName(s), other = siteOther(s);
      return `<button class="lrow" type="button" data-act="open" data-v="${esc(s.id)}"><span>` +
        `<span class="lrow__name" lang="${langOf(name)}">${esc(name)}</span>` +
        (other ? `<span class="lrow__alt" lang="${langOf(other)}">${esc(other)}</span>` : "") +
        `<span class="lrow__type">${esc(typeShort(s.type))}</span></span>` +
        `<span class="lrow__where">${esc(whereText(s))}${cityText(s) ? `<span class="lrow__city">${esc(cityText(s))}</span>` : ""}</span>` +
        `<span class="lrow__chips">${chips(s, 4)}</span><span class="lrow__ev">${statusBadge(s, true)}${ledBadge(s)}</span></button>`;
    }).join("") + "</div>";

  const gridHTML = (items) => `<div class="grid">` + items.map((s) => {
    const name = siteName(s), other = siteOther(s);
    const q = s.evidence.find((e) => e.check === "found");
    const where = [whereText(s), cityText(s)].filter(Boolean).join(" · ");
    return `<button class="card card--${s.status}" type="button" data-act="open" data-v="${esc(s.id)}">` +
      `<span class="card__type">${esc(typeShort(s.type))}</span>` +
      `<span class="card__name" lang="${langOf(name)}">${esc(name)}</span>` +
      (other ? `<span class="card__alt" lang="${langOf(other)}">${esc(other)}</span>` : "") +
      `<span class="card__where">${esc(where)}</span>` +
      (q ? `<span class="card__quote" lang="${langOf(q.quote)}">“${esc(q.quote)}”</span>` : "") +
      `<span class="card__chips">${chips(s, 4)}</span><span class="card__foot">${statusBadge(s, true)}${ledBadge(s)}</span></button>`;
  }).join("") + "</div>";

  /* ---------- province board ---------- */

  const renderBoard = () => {
    const by = {};
    DATA.provinces.forEach((p) => { (by[p.region] = by[p.region] || []).push(p); });
    const regions = Object.keys(by).sort((a, b) => by[b].length - by[a].length || REGIONS.indexOf(a) - REGIONS.indexOf(b));
    $("#rack").innerHTML = regions.map((r) => {
      const ps = by[r].slice().sort((a, b) => PROV_RANK[a.status] - PROV_RANK[b.status] || coll().compare(pname(a.code), pname(b.code)));
      const covered = ps.filter((p) => p.status === "covered").length;
      return `<div class="slat" role="group" aria-label="${esc(regionName(r))}"><span class="slat__label" aria-hidden="true">${esc(regionShort(r))}</span>` +
        `<div class="slat__body"><p class="slat__stat">${esc(t("slat", { covered, total: ps.length }))}</p><div class="slat__chips">` +
        ps.map((p) => `<button class="pchip pchip--${p.status}" type="button" data-act="board" data-v="${p.code}" ` +
          `aria-label="${esc(`${pname(p.code)}, ${t("st_" + p.status)}, ${nSites(p.n)}`)}"><span>${esc(pname(p.code))}</span>` +
          (p.n ? `<span class="n">${p.n}</span>` : "") + "</button>").join("") + "</div></div></div>";
    }).join("");
  };

  /* ---------- method rail ---------- */

  // Hovering or focusing a spine opens its panel; a click keeps the panel open. Below 821px the panels stack.
  const initRail = () => {
    const rail = $("#rail");
    if (!rail) return;
    const plates = $$(".plate", rail);
    const spines = plates.map((p) => $(".plate__spine", p));
    let picked = null;
    const show = (plate) => plates.forEach((p, i) => {
      p.classList.toggle("is-open", p === plate);
      spines[i].setAttribute("aria-expanded", String(p === plate));
    });
    const choose = (plate) => {
      picked = plate;
      plates.forEach((p) => p.classList.toggle("is-picked", p === plate));
      show(plate);
    };
    plates.forEach((p, i) => {
      p.addEventListener("mouseenter", () => { if (FINE.matches && RAIL.matches) show(p); });
      spines[i].addEventListener("focus", () => { if (RAIL.matches) show(p); });
      spines[i].addEventListener("click", () => choose(!RAIL.matches && p.classList.contains("is-open") ? null : p));
      p.addEventListener("click", (e) => { if (RAIL.matches && !e.target.closest("a, .plate__spine")) choose(p); });
      spines[i].addEventListener("keydown", (e) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (!step && e.key !== "Home" && e.key !== "End") return;
        e.preventDefault();
        const n = spines.length;
        spines[e.key === "Home" ? 0 : e.key === "End" ? n - 1 : (i + step + n) % n].focus();
      });
    });
    rail.addEventListener("mouseleave", () => { if (RAIL.matches) show(picked); });
    rail.addEventListener("focusout", (e) => { if (RAIL.matches && !rail.contains(e.relatedTarget)) show(picked); });
    RAIL.addEventListener("change", () => { if (RAIL.matches) choose(picked || plates[0]); });
    choose(plates[0]);
  };

  /* ---------- events ---------- */

  const toggleMenu = (open) => {
    const head = $("#masthead");
    const on = open ?? !head.classList.contains("is-open");
    head.classList.toggle("is-open", on);
    $(".menu").setAttribute("aria-expanded", String(on));
  };

  const toggleFilters = (open) => {
    const bar = $("#filterbar");
    const on = open ?? !bar.classList.contains("is-open");
    bar.classList.toggle("is-open", on);
    $(".fb-toggle").setAttribute("aria-expanded", String(on));
  };

  const focusIn = (root, sel, noScroll) => {
    const x = (sel && $(sel, root)) || $('[tabindex="-1"]', root) || root;
    x.focus({ preventScroll: Boolean(noScroll) });
  };
  const focusTab = () => $('.tab[aria-pressed="true"]').focus({ preventScroll: true });
  const focusFirstResult = () => {
    if (state.view === "map") return focusIn($("#panel"), ".pp__title", true);
    const first = $(".lrow, .card", state.view === "list" ? $("#view-list") : $("#view-grid"));
    if (first) first.focus({ preventScroll: true });
    else focusTab();
  };
  const refocus = (act, v) => {
    const b = $(`[data-act="${act}"][data-v="${CSS.escape(v)}"]`);
    if (b) b.focus({ preventScroll: true });
  };

  // In-page links scroll without adding history entries.
  const jump = (e, a) => {
    const id = decodeURIComponent(a.getAttribute("href").slice(1));
    const dest = id && document.getElementById(id);
    if (!dest) return;
    e.preventDefault();
    toggleMenu(false);
    dest.scrollIntoView({ behavior: smooth(), block: "start" });
    if (!dest.matches(FOCUSABLE)) dest.setAttribute("tabindex", "-1");
    dest.focus({ preventScroll: true });
    history.replaceState(null, "", "#" + id);
  };

  const act = (el) => {
    const a = el.dataset.act, v = el.dataset.v || "";
    const ctx = el.closest("#sheet") ? "sheet" : el.closest("#popover") ? "pop" : el.closest("#panel") ? "panel" : "";
    if (a === "menu") return toggleMenu();
    if (a === "filters") return toggleFilters();
    if (a === "lang") {
      state.lang = isTh() ? "en" : "th";
      save("hh_lang", state.lang);
      return applyLang();
    }
    if (!DATA) return;
    switch (a) {
      case "region":
        state.region = v;
        if (v && state.province && PROV[state.province].region !== v) state.province = "";
        state.panel = null;
        state.shown = BATCH;
        fitTo(v);
        renderFilters();
        render();
        refocus(a, v);
        break;
      case "evidence":
        state.evidence = v;
        state.shown = BATCH;
        renderFilters();
        render();
        refocus(a, v);
        break;
      case "led":
        state.led = !state.led;
        state.shown = BATCH;
        renderFilters();
        render();
        break;
      case "view":
        if (state.view === v) break;
        state.view = v;
        state.shown = BATCH;
        setView();
        render();
        break;
      case "site":
        if (ctx === "sheet" && sheet) {
          sheet.site = v;
          renderSheet();
          focusIn($("#sheet-card"), ".back");
        } else {
          state.panel = v;
          renderPanel();
          focusIn($("#panel"), ".back");
        }
        break;
      case "open":
        openSheet({ code: "", site: v }, el);
        break;
      case "back":
        if (ctx === "sheet" && sheet) {
          const from = sheet.site;
          if (!sheet.code) {
            closeSheet();
            break;
          }
          sheet.site = "";
          renderSheet();
          focusIn($("#sheet-card"), `.srow[data-v="${CSS.escape(from)}"]`);
        } else {
          const from = state.panel || "";
          state.panel = null;
          renderPanel();
          focusIn($("#panel"), `.srow[data-v="${CSS.escape(from)}"]`);
        }
        break;
      case "close":
        if (ctx === "pop") closePop(true);
        else if (ctx === "sheet") closeSheet();
        else {
          state.province = "";
          state.panel = null;
          state.shown = BATCH;
          fitTo(state.region);
          render();
          focusIn($("#panel"), ".pp__title");
        }
        break;
      case "clear-province":
        state.province = "";
        state.panel = null;
        state.shown = BATCH;
        fitTo(state.region);
        render();
        focusTab();
        break;
      case "province":
        pickProvince(v, el);
        if (WIDE.matches) focusIn($("#panel"), ".pp__title");
        break;
      case "board":
        if (state.view !== "map") {
          state.view = "map";
          state.shown = BATCH;
          setView();
        }
        $("#find").scrollIntoView({ behavior: smooth(), block: "start" });
        pickProvince(v, el);
        if (WIDE.matches) focusIn($("#panel"), ".pp__title", true);
        break;
      case "to-list":
        closeSheet();
        state.view = "list";
        state.shown = BATCH;
        setView();
        render();
        focusFirstResult();
        break;
      case "show-here":
        state.q = "";
        $("#f-q").value = "";
        state.service = "";
        $("#f-service").value = "";
        state.evidence = "all";
        state.led = false;
        state.shown = BATCH;
        renderFilters();
        render();
        if (ctx === "sheet") {
          renderSheet();
          focusIn($("#sheet-card"), ".pp__title");
        } else {
          focusIn($("#panel"), ".pp__title");
        }
        break;
      case "all":
        state.evidence = "all";
        state.shown = BATCH;
        renderFilters();
        render();
        focusFirstResult();
        break;
      case "more": {
        const before = state.shown;
        state.shown += BATCH;
        render();
        const items = $$(".lrow, .card", state.view === "list" ? $("#view-list") : $("#view-grid"));
        if (items[before]) items[before].focus({ preventScroll: true });
        break;
      }
      case "reset":
        Object.assign(state, { q: "", service: "", region: "", evidence: "included", led: false, province: "", panel: null, shown: BATCH });
        $("#f-q").value = "";
        $("#f-service").value = "";
        fitTo("");
        renderFilters();
        render();
        focusTab();
        break;
      case "info":
        if ($("#popover").hidden) openPop();
        else closePop(true);
        break;
      default:
        break;
    }
  };

  const onClick = (e) => {
    const target = e.target;
    if (!(target instanceof Element)) return;
    if (target.id === "sheet") {
      closeSheet();
      return;
    }
    const pop = $("#popover");
    if (!pop.hidden && !pop.contains(target) && !target.closest(".info")) closePop(false);
    const head = $("#masthead");
    if (head.classList.contains("is-open") && !head.contains(target)) toggleMenu(false);
    const a = target.closest('a[href^="#"]');
    if (a) {
      jump(e, a);
      return;
    }
    const el = target.closest("[data-act]");
    if (el) act(el);
  };

  const onKey = (e) => {
    if (e.key === "Tab" && sheet) {
      trapTab(e);
      return;
    }
    if (e.key !== "Escape") return;
    hideHover();
    if (!$("#popover").hidden) closePop(true);
    else if (sheet) closeSheet();
    else if ($("#masthead").classList.contains("is-open")) {
      toggleMenu(false);
      $(".menu").focus();
    } else if ($("#filterbar").classList.contains("is-open")) {
      toggleFilters(false);
      $(".fb-toggle").focus();
    }
  };

  const onSearch = (e) => {
    const value = e.target.value;
    clearTimeout(qTimer);
    qTimer = setTimeout(() => {
      state.q = value.trim().toLowerCase();
      state.shown = BATCH;
      render();
    }, 200);
  };

  const onService = (e) => {
    if (!DATA) return;
    state.service = e.target.value;
    state.shown = BATCH;
    renderFilters();
    render();
  };

  const onScroll = () => {
    $("#masthead").classList.toggle("is-drawn", window.scrollY > 40);
    placePop();
    hideHover();
  };

  const onResize = () => {
    placePop();
    hideHover();
  };

  const resetTilt = () => {
    if (tiltCard) tiltCard.style.transform = "";
    tiltCard = null;
  };

  const onTilt = (e) => {
    if (!FINE.matches || CALM.matches || e.pointerType !== "mouse") return;
    const card = e.target instanceof Element ? e.target.closest(".card") : null;
    if (tiltCard && tiltCard !== card) resetTilt();
    if (!card) return;
    tiltCard = card;
    const r = card.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
    card.style.transform = `perspective(900px) rotateX(${(-py * 10).toFixed(2)}deg) rotateY(${(px * 12).toFixed(2)}deg) translateY(-3px)`;
  };

  const bind = () => {
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    $("#f-q").addEventListener("input", onSearch);
    $("#f-service").addEventListener("change", onService);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    $("#view-grid").addEventListener("pointermove", onTilt);
    $("#view-grid").addEventListener("pointerleave", resetTilt);
    WIDE.addEventListener("change", () => render());
  };

  const init = async () => {
    harvest();
    const lang = load("hh_lang");
    state.lang = lang === "th" || lang === "en" ? lang : (navigator.language || "").toLowerCase().startsWith("th") ? "th" : "en";
    const view = load("hh_view");
    if (view === "map" || view === "list" || view === "grid") state.view = view;
    bind();
    initRail();
    try {
      const res = await fetch("data/sites.json", { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      DATA = await res.json();
    } catch {
      DATA = null;
      applyLang();
      $("#countline").innerHTML = `<p class="alert">${esc(t("load_error"))}</p>`;
      onScroll();
      return;
    }
    prepare();
    setView();
    applyLang();
    onScroll();
  };

  init();
})();
