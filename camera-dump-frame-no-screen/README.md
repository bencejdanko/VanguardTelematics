# camera-dump-frame-no-screen

This example source code shows how you receives a frame from the sensor service and dump raw frames to disk.

### How to build

QNX SDP 8.0 is required. SDP and required packages can be installed with QNX Software Center.

Required package:

- com.qnx.qnx800.target.sf.base.group

Run the following commands to build the application:
```bash
# Clone the repos
mkdir -p ~/qnx_workspace && cd qnx_workspace
git clone https://gitlab.com/qnx/projects/camera-projects/applications/camera-dump-frame-no-screen.git

# Build camera-dump-frame-no-screen
cd camera-dump-frame-no-screen
make install
```

### How to run
```bash
# scp libraries and tests to the target (note, mDNS is configured from
# /boot/qnx_config.txt and uses qnxpi.local by default).
TARGET_HOST=<target-ip-address-or-hostname>

# scp the built binary over to your QNX target
scp ./nto/aarch64/o.le/camera-dump-frame-no-screen qnxuser@$TARGET_HOST:/data/home/qnxuser/bin

# ssh into the target
ssh qnxuser@$TARGET_HOST

# Make sure sensor service is running
# Run "pidin ar | grep sensor" to see if sensor is running, if not run this as root:
# su
# sensor -U 521:521,1000 -b external -r /data/share/sensor -c /system/etc/config/camera_module3.conf

# Run
camera-dump-frame-no-screen
