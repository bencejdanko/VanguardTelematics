import { useState, useEffect } from 'react';
import styles from './App.module.css';
import { VehicleList } from './components/VehicleList';
import { TelemetryDashboard } from './components/TelemetryDashboard';
import { EmergencyAlert } from './components/EmergencyAlert';
import { useSensorStream } from './hooks/useSensorStream';
import { Vehicle } from './types';
import { API_BASE_URL } from './config';

function App() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [activeVehicleId, setActiveVehicleId] = useState<string | null>(null);
  
  // Custom hook tracking streaming data for all vehicles in the background
  const { dataStream, currentData, emergencyType, resetEmergency } = useSensorStream(activeVehicleId);

  // Fetch deployed vehicles on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/vehicles`)
      .then(r => r.json())
      .then(data => {
        setVehicles(data);
        if (data.length > 0 && !activeVehicleId) {
          setActiveVehicleId(data[0].id);
        }
      })
      .catch(err => console.error("Failed to fetch vehicles", err));
  }, []);

  // Sync the vehicle list status with any live emergencies from the stream
  const displayVehicles = vehicles.map(v => {
    if (v.id === activeVehicleId && emergencyType) {
      return { ...v, status: 'emergency' as const };
    }
    return v;
  });

  const activeVehicle = displayVehicles.find(v => v.id === activeVehicleId);

  return (
    <div className={styles.appLayout}>
      <VehicleList 
        vehicles={displayVehicles} 
        activeId={activeVehicleId} 
        onSelect={setActiveVehicleId} 
      />
      
      {activeVehicle ? (
        <TelemetryDashboard 
          vehicleName={activeVehicle.name}
          isEmergency={!!emergencyType}
          currentData={currentData}
          dataStream={dataStream}
        />
      ) : (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
          Loading Fleet Data...
        </div>
      )}

      {emergencyType && activeVehicle && (
        <EmergencyAlert 
          vehicleName={activeVehicle.name} 
          incidentType={emergencyType}
          onDismiss={resetEmergency} 
        />
      )}
    </div>
  );
}

export default App;
