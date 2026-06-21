import styles from './TelemetryDashboard.module.css';
import { SensorData } from '../types';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Thermometer, Gauge, WaveSine, NavigationArrow, ShieldWarning, Heartbeat } from '@phosphor-icons/react';
import { motion } from 'motion/react';
import { CybertruckViewer } from './CybertruckViewer';

interface Props {
  vehicleName: string;
  isEmergency: boolean;
  currentData: SensorData | null;
  dataStream: SensorData[];
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

// Net acceleration magnitude in g (sensor reports milli-g).
const accelG = (d: SensorData): number =>
  Math.sqrt(d.accelX ** 2 + d.accelY ** 2 + d.accelZ ** 2) / 1000;

export const TelemetryDashboard = ({ vehicleName, isEmergency, currentData, dataStream }: Props) => {
  return (
    <motion.div
      className={styles.dashboard}
      variants={containerVariants}
      initial="hidden"
      animate="show"
      key={vehicleName} // Re-trigger animation on vehicle switch
    >
      <motion.header variants={itemVariants} className={styles.header}>
        <div>
          <h1 className={styles.title}>{vehicleName}</h1>
          <p className={styles.subtitle}>Live Hardware Telemetry</p>
        </div>

        <div className={`${styles.statusBadge} ${isEmergency ? styles.statusEmergency : styles.statusHealthy}`}>
          {isEmergency ? <ShieldWarning size={20} weight="fill" /> : <Heartbeat size={20} weight="bold" />}
          {isEmergency ? 'Critical Event' : 'System Nominal'}
        </div>
      </motion.header>

      <motion.div variants={itemVariants} className={styles.heroGrid}>
        <CybertruckViewer
          pitch={currentData?.pitch ?? 0}
          roll={currentData?.roll ?? 0}
          yaw={currentData?.yaw ?? 0}
          isEmergency={isEmergency}
        />

        <div className={styles.statStack}>
          <div className={`${styles.kpiCard} glass-panel`}>
            <div className={styles.kpiLabel}><Gauge size={18} weight="duotone" /> Impact G-Force</div>
            <div className={`${styles.kpiValue} mono`} style={{ color: currentData?.gForce && currentData.gForce > 4.0 ? 'var(--error-color, #ef4444)' : 'inherit' }}>
              {currentData?.gForce !== undefined ? currentData.gForce.toFixed(2) : '0.00'}<span className={styles.kpiUnit}>G</span>
            </div>
          </div>
          <div className={`${styles.kpiCard} glass-panel`}>
            <div className={styles.kpiLabel}><Gauge size={18} weight="duotone" /> Pressure</div>
            <div className={`${styles.kpiValue} mono`}>{currentData ? currentData.pressure.toFixed(1) : 'N/A'}<span className={styles.kpiUnit}>hPa</span></div>
          </div>
          
          <div className={`${styles.kpiCard} glass-panel`}>
            <div className={styles.kpiLabel}><WaveSine size={18} weight="duotone" /> Net Accel</div>
            <div className={`${styles.kpiValue} mono`}>
              {currentData ? accelG(currentData).toFixed(2) : 'N/A'}
              <span className={styles.kpiUnit}>g</span>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div variants={itemVariants} className={styles.chartsGrid}>
        <div className={`${styles.chartCard} glass-panel`}>
          <div className={styles.chartHeader}>
            <span className={styles.chartTitle}>Gyroscope Vector</span>
            <span className={styles.chartSub}>(mdps)</span>
          </div>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dataStream}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" hide />
                <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} width={60} domain={[-100000, 100000]} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'rgba(9, 9, 11, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', backdropFilter: 'blur(10px)' }}
                  itemStyle={{ fontSize: '13px' }}
                />
                <Line type="basis" dataKey="gyroX" stroke="#06b6d4" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="basis" dataKey="gyroY" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="basis" dataKey="gyroZ" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className={`${styles.chartCard} glass-panel`}>
          <div className={styles.chartHeader}>
            <span className={styles.chartTitle}>Accelerometer</span>
            <span className={styles.chartSub}>(mg)</span>
          </div>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dataStream}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" hide />
                <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} width={40} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'rgba(9, 9, 11, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', backdropFilter: 'blur(10px)' }}
                  itemStyle={{ fontSize: '13px' }}
                />
                <Line type="monotone" dataKey="accelX" stroke="#06b6d4" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="accelY" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="accelZ" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
