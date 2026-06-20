import { useState } from 'react';
import styles from './App.module.css';
import { VehicleList } from './components/VehicleList';
import { TelemetryDashboard } from './components/TelemetryDashboard';
import { EmergencyAlert } from './components/EmergencyAlert';
import { useSensorStream } from './hooks/useSensorStream';

const INITIAL_VEHICLES = [
  { id: 'V-001', name: 'Cybertruck Unit Alpha', status: 'healthy' as const },
  { id: 'V-002', name: 'Ambulance 12', status: 'healthy' as const },
  { id: 'V-003', name: 'Fire Engine 4', status: 'healthy' as const },
];

function App() {
  const [activeVehicleId, setActiveVehicleId] = useState('V-001');
  
  // Custom hook simulating streaming data for the active vehicle
  const { dataStream, currentData, isEmergency, resetEmergency } = useSensorStream(true);

  // Update vehicle status in the list based on the emergency state
  const vehicles = INITIAL_VEHICLES.map(v => {
    if (v.id === activeVehicleId && isEmergency) {
      return { ...v, status: 'emergency' as const };
    }
    return v;
  });

  const activeVehicle = vehicles.find(v => v.id === activeVehicleId)!;

  return (
    <div className={styles.appLayout}>
      <VehicleList 
        vehicles={vehicles} 
        activeId={activeVehicleId} 
        onSelect={setActiveVehicleId} 
      />
      
      <TelemetryDashboard 
        vehicleName={activeVehicle.name}
        isEmergency={isEmergency}
        currentData={currentData}
        dataStream={dataStream}
      />

      {isEmergency && (
        <EmergencyAlert 
          vehicleName={activeVehicle.name} 
          onDismiss={resetEmergency} 
        />
      )}
    </div>
  );
}

export default App;
