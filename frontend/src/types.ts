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
  temperature?: number;
  pitch: number;
  roll: number;
  yaw?: number;
  gForce?: number;
}

export interface Vehicle {
  id: string;
  name: string;
  status: 'healthy' | 'warning' | 'emergency';
}
