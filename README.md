# DataLogFusion Clone

Repurposed from https://www.st.com/en/embedded-software/x-cube-mems1.html

Modified clone of the DataLogFusion firmware from STMicroElectronics:  `\x-cube-mems1\Projects\NUCLEO-F401RE\Applications\IKS5A1\DataLogFusion`


Logs to Serial port - 115200 8N1

The sampling frequency of the measurements is 100 Hz (a sampling period of 10 ms).

```c
# app_mems.c

#define ALGO_FREQ  100U /* Algorithm frequency 100Hz */
#define ALGO_PERIOD  (1000U / ALGO_FREQ) /* Algorithm period [ms] = 10ms */
```


Output format:


```bash
timestamp,acc_x_mg,acc_y_mg,acc_z_mg,gyr_x_mdps,gyr_y_mdps,gyr_z_mdps,mag_x_mgauss,mag_y_mgauss,mag_z_mgauss,press_hpa,roll_deg,pitch_deg,yaw_deg
00:02:54.60,-50,-21,996,0,210,-210,526,-162,-345,1005.83,17.68,2.88,1.12
00:02:54.61,-51,-22,997,-210,70,-210,531,-165,-345,1005.83,17.68,2.88,1.12
```

### CSV Header Summary

| Column Name | Data Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **`timestamp`** | String | `HH:MM:SS.hh` | Real-Time Clock (RTC) timestamp (Hours:Minutes:Seconds.hundredths) |
| **`acc_x_mg`** / **`y`** / **`z`** | Integer | $mg$ (milli-g) | Accelerometer axes value ($1000\text{ mg} \approx 9.81\text{ m/s}^2$) |
| **`gyr_x_mdps`** / **`y`** / **`z`** | Integer | $mdps$ | Gyroscope axes angular rate value (milli-degrees per second) |
| **`mag_x_mgauss`** / **`y`** / **`z`**| Integer | $mgauss$ | Magnetometer axes magnetic field intensity value (milli-gauss) |
| **`press_hpa`** | Float | $hPa$ | Ambient atmospheric pressure (hectopascals) |
| **`roll_deg`** | Float | Degrees | Estimated device **Roll** angle from MotionFX Sensor Fusion |
| **`pitch_deg`** | Float | Degrees | Estimated device **Pitch** angle from MotionFX Sensor Fusion |
| **`yaw_deg`** | Float | Degrees | Estimated device **Yaw** (heading) angle from MotionFX Sensor Fusion |

