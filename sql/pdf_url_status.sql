create table if not exists pdf_url_status (
    url             text    primary key,
    is_pdf          boolean,
    http_status     smallint,
    last_checked    timestamp without time zone
);


ALTER TABLE pdf_url_status SET (autovacuum_vacuum_scale_factor = 0.001);
ALTER TABLE pdf_url_status SET (autovacuum_vacuum_threshold = 10000);
ALTER TABLE pdf_url_status SET (autovacuum_analyze_scale_factor = 0.001);
ALTER TABLE pdf_url_status SET (autovacuum_analyze_threshold = 10000);
ALTER TABLE pdf_url_status SET (autovacuum_vacuum_cost_limit = 10000);
ALTER TABLE pdf_url_status SET (log_autovacuum_min_duration=0);