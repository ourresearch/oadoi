 SELECT md5(e.doi) AS id,
    e.doi,
    e.updated,
    e.oa_status,
    e.fulltext_url,
    e.evidence,
    e.license,
    e.version,
    true AS is_best
   FROM export_main e
  WHERE e.oa_status = ANY (ARRAY['hybrid'::text, 'bronze'::text, 'gold'::text, 'green'::text])
UNION
 SELECT b.id,
    b.doi,
    e.updated,
    'green'::text AS oa_status,
    COALESCE(b.scrape_pdf_url, COALESCE(b.scrape_metadata_url, b.url)) AS fulltext_url,
    b.scrape_evidence AS evidence,
    b.scrape_license AS license,
    b.scrape_version AS version,
    false AS is_best
   FROM base_match b,
    export_main e
  WHERE b.doi = e.doi;