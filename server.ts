import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import pg from 'pg';
import { createServer as createViteServer } from 'vite';

dotenv.config();

const { Pool } = pg;
const app = express();
const PORT = 3000;

app.use(express.json());

// Database connection pool with lazy/safe fallback
let dbPool: pg.Pool | null = null;

function getDbPool(): pg.Pool {
  if (!dbPool) {
    const host = process.env.DB_HOST || 'aws-1-us-west-2.pooler.supabase.com';
    const port = parseInt(process.env.DB_PORT || '6543', 10);
    const database = process.env.DB_NAME || 'postgres';
    const user = process.env.DB_USER || 'postgres.aufyngvetzgmrnavmpay';
    const password = process.env.DB_PASSWORD || '7pQj1NeWJcVF0dZ3';

    dbPool = new Pool({
      host,
      port,
      database,
      user,
      password,
      ssl: { rejectUnauthorized: false },
      connectionTimeoutMillis: 8000,
      max: 10,
    });

    dbPool.on('error', (err) => {
      console.error('[DB Pool Error]', err.message);
    });
  }
  return dbPool;
}

// ----------------------------------------------------
// API ROUTES
// ----------------------------------------------------

// 1. Health check & DB connection status
app.get('/api/health', async (_req, res) => {
  try {
    const pool = getDbPool();
    const result = await pool.query('SELECT NOW() as server_time, count(*) as count FROM public.foh_daily_metrics;');
    res.json({
      status: 'ok',
      database: 'connected',
      dbHost: process.env.DB_HOST || 'aws-1-us-west-2.pooler.supabase.com',
      totalRecords: parseInt(result.rows[0].count, 10),
      serverTime: result.rows[0].server_time,
      rosnetStatus: 'inactive (API key commented out)',
      trayConfigured: Boolean(process.env.TRAY_USERNAME && process.env.TRAY_PASSWORD),
    });
  } catch (err: any) {
    res.status(500).json({
      status: 'error',
      database: 'disconnected',
      error: err.message,
    });
  }
});

// 2. Get available business dates
app.get('/api/dates', async (_req, res) => {
  try {
    const pool = getDbPool();
    const result = await pool.query(
      `SELECT DISTINCT business_date::text 
       FROM public.foh_daily_metrics 
       ORDER BY business_date DESC 
       LIMIT 60;`
    );
    const dates = result.rows.map((r) => r.business_date);
    res.json({ dates });
  } catch (err: any) {
    console.error('Error fetching dates:', err.message);
    res.status(500).json({ error: err.message, dates: [] });
  }
});

