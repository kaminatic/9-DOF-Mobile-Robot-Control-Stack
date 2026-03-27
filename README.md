# 6-DOF Mobile Robot Control Stack

This repository contains the software and firmware required to coordinate a **6-DOF Stewart Platform** and a **Mecanum drive** base. The system enables high-fidelity motion through a Master-Slave architecture, supporting both real-time teleoperation and timestamped gesture playback.

Motion files can be found here: https://doi.org/10.6084/m9.figshare.30625013

## ⚙️ System Architecture

The control stack is divided into two primary layers communicating via Serial at **115200 Baud**:
1.  **Operator Interface (Python):** Processes user input, manages motion profile timing, and streams 10-degrees-of-freedom pose data.
2.  **Kinematics Firmware (Arduino):** Executes Inverse Kinematics (IK) for the platform and manages PWM signals for the drive motors and servos.

---

## 🤖 Firmware Technical Details (`robot_firmware.ino`)

### 1. Kinematics & Platform Control
* **6-DOF Stewart Platform:** The firmware calculates the required angle for each of the 6 servos to achieve a requested pose ($X, Y, Z, P, R, Y$).
* **Iterative Solver:** A numerical approach (`getAlpha`) solves the IK by finding the specific servo arm angle ($\alpha$) that maintains a constant leg length ($L2$) between the base and the platform.
* **Mecanum Drive:** Implemented using a holonomic kinematic model, allowing for simultaneous translation and rotation ($X, Y, R$) by coordinating four independent DC motors.

### 2. Hardware Constraints & Sensing
The robot utilizes an HC-SR04 ultrasonic sensor for distance telemetry, subject to the following mechanical constraint:
* **Sensor Obstruction:** The robot's outer shell physically covers/obstructs the ultrasonic sensor when the Stewart Platform is in a lowered position.
* **Software Interlock:** To prevent false positives caused by internal reflections against the shell, the sensor is only polled when the platform height ($Z$) is **$\ge$ 14.5mm**.
* **Telemetry:** When active, distance data is transmitted back to the controller via the `DIST:` prefix every 150ms.

---

## 🖥️ Controller Technical Details (`controller.py`)

### 1. Data Stream Protocol
The controller streams a 10-float CSV packet to the hardware at ~100Hz. The stream follows this exact sequence:
> `X_trans, Y_trans, Z_height, Pitch, Roll, Yaw, X_speed, Y_speed, Turn_R, Turn_L`

### 2. Motion Processing
* **Interpolation:** The controller uses a `smooth_value` function to interpolate $Z$ (height) and $Pitch$ setpoints, ensuring fluid mechanical transitions and protecting the servos from high-torque instantaneous shifts.
* **Adaptive Speed Scaling:** A `replay_counter` tracks the number of executed gestures, automatically scaling the `drive_speed`, `z_speed`, and `pitch_speed` multipliers to increase robot responsiveness over time.

### 3. Replay Engine
* **Temporal Accuracy:** The engine parses `.txt` files containing timestamped pose data. It calculates the delta between recorded timestamps to ensure playback velocity matches the original movement duration.
* **Interrupt Logic:** Replays run in a separate thread and can be immediately terminated using the `ESC` key, reverting the robot to manual "Drive" mode.

---

## 📂 Repository Contents
* `robot_firmware.ino`: Arduino C++ source code (Requires `Adafruit_MotorShield` and `Adafruit_PWMServoDriver` libraries).
* `controller.py`: Python 3.x control interface (Requires `pyserial` and `pygame`).


## 🛠 Hardware Requirements
This software stack is designed for a robot utilizing:
* Arduino-compatible Microcontroller.
* Adafruit Motor Shield (v2).
* PCA9685 16-Channel PWM Servo Driver.
* HC-SR04 Ultrasonic Sensor.
* 4x Mecanum Wheels + DC Motors.
* 6x High-Torque Servos (Stewart Platform configuration).
