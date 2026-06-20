import { useState, useEffect, useRef } from 'react';
import Papa from 'papaparse';

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

export const useSensorStream = (isActive: boolean) => {
  const [dataStream, setDataStream] = useState<SensorData[]>([]);
  const [currentData, setCurrentData] = useState<SensorData | null>(null);
  const [isEmergency, setIsEmergency] = useState(false);
  const fullDataRef = useRef<SensorData[]>([]);
  const currentIndexRef = useRef(0);

  // Load the CSV data on mount
  useEffect(() => {
    Papa.parse('/sample.csv', {
      download: true,
      header: false,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        const parsed = results.data.map((row: any) => ({
          time: String(row[0]),
          accelX: Number(row[1]),
          accelY: Number(row[2]),
          accelZ: Number(row[3]),
          gyroX: Number(row[4]),
          gyroY: Number(row[5]),
          gyroZ: Number(row[6]),
          magX: Number(row[7]),
          magY: Number(row[8]),
          magZ: Number(row[9]),
          pressure: Number(row[10]),
          temperature: Number(row[11]),
          pitch: Number(row[12]),
          roll: Number(row[13]),
        }));
        fullDataRef.current = parsed;
      },
    });
  }, []);

  // Simulate streaming
  useEffect(() => {
    if (!isActive || fullDataRef.current.length === 0) return;

    const intervalId = setInterval(() => {
      const data = fullDataRef.current;
      if (currentIndexRef.current >= data.length) {
        currentIndexRef.current = 0; // loop back for demo
      }

      const nextPoint = data[currentIndexRef.current];
      
      // Emergency logic: Z-axis gyro exceeds threshold (e.g. > 10000 or < -10000 means rolling over)
      if (Math.abs(nextPoint.gyroZ) > 8000 || Math.abs(nextPoint.accelZ) < 500) {
        setIsEmergency(true);
      }

      setCurrentData(nextPoint);
      setDataStream((prev) => {
        const newStream = [...prev, nextPoint];
        // Keep last 50 points for chart
        if (newStream.length > 50) return newStream.slice(newStream.length - 50);
        return newStream;
      });

      currentIndexRef.current += 1;
    }, 100); // 10hz update rate

    return () => clearInterval(intervalId);
  }, [isActive]);

  const resetEmergency = () => {
    setIsEmergency(false);
  };

  return { dataStream, currentData, isEmergency, resetEmergency };
};