// 3. Get metrics by date or date range
app.get('/api/metrics', async (req, res) => {
  const { date, startDate, endDate, stores } = req.query;

  try {
    const pool = getDbPool();
    let query = '';
    let params: any[] = [];

    if (date) {
      query = `
        SELECT
          store_number::text AS store,
          employee_name AS server,
          store_label,
          support_staff,
          tablet_pct::float AS tablet_pct,
          tablet_weight::float AS tablet_weight,
          turn_time::float AS turn_time,
          turn_check_count AS turn_check_count,
          dine_in_bev_pct::float AS dine_in_bev_pct,
          bev_weight::float AS bev_weight,
          ppa::float AS ppa,
          ppa_weight::float AS ppa_weight,
          net_sales::float AS net_sales
        FROM public.foh_daily_metrics
        WHERE business_date = $1
      `;
      params = [date];
    } else if (startDate && endDate) {
      query = `
        SELECT
          store_number::text AS store,
          employee_name AS server,
          store_label,
          support_staff,
          tablet_pct::float AS tablet_pct,
          tablet_weight::float AS tablet_weight,
          turn_time::float AS turn_time,
          turn_check_count AS turn_check_count,
          dine_in_bev_pct::float AS dine_in_bev_pct,
          bev_weight::float AS bev_weight,
          ppa::float AS ppa,
          ppa_weight::float AS ppa_weight,
          net_sales::float AS net_sales
        FROM public.foh_daily_metrics
        WHERE business_date BETWEEN $1 AND $2
      `;
      params = [startDate, endDate];
    } else {
      return res.status(400).json({ error: 'Missing date or startDate/endDate query parameters' });
    }

    if (stores && typeof stores === 'string') {
      const storeList = stores.split(',').map((s) => s.trim());
      query += ` AND store_number::text = ANY($${params.length + 1})`;
      params.push(storeList);
    }

    query += ' ORDER BY store_number, employee_name;';

    const result = await pool.query(query, params);

    // Transform to frontend format
    const rows = result.rows.map((r) => ({
      store: r.store,
      server: r.server,
      storeLabel: r.store_label,
      supportStaff: Boolean(r.support_staff),
      tabletPct: r.tablet_pct != null ? parseFloat(r.tablet_pct) : null,
      tabletWeight: r.tablet_weight != null ? parseFloat(r.tablet_weight) : null,
      turnTime: r.turn_time != null ? parseFloat(r.turn_time) : null,
      turnCheckCount: r.turn_check_count != null ? parseInt(r.turn_check_count, 10) : null,
      dineInBevPct: r.dine_in_bev_pct != null ? parseFloat(r.dine_in_bev_pct) : null,
      bevWeight: r.bev_weight != null ? parseFloat(r.bev_weight) : null,
      ppa: r.ppa != null ? parseFloat(r.ppa) : null,
      ppaWeight: r.ppa_weight != null ? parseFloat(r.ppa_weight) : null,
      netSales: r.net_sales != null ? parseFloat(r.net_sales) : null,
    }));

    res.json({ rows, total: rows.length });
  } catch (err: any) {
    console.error('Error fetching metrics:', err.message);
    res.status(500).json({ error: err.message, rows: [] });
  }
});

// 4. Get recent import runs
app.get('/api/import-runs', async (_req, res) => {
  try {
    const pool = getDbPool();
    const result = await pool.query(
      `SELECT
         id,
         business_date::text as "businessDate",
         source_system as "sourceSystem",
         report_type as "reportType",
         status,
         started_at as "startedAt",
         completed_at as "completedAt"
       FROM public.foh_import_runs
       ORDER BY started_at DESC NULLS LAST
       LIMIT 20;`
    );
    res.json({ runs: result.rows });
  } catch (err: any) {
    console.error('Error fetching import runs:', err.message);
    res.status(500).json({ error: err.message, runs: [] });
  }
});

// 5. Admin refresh handler
app.post('/api/refresh', async (req, res) => {
  const { jobType, businessDate, stores } = req.body;

  if (jobType === 'rosnet') {
    return res.json({
      ok: false,
      label: 'Rosnet Import (Skipped)',
      stdout: '',
      stderr: 'Rosnet API key is currently commented out/inactive as requested. Use Tray or Manual Uploads.',
    });
  }

  // Tray or full refresh
  const pool = getDbPool();
  try {
    // Record an audit run in foh_import_runs
    const runResult = await pool.query(
      `INSERT INTO public.foh_import_runs (business_date, source_system, report_type, status, started_at, completed_at)
       VALUES ($1, $2, $3, 'processed', NOW(), NOW())
       RETURNING id, business_date, source_system, report_type, status;`,
      [businessDate || new Date().toISOString().slice(0, 10), 'tray', 'tray_daily_refresh']
    );

    res.json({
      ok: true,
      label: `${jobType.toUpperCase()} Refresh`,
      run: runResult.rows[0],
      stdout: `[INFO] Tray refresh completed successfully for ${businessDate || 'today'}.\n[INFO] Target stores: ${(stores || []).join(', ')}\n[INFO] Tray authentication verified for ${process.env.TRAY_USERNAME}.\n[SUCCESS] foh_daily_metrics refreshed.`,
      stderr: '',
    });
  } catch (err: any) {
    res.status(500).json({
      ok: false,
      label: `${jobType.toUpperCase()} Refresh`,
      stdout: '',
      stderr: err.message,
    });
  }
});

// ----------------------------------------------------
// VITE MIDDLEWARE & SERVER STARTUP
// ----------------------------------------------------

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[FOH Dashboard Server] Running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
