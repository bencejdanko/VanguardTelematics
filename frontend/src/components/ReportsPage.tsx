import { useState, useEffect } from 'react';
import styles from './ReportsPage.module.css';
import { API_BASE_URL } from '../config';
import { motion } from 'motion/react';
import {
  FileText, CloudArrowDown, HardDrives, Gauge, Clock,
  WarningCircle, ShieldWarning, ChartBar, CheckCircle
} from '@phosphor-icons/react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';

interface ReportData {
  generated_at: string;
  stream_depth: number;
  vehicles: string[];
  fleet_summary: {
    total_vehicles: number;
    vehicles_reporting: number;
    total_data_points: number;
    time_range: { earliest: string; latest: string };
  };
  per_vehicle: Record<string, {
    data_points: number;
    avg_pressure: number;
    max_pressure: number;
    min_pressure: number;
    avg_g_force: number;
    max_g_force: number;
    avg_pitch: number;
    avg_roll: number;
    incidents_count: number;
  }>;
  incidents: Array<{
    vehicle_id: string;
    type: string;
    g_force: number;
    jerk: number;
    timestamp_approx: string;
  }>;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 120, damping: 20 } }
};

export const ReportsPage = () => {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/report`);
      if (!res.ok) throw new Error("Failed to fetch report");
      const data = await res.json();
      setReport(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  const handleDownloadCSV = () => {
    window.location.href = `${API_BASE_URL}/export/csv?count=5000`;
  };

  const handleDownloadJSON = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fleet_report_${new Date().toISOString()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading && !report) {
    return (
      <div className={styles.reportsPage} style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--text-muted)' }}>Generating Fleet Intelligence Report...</div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className={styles.reportsPage} style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--status-emergency)' }}>Error: {error || "Failed to load report"}</div>
        <button className={styles.btn} onClick={fetchReport}>Retry</button>
      </div>
    );
  }

  // Transform data for charts
  const vehicleChartData = report.vehicles.map(vId => {
    const vData = report.per_vehicle[vId] || {};
    return {
      name: vId,
      avg_g: vData.avg_g_force || 0,
      max_g: vData.max_g_force || 0,
      avg_press: vData.avg_pressure || 0,
      min_press: vData.min_pressure || 0,
    };
  });

  return (
    <motion.div
      className={styles.reportsPage}
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.header variants={itemVariants} className={styles.header}>
        <div>
          <h1 className={styles.title}>Fleet Intelligence Report</h1>
          <p className={styles.subtitle}>
            <Clock size={16} /> Generated: {new Date(report.generated_at).toLocaleString()}
          </p>
        </div>
        <div className={styles.actions}>
          <button className={styles.btn} onClick={fetchReport}>
            Refresh Data
          </button>
          <button className={`${styles.btn} ${styles.btnPrimary}`} onClick={handleDownloadCSV}>
            <CloudArrowDown size={18} weight="bold" /> Export CSV
          </button>
        </div>
      </motion.header>

      <motion.div variants={itemVariants} className={styles.kpiGrid}>
        <div className={`${styles.kpiCard} glass-panel`}>
          <div className={styles.kpiLabel}><HardDrives size={18} weight="duotone" /> Data Points Analyzed</div>
          <div className={`${styles.kpiValue} mono`}>
            {report.fleet_summary.total_data_points.toLocaleString()}
          </div>
        </div>
        <div className={`${styles.kpiCard} glass-panel`}>
          <div className={styles.kpiLabel}><CheckCircle size={18} weight="duotone" /> Reporting Vehicles</div>
          <div className={styles.kpiValue}>
            {report.fleet_summary.vehicles_reporting} <span className={styles.kpiSub}>/ {report.fleet_summary.total_vehicles}</span>
          </div>
        </div>
        <div className={`${styles.kpiCard} glass-panel`}>
          <div className={styles.kpiLabel}><WarningCircle size={18} weight="duotone" /> Total Incidents</div>
          <div className={styles.kpiValue} style={{ color: report.incidents.length > 0 ? 'var(--status-emergency)' : 'inherit' }}>
            {report.incidents.length}
          </div>
        </div>
        <div className={`${styles.kpiCard} glass-panel`}>
          <div className={styles.kpiLabel}><Clock size={18} weight="duotone" /> Time Range</div>
          <div className={`${styles.kpiValue} mono`} style={{ fontSize: '1.2rem' }}>
            {report.fleet_summary.time_range.earliest ? new Date(report.fleet_summary.time_range.earliest).toLocaleTimeString() : 'N/A'} - 
            <br />
            {report.fleet_summary.time_range.latest ? new Date(report.fleet_summary.time_range.latest).toLocaleTimeString() : 'N/A'}
          </div>
        </div>
      </motion.div>

      <motion.section variants={itemVariants} className={styles.section}>
        <h2 className={styles.sectionTitle}><FileText size={22} weight="duotone" /> Per-Vehicle Status</h2>
        <div className={`${styles.tableContainer} glass-panel`}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Vehicle ID</th>
                <th>Data Points</th>
                <th>Avg / Max G-Force</th>
                <th>Avg / Max Pressure</th>
                <th>Incidents</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {report.vehicles.map(vId => {
                const data = report.per_vehicle[vId];
                if (!data) return null;
                const statusClass = data.incidents_count > 0 ? styles.statusEmergency : (data.max_g_force > 2 ? styles.statusWarning : styles.statusHealthy);
                const statusText = data.incidents_count > 0 ? 'Critical' : (data.max_g_force > 2 ? 'Warning' : 'Healthy');
                
                return (
                  <tr key={vId}>
                    <td className="mono">{vId}</td>
                    <td className="mono">{data.data_points.toLocaleString()}</td>
                    <td className="mono">{data.avg_g_force}g / {data.max_g_force}g</td>
                    <td className="mono">{data.avg_pressure}hPa / {data.max_pressure}hPa</td>
                    <td className="mono" style={{ color: data.incidents_count > 0 ? 'var(--status-emergency)' : 'inherit' }}>
                      {data.incidents_count}
                    </td>
                    <td>
                      <span className={`${styles.statusDot} ${statusClass}`}></span>
                      {statusText}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </motion.section>

      <motion.section variants={itemVariants} className={styles.section}>
        <h2 className={styles.sectionTitle}><ChartBar size={22} weight="duotone" /> Sensor Distribution</h2>
        <div className={styles.chartsGrid}>
          <div className={`${styles.chartCard} glass-panel`}>
            <div className={styles.chartTitle}>G-Force Load per Vehicle</div>
            <div style={{ height: 300 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={vehicleChartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: 'rgba(9, 9, 11, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }} />
                  <Legend />
                  <Bar dataKey="avg_g" name="Average G-Force" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="max_g" name="Max G-Force" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className={`${styles.chartCard} glass-panel`}>
            <div className={styles.chartTitle}>Atmospheric Pressure per Vehicle (hPa)</div>
            <div style={{ height: 300 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={vehicleChartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--text-muted)" tickLine={false} axisLine={false} domain={['dataMin - 5', 'dataMax + 5']} />
                  <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: 'rgba(9, 9, 11, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }} />
                  <Legend />
                  <Bar dataKey="avg_press" name="Avg Pressure" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="min_press" name="Min Pressure" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section variants={itemVariants} className={styles.section}>
        <h2 className={styles.sectionTitle}><ShieldWarning size={22} weight="duotone" /> Incident Log</h2>
        {report.incidents.length === 0 ? (
          <div className={styles.emptyState}>
            No incidents detected in the current time window.
          </div>
        ) : (
          <div className={styles.incidentList}>
            {report.incidents.map((inc, i) => (
              <div key={i} className={styles.incidentCard}>
                <div className={styles.incidentInfo}>
                  <div className={styles.incidentType}>{inc.type} on Unit {inc.vehicle_id}</div>
                  <div className={styles.incidentMeta}>
                    <span className="mono">{new Date(inc.timestamp_approx).toLocaleString()}</span>
                    <span className="mono">Stream ID: {inc.stream_id}</span>
                  </div>
                </div>
                <div className={styles.incidentMetrics}>
                  <div className={styles.metric}>
                    <span className={`${styles.metricValue} mono`}>{inc.g_force}G</span>
                    <span className={styles.metricLabel}>Impact Force</span>
                  </div>
                  <div className={styles.metric}>
                    <span className={`${styles.metricValue} mono`}>{inc.jerk}</span>
                    <span className={styles.metricLabel}>Jerk Ratio</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.section>

      <motion.div variants={itemVariants} style={{ display: 'flex', justifyContent: 'center', marginTop: '20px', marginBottom: '40px' }}>
         <button className={styles.btn} onClick={handleDownloadJSON}>
            Download Raw Report (JSON)
          </button>
      </motion.div>
    </motion.div>
  );
};
