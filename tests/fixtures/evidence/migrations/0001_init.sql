create table session_set (id uuid primary key, owner uuid not null);
alter table session_set enable row level security;
