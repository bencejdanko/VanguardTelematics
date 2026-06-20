import styles from './VehicleList.module.css';
import { Activity } from 'lucide-react';

interface Vehicle {
  id: string;
  name: string;
  status: 'healthy' | 'emergency';
}

interface Props {
  vehicles: Vehicle[];
  activeId: string;
  onSelect: (id: string) => void;
}

export const VehicleList = ({ vehicles, activeId, onSelect }: Props) => {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <Activity className={styles.brandIcon} size={24} />
        <span>AeroDispatch</span>
      </div>

      <div>
        <div className={styles.sectionTitle}>Active Fleet</div>
        <div className={styles.list}>
          {vehicles.map((v) => (
            <div
              key={v.id}
              className={`${styles.vehicleItem} ${activeId === v.id ? styles.active : ''}`}
              onClick={() => onSelect(v.id)}
            >
              <div className={`${styles.statusIndicator} ${v.status === 'emergency' ? styles.emergency : ''}`} />
              <div className={styles.vehicleInfo}>
                <span className={styles.vehicleName}>{v.name}</span>
                <span className={styles.vehicleId}>{v.id}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
};
