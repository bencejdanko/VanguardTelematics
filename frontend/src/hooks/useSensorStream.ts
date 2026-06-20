import { useState, useEffect } from 'react';

export interface SensorData {
  time: string;
  accelX: number;
  accelY: number;
  accelZ: number;
  gyroX: number;
  gyroY: number;
  gyroZ: number;
  magX: number;
  magY: number;
  magZ: number;
  pressure: number;
  temperature: number;
  pitch: number;
  roll: number;
}

export const useSensorStream = (activeVehicleId: string | null) => {
  const [streams, setStreams] = useState<Record<string, SensorData[]>>({});
  const [currentData, setCurrentData] = useState<Record<string, SensorData | null>>({});
  const [emergencies, setEmergencies] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const source = new EventSource('http://localhost:8000/stream');

    source.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data);
        const vehicle_id = raw.vehicle_id || 'V-001';
        
        const nextPoint: SensorData = {
          time: raw.time || new Date().toLocaleTimeString(),
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

        // Emergency threshold check
        if (Math.abs(nextPoint.gyroZ) > 8000 || Math.abs(nextPoint.accelZ) < 500) {
          setEmergencies(prev => ({ ...prev, [vehicle_id]: true }));
        }

        setCurrentData(prev => ({ ...prev, [vehicle_id]: nextPoint }));
        
        setStreams((prev) => {
          const stream = prev[vehicle_id] || [];
          const newStream = [...stream, nextPoint];
          if (newStream.length > 50) return { ...prev, [vehicle_id]: newStream.slice(newStream.length - 50) };
          return { ...prev, [vehicle_id]: newStream };
        });
      } catch (err) {
        console.error("Error parsing SSE data:", err);
      }
    };

    source.onerror = (err) => {
      console.error("SSE connection error:", err);
    };

    return () => {
      source.close();
    };
  }, []);

  const resetEmergency = (vId: string) => {
    setEmergencies(prev => ({ ...prev, [vId]: false }));
  };

  if (!activeVehicleId) {
    return { dataStream: [], currentData: null, isEmergency: false, resetEmergency: () => {} };
  }

  return { 
    dataStream: streams[activeVehicleId] || [], 
    currentData: currentData[activeVehicleId] || null, 
    isEmergency: emergencies[activeVehicleId] || false, 
    resetEmergency: () => resetEmergency(activeVehicleId) 
  };
};
