import { useState, useEffect } from 'react';
import { SensorData } from '../types';
import { API_BASE_URL, SENSOR_THRESHOLDS } from '../config';

const parseSensorData = (raw: any): SensorData => {
  return {
    time: raw.time || raw.ts || raw.timestamp || new Date().toLocaleTimeString(),
    accelX: Number(raw.acc_x_mg !== undefined ? raw.acc_x_mg : raw.acc_x) || 0,
    accelY: Number(raw.acc_y_mg !== undefined ? raw.acc_y_mg : raw.acc_y) || 0,
    accelZ: Number(raw.acc_z_mg !== undefined ? raw.acc_z_mg : raw.acc_z) || 0,
    gyroX: Number(raw.gyr_x_mdps !== undefined ? raw.gyr_x_mdps : raw.gyr_x) || 0,
    gyroY: Number(raw.gyr_y_mdps !== undefined ? raw.gyr_y_mdps : raw.gyr_y) || 0,
    gyroZ: Number(raw.gyr_z_mdps !== undefined ? raw.gyr_z_mdps : raw.gyr_z) || 0,
    magX: Number(raw.mag_x_mgauss !== undefined ? raw.mag_x_mgauss : raw.mag_x) || 0,
    magY: Number(raw.mag_y_mgauss !== undefined ? raw.mag_y_mgauss : raw.mag_y) || 0,
    magZ: Number(raw.mag_z_mgauss !== undefined ? raw.mag_z_mgauss : raw.mag_z) || 0,
    pressure: Number(raw.press_hpa !== undefined ? raw.press_hpa : raw.press) || 0,
    temperature: Number(raw.temp !== undefined ? raw.temp : (raw.temperature !== undefined ? raw.temperature : (raw.roll_deg !== undefined ? raw.roll_deg : raw.roll))) || 0,
    pitch: Number(raw.pitch_deg !== undefined ? raw.pitch_deg : raw.pitch) || 0,
    roll: Number(raw.roll_deg !== undefined ? raw.roll_deg : raw.roll) || 0,
  };
};

const checkEmergency = (data: SensorData): boolean => {
  return Math.abs(data.gyroZ) > SENSOR_THRESHOLDS.GYRO_Z_MAX || 
         Math.abs(data.accelZ) < SENSOR_THRESHOLDS.ACCEL_Z_MIN;
};

export const useSensorStream = (activeVehicleId: string | null) => {
  const [streams, setStreams] = useState<Record<string, SensorData[]>>({});
  const [currentDataMap, setCurrentDataMap] = useState<Record<string, SensorData | null>>({});
  const [emergencies, setEmergencies] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let source: EventSource | null = null;
    let isMounted = true;

    const initStream = async () => {
      try {
        // 1. Fetch history first (up to 100 entries)
        const res = await fetch(`${API_BASE_URL}/history?count=100`);
        const historyData = await res.json();
        
        if (!isMounted) return;

        const initialStreams: Record<string, SensorData[]> = {};
        const initialCurrentData: Record<string, SensorData | null> = {};
        const initialEmergencies: Record<string, boolean> = {};

        // History comes newest-first, so reverse it to show oldest-first (chronological order)
        const reversedHistory = [...historyData].reverse();

        for (const raw of reversedHistory) {
          const vehicle_id = raw.vehicle_id || 'V-001';
          const point = parseSensorData(raw);

          if (!initialStreams[vehicle_id]) {
            initialStreams[vehicle_id] = [];
          }
          initialStreams[vehicle_id].push(point);
          initialCurrentData[vehicle_id] = point;

          // Check emergency thresholds for history entries
          if (checkEmergency(point)) {
            initialEmergencies[vehicle_id] = true;
          }
        }

        // Limit each vehicle's stream array size to 100
        for (const vehicle_id in initialStreams) {
          if (initialStreams[vehicle_id].length > 100) {
            initialStreams[vehicle_id] = initialStreams[vehicle_id].slice(initialStreams[vehicle_id].length - 100);
          }
        }

        setStreams(initialStreams);
        setCurrentDataMap(initialCurrentData);
        setEmergencies(initialEmergencies);
      } catch (err) {
        console.error("Failed to load telemetry history:", err);
      }

      if (!isMounted) return;

      // 2. Start SSE Stream for real-time updates
      source = new EventSource(`${API_BASE_URL}/stream`);

      source.onmessage = (e) => {
        try {
          const raw = JSON.parse(e.data);
          const vehicle_id = raw.vehicle_id || 'V-001';
          const nextPoint = parseSensorData(raw);

          // Emergency threshold check
          if (checkEmergency(nextPoint)) {
            setEmergencies(prev => ({ ...prev, [vehicle_id]: true }));
          }

          setCurrentDataMap(prev => ({ ...prev, [vehicle_id]: nextPoint }));
          
          setStreams((prev) => {
            const stream = prev[vehicle_id] || [];
            const newStream = [...stream, nextPoint];
            if (newStream.length > 100) return { ...prev, [vehicle_id]: newStream.slice(newStream.length - 100) };
            return { ...prev, [vehicle_id]: newStream };
          });
        } catch (err) {
          console.error("Error parsing SSE data:", err);
        }
      };

      source.onerror = (err) => {
        console.error("SSE connection error:", err);
      };
    };

    initStream();

    return () => {
      isMounted = false;
      if (source) {
        source.close();
      }
    };
  }, []);

  const resetEmergency = () => {
    if (activeVehicleId) {
      setEmergencies(prev => ({ ...prev, [activeVehicleId]: false }));
    }
  };

  const dataStream = activeVehicleId ? (streams[activeVehicleId] || []) : [];
  const currentData = activeVehicleId ? (currentDataMap[activeVehicleId] || null) : null;
  const isEmergency = activeVehicleId ? (emergencies[activeVehicleId] || false) : false;

  return { 
    dataStream, 
    currentData, 
    isEmergency, 
    resetEmergency 
  };
};
