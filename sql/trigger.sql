CREATE OR REPLACE FUNCTION insert_doi()
  RETURNS trigger AS
$$
BEGIN
         INSERT INTO pub_queue(id) VALUES(NEW.id);
         INSERT INTO pub_queue_abstract(id) VALUES(NEW.id);
         INSERT INTO pub_refresh_queue(id) VALUES(NEW.id);
    RETURN NEW;
END;
$$
LANGUAGE 'plpgsql';

CREATE TRIGGER insert_doi_queue_trigger
  AFTER INSERT
  ON pub
  FOR EACH ROW
  EXECUTE PROCEDURE insert_doi();
-- 97216394

ALTER TABLE pub_queue SET (autovacuum_vacuum_scale_factor = 0.001);
ALTER TABLE pub_queue SET (autovacuum_vacuum_threshold = 10000);
ALTER TABLE pub_queue SET (autovacuum_analyze_scale_factor = 0.001);
ALTER TABLE pub_queue SET (autovacuum_analyze_threshold = 10000);
ALTER TABLE pub_queue SET (autovacuum_vacuum_cost_limit = 10000);
ALTER TABLE pub_queue SET (log_autovacuum_min_duration=0);

ALTER TABLE pub_queue_abstract SET (autovacuum_vacuum_scale_factor = 0.001);
ALTER TABLE pub_queue_abstract SET (autovacuum_vacuum_threshold = 10000);
ALTER TABLE pub_queue_abstract SET (autovacuum_analyze_scale_factor = 0.001);
ALTER TABLE pub_queue_abstract SET (autovacuum_analyze_threshold = 10000);
ALTER TABLE pub_queue_abstract SET (autovacuum_vacuum_cost_limit = 10000);
ALTER TABLE pub_queue_abstract SET (log_autovacuum_min_duration=0);

ALTER TABLE pub_refresh_queue SET (autovacuum_vacuum_scale_factor = 0.001);
ALTER TABLE pub_refresh_queue SET (autovacuum_vacuum_threshold = 10000);
ALTER TABLE pub_refresh_queue SET (autovacuum_analyze_scale_factor = 0.001);
ALTER TABLE pub_refresh_queue SET (autovacuum_analyze_threshold = 10000);
ALTER TABLE pub_refresh_queue SET (autovacuum_vacuum_cost_limit = 10000);
ALTER TABLE pub_refresh_queue SET (log_autovacuum_min_duration=0);

CREATE OR REPLACE FUNCTION insert_pdf_url()
  RETURNS trigger AS
$$
BEGIN
    INSERT INTO pdf_url_check_queue(url) VALUES(NEW.url);
    RETURN NEW;
END;
$$
LANGUAGE 'plpgsql';

CREATE TRIGGER insert_pdf_queue_trigger
  AFTER INSERT
  ON pdf_url
  FOR EACH ROW
  EXECUTE PROCEDURE insert_pdf_url();

ALTER TABLE pdf_url_check_queue SET (autovacuum_vacuum_scale_factor = 0.001);
ALTER TABLE pdf_url_check_queue SET (autovacuum_vacuum_threshold = 10000);
ALTER TABLE pdf_url_check_queue SET (autovacuum_analyze_scale_factor = 0.001);
ALTER TABLE pdf_url_check_queue SET (autovacuum_analyze_threshold = 10000);
ALTER TABLE pdf_url_check_queue SET (autovacuum_vacuum_cost_limit = 10000);
ALTER TABLE pdf_url_check_queue SET (log_autovacuum_min_duration=0);


SELECT pg_reload_conf();
