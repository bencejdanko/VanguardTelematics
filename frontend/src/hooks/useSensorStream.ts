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

    const fetchData = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/history?count=${HISTORY_COUNT}`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        // Data comes newest first, so we reverse it for chronological plotting
        const chronological = data.reverse();
        
        // Filter and map for the active vehicle
        const mappedData: SensorData[] = chronological
          .map((raw: any) => parseSensorData(raw, activeVehicleId))
          .filter((item: SensorData | null): item is SensorData => item !== null);

        if (mappedData.length > 0) {
          setDataStream(mappedData);
          
          const latest = mappedData[mappedData.length - 1];
          setCurrentData(latest);
          
          // Emergency threshold check on the latest point
          if (checkEmergency(latest)) {
            setIsEmergency(true);
          }
        }
      } catch (err) {
        console.error("Error fetching history:", err);
      }
    };

    // Initial fetch
    fetchData();

    // Poll at configured interval
    const interval = setInterval(fetchData, HISTORY_POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [activeVehicleId]);

  const resetEmergency = () => setIsEmergency(false);

  return { 
    dataStream, 
    currentData, 
    isEmergency, 
    resetEmergency 
  };
};
