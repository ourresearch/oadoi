create table if not exists pdf_url (
    url             text    primary key,
    publisher       text,
    is_pdf          boolean,
    http_status     smallint,
    last_checked    timestamp without time zone
);


ALTER TABLE pdf_url SET (autovacuum_vacuum_scale_factor = 0.001);
ALTER TABLE pdf_url SET (autovacuum_vacuum_threshold = 10000);
ALTER TABLE pdf_url SET (autovacuum_analyze_scale_factor = 0.001);
ALTER TABLE pdf_url SET (autovacuum_analyze_threshold = 10000);
ALTER TABLE pdf_url SET (autovacuum_vacuum_cost_limit = 10000);
ALTER TABLE pdf_url SET (log_autovacuum_min_duration=0);