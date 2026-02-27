# AI Vision HandRover Bot

## Overview

AI Vision HandRover Bot is a real-time gesture-controlled robot that integrates computer vision, wireless communication, and embedded motor control. The system detects hand gestures using OpenCV and MediaPipe and wirelessly controls an ESP8266-based robot via UDP communication.

---

## Tech Stack

- Python
- OpenCV
- MediaPipe (Hand Landmark Detection)
- ESP8266 (NodeMCU)
- L298N Motor Driver
- UDP & HTTP Communication
- Arduino IDE

---

## System Architecture

Camera → OpenCV → MediaPipe (21 Hand Landmarks) → Gesture Classification → UDP Transmission → ESP8266 → Motor Driver → Robot Movement

---

## Key Features

- Real-time hand tracking (30 FPS)
- 21-point hand landmark detection
- Custom finger-count gesture classification
- Dual protocol communication (UDP + HTTP)
- ~50–100 ms end-to-end latency
- PWM-based motor speed control

---

## Gesture Mapping

| Gesture | Command |
|---------|----------|
| 1 Finger | Forward |
| 2 Fingers | Backward |
| 3 Fingers | Left |
| 4 Fingers | Right |
| Fist / 5 Fingers | Stop |

---

## Hardware Components

- ESP8266 NodeMCU
- L298N Motor Driver
- 4x BO Motors
- 4x Wheels
- 3S 18650 Battery Pack
- Chassis
- Jumper Wires

---

## How It Works

1. OpenCV captures live camera feed.
2. MediaPipe detects 21 hand landmarks.
3. Gesture classification logic interprets finger positions.
4. Python sends movement command via UDP.
5. ESP8266 receives command and controls motors using L298N.
6. Robot moves in real time.

---

## Results

- Stable real-time performance at ~30 FPS.
- Low latency communication (~50–100 ms).
- Dual control support (AI gesture + WiFi manual app).

---

## Future Improvements

- Add obstacle avoidance using ultrasonic sensors
- Implement speed control via gesture intensity
- Upgrade to ESP32 for higher processing capability
- Integrate onboard camera processing
