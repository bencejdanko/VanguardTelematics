import styles from './EmergencyAlert.module.css';
import { AlertTriangle, Radio, CheckCircle2 } from 'lucide-react';

interface Props {
  vehicleName: string;
  onDismiss: () => void;
}

export const EmergencyAlert = ({ vehicleName, onDismiss }: Props) => {
  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <div className={styles.iconWrapper}>
          <AlertTriangle size={32} />
        </div>
        
        <div className={styles.content}>
          <h2 className={styles.title}>Incident Detected</h2>
          <p className={styles.description}>
            Critical rollover or impact detected on <strong>{vehicleName}</strong>. 
            Telemetry values exceeded safe thresholds.
          </p>
        </div>

        <div className={styles.systemStatus}>
          <div className={styles.statusRow}>
            <CheckCircle2 size={16} className={styles.statusIcon} />
            <span>Event logged to Redis stream</span>
          </div>
          <div className={styles.statusRow}>
            <CheckCircle2 size={16} className={styles.statusIcon} />
            <span>Initiated Deepgram emergency dispatch radio call</span>
          </div>
          <div className={styles.statusRow}>
            <Radio size={16} className={styles.statusIcon} />
            <span className="mono">Awaiting responder confirmation...</span>
          </div>
        </div>

        <button className={styles.button} onClick={onDismiss}>
          Acknowledge & Dismiss
        </button>
      </div>
    </div>
  );
};
