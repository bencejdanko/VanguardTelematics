import styles from './EmergencyAlert.module.css';
import { WarningCircle, Radio, CheckCircle, X } from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'motion/react';

interface Props {
  vehicleName: string;
  incidentType?: string;
  onDismiss: () => void;
}

const toastVariants = {
  hidden: { opacity: 0, x: 40, scale: 0.96 },
  visible: { opacity: 1, x: 0, scale: 1, transition: { type: "spring" as const, stiffness: 300, damping: 26 } },
  exit: { opacity: 0, x: 40, scale: 0.96, transition: { duration: 0.2 } }
};

export const EmergencyAlert = ({ vehicleName, incidentType, onDismiss }: Props) => {
  return (
    <AnimatePresence>
      <motion.div
        className={styles.toast}
        variants={toastVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        role="alert"
      >
        <div className={styles.head}>
          <div className={styles.iconWrapper}>
            <WarningCircle size={22} weight="fill" />
            <div className={styles.pulseRing} />
          </div>
          <div className={styles.content}>
            <h2 className={styles.title}>{incidentType || 'Incident'} Detected</h2>
            <p className={styles.description}>
              Critical <strong>{incidentType ? incidentType.toLowerCase() : 'incident'}</strong> detected on <strong>{vehicleName}</strong>. 
              Telemetry values exceeded safe operational thresholds.
            </p>
          </div>
          <button className={styles.close} onClick={onDismiss} aria-label="Dismiss alert">
            <X size={16} weight="bold" />
          </button>
        </div>

        <div className={styles.systemStatus}>
          <div className={styles.statusRow}>
            <CheckCircle size={16} weight="fill" className={styles.statusIcon} />
            <span>Event logged to Redis stream</span>
          </div>
          <div className={styles.statusRow}>
            <CheckCircle size={16} weight="fill" className={styles.statusIcon} />
            <span>Deepgram emergency dispatch initiated</span>
          </div>
          <div className={styles.statusRow}>
            <Radio size={16} weight="duotone" className={styles.statusIconRadio} />
            <span className="mono">Awaiting responder confirmation...</span>
          </div>
        </div>

        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={styles.button}
          onClick={onDismiss}
        >
          Acknowledge
        </motion.button>
      </motion.div>
    </AnimatePresence>
  );
};
