import styles from './TelemetryDashboard.module.css';
import { SensorData } from '../hooks/useSensorStream';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Thermometer, Gauge, Navigation } from 'lucide-react';

interface Props {
  vehicleName: string;
  isEmergency: boolean;
  currentData: SensorData | null;
  dataStream: SensorData[];
}

export const TelemetryDashboard = ({ vehicleName, isEmergency, currentData, dataStream }: Props) => {
  return (
    <div className={styles.dashboard}>
      <header className={styles.header}>
        <h1 className={styles.title}>{vehicleName} Telemetry</h1>
        <div className={`${styles.statusBadge} ${isEmergency ? styles.statusEmergency : styles.statusHealthy}`}>
          {isEmergency ? 'Emergency Detected' : 'Healthy'}
        </div>
      </header>

      {currentData && (
        <div className={styles.kpiGrid}>
          <div className={`${styles.kpiCard} glass-panel`}>
            <div className={styles.kpiLabel}><Thermometer size={16} /> Temperature</div>
            <div className={`${styles.kpiValue} mono`}>{currentData.temperature.toFixed(2)} °C</div>
          </div>
          <div className={`${styles.kpiCard} glass-panel`}>
            <div className={styles.kpiLabel}><Gauge size={16} /> Pressure</div>
            <div className={`${styles.kpiValue} mono`}>{currentData.pressure.toFixed(2)} hPa</div>
          </div>
          <div className={`${styles.kpiCard} glass-panel`}>
            <div className={styles.kpiLabel}><Navigation size={16} /> Pitch / Roll</div>
            <div className={`${styles.kpiValue} mono`}>
              {currentData.pitch.toFixed(1)}° / {currentData.roll.toFixed(1)}°
            </div>
          </div>
        </div>
      )}

      <div className={styles.chartsGrid}>
        <div className={`${styles.chartCard} glass-panel`}>
          <div className={styles.chartHeader}>Gyroscope (X, Y, Z)</div>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dataStream}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="time" hide />
                <YAxis stroke="var(--text-muted)" />
                <Tooltip contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: 'none', borderRadius: '8px' }} />
                <Line type="monotone" dataKey="gyroX" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="gyroY" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="gyroZ" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className={`${styles.chartCard} glass-panel`}>
          <div className={styles.chartHeader}>Accelerometer (X, Y, Z)</div>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dataStream}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="time" hide />
                <YAxis stroke="var(--text-muted)" />
                <Tooltip contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: 'none', borderRadius: '8px' }} />
                <Line type="monotone" dataKey="accelX" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="accelY" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="accelZ" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
