# DataLogFusion Clone

Repurposed from https://www.st.com/en/embedded-software/x-cube-mems1.html. Modified clone of the DataLogFusion firmware from STMicroElectronics:  `\x-cube-mems1\Projects\NUCLEO-F401RE\Applications\IKS5A1\DataLogFusion`


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

---

QNX configuration

Plug in the kit.

```bash
[qnxuser@qnxpi18 ~]$ usb -v
USB 0 (XHCI) v10.00, v1.01 DDK, v2.00 HCD, DLL: Active
    Control, Interrupt, Bulk(SG), Isoch(Stream), High Speed, Super Speed, DMA:32-bit

Device Address             : 1
Upstream Host Controller   : 0
Upstream Device Address    : 0
Upstream Port              : 1
Upstream Port Speed        : Full
Vendor                     : 0x0483 (STMicroelectronics)
Product                    : 0x374b (STM32 STLink)
Device Release             : r1.00
Class                      : 0xef (Miscellaneous)
Subclass                   : 0x02
Protocol                   : 0x01
Max PacketSize0            : 64
Configurations             : 1
  Configuration            : 1
    Attributes             : 0x80 (Bus-powered)
    Max Power              : 300 mA

USB 1 (XHCI) v10.00, v1.01 DDK, v2.00 HCD, DLL: Active
    Control, Interrupt, Bulk(SG), Isoch(Stream), High Speed, Super Speed, DMA:32-bit
```

You must configure the the driver tool to help the pi/qnx to understand the USB 

https://devblog.qnx.com/get-gps-data-on-qnx-with-a-usb-gps/

```bash
# you can request the binary from john in the discord
# or it is in the tools somewhere :D
scp devc-serusb qnxuser@172.20.10.7:/tmp/

# give permissions to the binary and configure anything active
chmod +x /tmp/devc-serusb
sudo /tmp/devc-serusb

# check what serial line the USB device is using
ls -l /dev/ser*

# ex gives me /dev/serusb1

# set the correct baud rate to that line
stty baud=115200 < /dev/serusb1

# verify 
stty < /dev/serusb1
```

# Raspberry Pi Hardware Sensor Code

We have cloned QNX's example repository for sensors: 

https://github.com/qnx/Raspberry-Pi-Hardware-Component-Samples
(pi sensor sample code)

https://gitlab.com/qnx/projects/camera-projects/applications/camera-dump-frame-no-screen
(camera sample code)

And modified for "poor mans sentry mode", where we use an infrared sensor to start a camera only when infrared activity is detected

## Wiring IR Obstacle Sensor 

Wiring: Connected VCC to 3.3V to protect the Pi's GPIO pins, GND to ground, and SIG (Signal / OUT) to GPIO 21.

```
# ssh helper shortcut 
ssh qnxuser@172.20.10.7
```
