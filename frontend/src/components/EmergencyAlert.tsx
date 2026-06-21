import styles from './EmergencyAlert.module.css';
import { WarningCircle, Radio, CheckCircle } from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'motion/react';

interface Props {
  vehicleName: string;
  incidentType?: string;
  onDismiss: () => void;
}

const overlayVariants = {
  hidden: { opacity: 0, backdropFilter: 'blur(0px)' },
  visible: { opacity: 1, backdropFilter: 'blur(12px)', transition: { duration: 0.3 } },
  exit: { opacity: 0, backdropFilter: 'blur(0px)', transition: { duration: 0.2 } }
};

const modalVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 20 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 25 } },
  exit: { opacity: 0, scale: 0.95, y: -20, transition: { duration: 0.2 } }
};

export const EmergencyAlert = ({ vehicleName, incidentType, onDismiss }: Props) => {
  return (
    <AnimatePresence>
      <motion.div 
        className={styles.overlay}
        variants={overlayVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        <motion.div className={styles.modal} variants={modalVariants}>
          <div className={styles.iconWrapper}>
            <WarningCircle size={40} weight="fill" />
            <div className={styles.pulseRing} />
          </div>
          
          <div className={styles.content}>
            <h2 className={styles.title}>{incidentType || 'Incident'} Detected</h2>
            <p className={styles.description}>
              Critical <strong>{incidentType ? incidentType.toLowerCase() : 'incident'}</strong> detected on <strong>{vehicleName}</strong>. 
              Telemetry values exceeded safe operational thresholds.
            </p>
          </div>

          <div className={styles.systemStatus}>
            <div className={styles.statusRow}>
              <CheckCircle size={18} weight="fill" className={styles.statusIcon} />
              <span>Event logged to Redis stream</span>
            </div>
            <div className={styles.statusRow}>
              <CheckCircle size={18} weight="fill" className={styles.statusIcon} />
              <span>Initiated Deepgram emergency dispatch radio call</span>
            </div>
            <div className={styles.statusRow}>
              <Radio size={18} weight="duotone" className={styles.statusIconRadio} />
              <span className="mono">Awaiting responder confirmation...</span>
            </div>
          </div>

          <motion.button 
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className={styles.button} 
            onClick={onDismiss}
          >
            Acknowledge & Dismiss
          </motion.button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};
