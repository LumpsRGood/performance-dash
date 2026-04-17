create table if not exists public.foh_import_runs (
    id bigserial primary key,
    business_date date not null,
    source_system text not null,
    report_type text not null,
    source_filename text,
    source_file_hash text,
    status text not null default 'loaded',
    row_count integer,
    metadata jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    constraint foh_import_runs_source_system_check
        check (source_system in ('tray', 'rosnet', 'pipeline')),
    constraint foh_import_runs_status_check
        check (status in ('loaded', 'processed', 'failed', 'skipped'))
);

create index if not exists idx_foh_import_runs_business_date
    on public.foh_import_runs (business_date desc);

create index if not exists idx_foh_import_runs_source
    on public.foh_import_runs (source_system, report_type, business_date desc);

create table if not exists public.foh_daily_metrics (
    business_date date not null,
    store_number bigint not null,
    store_label text,
    employee_name text not null,
    employee_source_id text,
    support_staff boolean not null default false,
    tablet_pct numeric,
    tablet_weight numeric,
    turn_time numeric,
    turn_check_count integer,
    dine_in_bev_pct numeric,
    bev_weight numeric,
    ppa numeric,
    ppa_weight numeric,
    net_sales numeric,
    tablet_import_run_id bigint references public.foh_import_runs(id) on delete set null,
    turn_import_run_id bigint references public.foh_import_runs(id) on delete set null,
    bev_import_run_id bigint references public.foh_import_runs(id) on delete set null,
    ppa_import_run_id bigint references public.foh_import_runs(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (business_date, store_number, employee_name)
);

create index if not exists idx_foh_daily_metrics_store_date
    on public.foh_daily_metrics (store_number, business_date desc);

create index if not exists idx_foh_daily_metrics_date
    on public.foh_daily_metrics (business_date desc);

create index if not exists idx_foh_daily_metrics_support_staff
    on public.foh_daily_metrics (business_date desc, support_staff);

comment on table public.foh_import_runs is
    'Tracks one-day Rosnet and Tray source imports so dates can be rerun, audited, and backfilled cleanly.';

comment on table public.foh_daily_metrics is
    'Normalized daily FOH metrics by store/server, designed for automated Tray + Rosnet ingestion and weighted lookback trends.';

comment on column public.foh_daily_metrics.tablet_weight is
    'Total sales base used to weight tablet percentage across multi-day rollups.';

comment on column public.foh_daily_metrics.turn_check_count is
    'Count of eat-in checks contributing to turn time for weighted multi-day rollups.';

comment on column public.foh_daily_metrics.bev_weight is
    'Net sales weight used to roll dine-in beverage percent accurately across multiple days.';

comment on column public.foh_daily_metrics.ppa_weight is
    'Covers used to roll PPA accurately across multiple days.';
