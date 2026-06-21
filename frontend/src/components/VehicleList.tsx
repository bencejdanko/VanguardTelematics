import styles from './VehicleList.module.css';
import { Heartbeat, ChartBar } from '@phosphor-icons/react';
import { motion } from 'motion/react';

interface Vehicle {
  id: string;
  name: string;
  status: 'healthy' | 'warning' | 'emergency';
}

interface Props {
  vehicles: Vehicle[];
  activeId: string | null;
  onSelect: (id: string) => void;
  currentPage: 'dashboard' | 'reports';
  onNavigate: (page: 'dashboard' | 'reports') => void;
}

export const VehicleList = ({ vehicles, activeId, onSelect, currentPage, onNavigate }: Props) => {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.brandIconWrapper}>
          <Heartbeat weight="bold" />
        </div>
        <span>DataLog<span className={styles.brandAccent}>Fusion</span></span>
      </div>

      <div className={styles.fleetSection}>
        <div className={styles.sectionTitle}>Deployed Units</div>
        <div className={styles.list}>
          {vehicles.map((v) => {
            const isActive = activeId === v.id && currentPage === 'dashboard';
            return (
              <motion.button
                key={v.id}
                whileTap={{ scale: 0.98 }}
                className={`${styles.vehicleItem} ${isActive ? styles.active : ''}`}
                onClick={() => {
                  onSelect(v.id);
                  onNavigate('dashboard');
                }}
              >
                <div className={`${styles.statusIndicator} ${v.status === 'emergency' ? styles.emergency : ''}`} />
                <div className={styles.vehicleInfo}>
                  <span className={styles.vehicleName}>{v.name}</span>
                  <span className={styles.vehicleId}>{v.id}</span>
                </div>
                {isActive && (
                  <motion.div layoutId="activeIndicator" className={styles.activePill} />
                )}
              </motion.button>
            );
          })}
          {vehicles.length === 0 && (
            <div className={styles.emptyState}>No units deployed</div>
          )}
        </div>
      </div>

      <div className={styles.navSection}>
        <div className={styles.sectionTitle}>Intelligence</div>
        <button 
          className={`${styles.reportsBtn} ${currentPage === 'reports' ? styles.active : ''}`}
          onClick={() => onNavigate('reports')}
        >
          <ChartBar size={20} className={styles.reportsIcon} />
          <span>Fleet Reports</span>
          {currentPage === 'reports' && (
            <motion.div layoutId="activeIndicator" className={styles.activePill} />
          )}
        </button>
      </div>
    </aside>
  );
};
