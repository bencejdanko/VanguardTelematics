import { useState, useEffect, useRef } from 'react';
import { SensorData } from '../types';
import { API_BASE_URL, HISTORY_POLL_INTERVAL_MS, HISTORY_COUNT, SENSOR_THRESHOLDS } from '../config';

const parseSensorData = (raw: any, activeVehicleId: string): SensorData | null => {
  const vehicle_id = raw.vehicle_id || 'V-001';
  if (vehicle_id !== activeVehicleId) return null;

  return {
    time: raw.ts || new Date(Number(raw.stream_id?.split('-')[0] || Date.now())).toLocaleTimeString(),
    accelX: raw.acc_x || 0,
    accelY: raw.acc_y || 0,
    accelZ: raw.acc_z || 0,
    gyroX: raw.gyr_x || 0,
    gyroY: raw.gyr_y || 0,
    gyroZ: raw.gyr_z || 0,
    magX: raw.mag_x || 0,
    magY: raw.mag_y || 0,
    magZ: raw.mag_z || 0,
    pressure: raw.press || 0,
    // temperature: Number(raw.temp || raw.temperature || raw.roll_deg) || 0,
    pitch: raw.pitch || 0,
    roll: raw.roll || 0,
    yaw: raw.yaw || 0,
    gForce: raw.g_force || 0,
  };
};

const checkEmergency = (data: SensorData): string | null => {
  if (data.gForce && data.gForce > SENSOR_THRESHOLDS.G_FORCE_CRASH) return "High-Impact Crash";
  if (Math.abs(data.roll) > SENSOR_THRESHOLDS.ROLL_MAX || Math.abs(data.pitch) > SENSOR_THRESHOLDS.PITCH_MAX) return "Rollover";
  return null;
};

export const useSensorStream = (activeVehicleId: string | null) => {
  const [dataStream, setDataStream] = useState<SensorData[]>([]);
  const [currentData, setCurrentData] = useState<SensorData | null>(null);
  const [emergencyType, setEmergencyType] = useState<string | null>(null);
  const [v1Live, setV1Live] = useState(false);
  const acknowledgedRef = useRef(false);

  useEffect(() => {
    if (!activeVehicleId) return;

    const source = new EventSource(`${API_BASE_URL}/stream`);
    let currentStream: SensorData[] = [];
    let timeoutId: NodeJS.Timeout;

    source.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        const vehicleId = raw.vehicle_id || 'V-001';
        
        if (vehicleId === 'V-001') {
          setV1Live(true);
          clearTimeout(timeoutId);
          timeoutId = setTimeout(() => setV1Live(false), 3000);
        }

        const newPoint = parseSensorData(raw, activeVehicleId);
        
        if (newPoint) {
          currentStream = [...currentStream, newPoint].slice(-HISTORY_COUNT);
          setDataStream(currentStream);
          setCurrentData(newPoint);
          
          const incidentType = checkEmergency(newPoint);
          if (incidentType) {
            if (!acknowledgedRef.current) {
              setEmergencyType(incidentType);
            }
          } else {
            acknowledgedRef.current = false;
            setEmergencyType(null);
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
      clearTimeout(timeoutId);
      source.close();
    };
  }, [activeVehicleId]);

  const resetEmergency = () => {
    setEmergencyType(null);
    acknowledgedRef.current = true;
  };

  return { 
    dataStream, 
    currentData, 
    emergencyType, 
    resetEmergency,
    v1Live
  };
};

