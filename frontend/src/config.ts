export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const HISTORY_POLL_INTERVAL_MS = 1000;
export const HISTORY_COUNT = 50;

export const SENSOR_THRESHOLDS = {
  GYRO_Z_MAX: 8000,
  ACCEL_Z_MIN: 500,
};
