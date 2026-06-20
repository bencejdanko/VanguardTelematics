import { useState, useEffect } from 'react';
import { SensorData } from '../types';
import { API_BASE_URL, HISTORY_POLL_INTERVAL_MS, HISTORY_COUNT, SENSOR_THRESHOLDS } from '../config';

const parseSensorData = (raw: any, activeVehicleId: string): SensorData | null => {
  const vehicle_id = raw.vehicle_id || 'V-001';
  if (vehicle_id !== activeVehicleId) return null;

  return {
    time: raw.time || new Date(Number(raw.stream_id?.split('-')[0] || Date.now())).toLocaleTimeString(),
    accelX: raw.acc_x_mg || 0,
    accelY: raw.acc_y_mg || 0,
    accelZ: raw.acc_z_mg || 0,
    gyroX: raw.gyr_x_mdps || 0,
    gyroY: raw.gyr_y_mdps || 0,
    gyroZ: raw.gyr_z_mdps || 0,
    magX: raw.mag_x_mgauss || 0,
    magY: raw.mag_y_mgauss || 0,
    magZ: raw.mag_z_mgauss || 0,
    pressure: raw.press_hpa || 0,
    temperature: Number(raw.temp || raw.temperature || raw.roll_deg) || 0,
    pitch: raw.pitch_deg || 0,
    roll: raw.roll_deg || 0,
  };
};

const checkEmergency = (data: SensorData): boolean => {
  return Math.abs(data.gyroZ) > SENSOR_THRESHOLDS.GYRO_Z_MAX || 
         Math.abs(data.accelZ) < SENSOR_THRESHOLDS.ACCEL_Z_MIN;
};

export const useSensorStream = (activeVehicleId: string | null) => {
  const [dataStream, setDataStream] = useState<SensorData[]>([]);
  const [currentData, setCurrentData] = useState<SensorData | null>(null);
  const [isEmergency, setIsEmergency] = useState<boolean>(false);

  useEffect(() => {
    if (!activeVehicleId) return;

    const source = new EventSource(`${API_BASE_URL}/stream`);
    let currentStream: SensorData[] = [];

    source.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        const newPoint = parseSensorData(raw, activeVehicleId);
        
        if (newPoint) {
          currentStream = [...currentStream, newPoint].slice(-HISTORY_COUNT);
          setDataStream(currentStream);
          setCurrentData(newPoint);
          
          if (checkEmergency(newPoint)) {
            setIsEmergency(true);
          }
        }
      } catch (err) {
        // Ignore keepalive or parse errors
      }
    };

    source.onerror = (err) => {
      console.error("SSE Error:", err);
    };

    return () => {
      source.close();
    };
  }, [activeVehicleId]);

  const resetEmergency = () => setIsEmergency(false);

  console.log("useSensorStream state:", { activeVehicleId, dataStreamLength: dataStream.length, currentData });

  return { 
    dataStream, 
    currentData, 
    isEmergency, 
    resetEmergency 
  };
};

