select * from pg_stat_activity where pid <> pg_backend_pid();
