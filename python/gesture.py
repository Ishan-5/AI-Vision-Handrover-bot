import cv2
import mediapipe as mp
import socket
import math

# ==== UDP setup ====
ESP32_IP = "192.168.4.1"   # ESP32 AP mode default IP
ESP32_PORT = 1234          # UDP port (must match ESP32)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Test connection
try:
    test_msg = "CONNECTION_TEST"
    sock.sendto(test_msg.encode(), (ESP32_IP, ESP32_PORT))
    print(f"✅ Connected to ESP32 at {ESP32_IP}:{ESP32_PORT}")
except Exception as e:
    print(f"❌ Failed to connect to ESP32: {e}")
    print("Make sure ESP32 is running and accessible")

# ==== Mediapipe setup ====
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)

# ==== Helper function to calculate distance between two points ====
def calculate_distance(point1, point2):
    """Calculate Euclidean distance between two landmark points"""
    return math.sqrt((point1.x - point2.x)**2 + (point1.y - point2.y)**2)

# ==== Enhanced gesture recognition function ====
def recognize_gesture(hand_landmarks):
    landmarks = hand_landmarks.landmark
    fingers = []

    # Thumb (check horizontal position - thumb extends to the right)
    # When thumb is out (extended): tip_x < joint_x, so return 1
    # When thumb is in (curled): tip_x > joint_x, so return 0
    fingers.append(1 if landmarks[4].x < landmarks[3].x else 0)
    
    # Other 4 fingers
    for tip_id in [8, 12, 16, 20]:
        fingers.append(1 if landmarks[tip_id].y < landmarks[tip_id - 2].y else 0)

    # Check for speed control trigger (ONLY thumb up + index finger up, others curled)
    thumb_up = fingers[0] == 1
    index_up = fingers[1] == 1
    middle_down = fingers[2] == 0
    ring_down = fingers[3] == 0
    pinky_down = fingers[4] == 0
    
    # Speed control trigger: thumb + index up, all others down
    if thumb_up and index_up and middle_down and ring_down and pinky_down:
        # Calculate pinch distance between thumb tip and index finger tip
        thumb_tip = landmarks[4]  # Thumb tip
        index_tip = landmarks[8]  # Index finger tip
        pinch_distance = calculate_distance(thumb_tip, index_tip)
        
        # Map pinch distance to speed (0-100%)
        # Increased range for better control
        min_distance = 0.02  # Minimum pinch distance (0% speed)
        max_distance = 0.25  # Maximum pinch distance (100% speed) - increased range
        
        # Clamp the distance within our range
        clamped_distance = max(min_distance, min(max_distance, pinch_distance))
        
        # Convert to speed percentage (normal - smaller distance = lower speed, larger distance = higher speed)
        speed_percentage = ((clamped_distance - min_distance) / (max_distance - min_distance)) * 100
        speed_percentage = max(0, min(100, speed_percentage))  # Ensure 0-100 range
        
        # Convert to speed command (0-9 for 0-90%, 'q' for 100%)
        if speed_percentage >= 100:
            speed_command = "q"
        else:
            speed_command = str(int(speed_percentage // 10))
        
        return "SPEED", fingers, speed_command, speed_percentage, pinch_distance
    
    # Regular gesture recognition
    if fingers == [0,1,0,0,0]:
        return "FORWARD", fingers, None, None, None
    elif fingers == [0,1,1,0,0]:
        return "LEFT", fingers, None, None, None
    elif fingers == [0,1,1,1,0]:
        return "RIGHT", fingers, None, None, None
    elif fingers == [0,1,1,1,1]:
        return "BACKWARD", fingers, None, None, None
    elif fingers == [0,0,0,0,0]:
        return "STOP", fingers, None, None, None
    else:
        return "STOP", fingers, None, None, None

# ==== Webcam loop ====
cap = cv2.VideoCapture(0)
last_speed_command = "None"  # Track the last speed command sent

print("🎮 Enhanced Gesture Control Started!")
print("📋 Gestures:")
print("   - Index finger: FORWARD")
print("   - Index + Middle: LEFT") 
print("   - Index + Middle + Ring: RIGHT")
print("   - All fingers: BACKWARD")
print("   - Fist: STOP")
print("   - Thumb + Index: SPEED CONTROL (pinch to adjust)")
print("   - Press ESC to quit")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            gesture_result = recognize_gesture(hand_landmarks)
            gesture, fingers = gesture_result[0], gesture_result[1]
            speed_command = gesture_result[2] if len(gesture_result) > 2 else None
            speed_percentage = gesture_result[3] if len(gesture_result) > 3 else None
            pinch_distance = gesture_result[4] if len(gesture_result) > 4 else None

            # Display gesture on screen
            if gesture == "SPEED":
                # Speed control mode
                cv2.putText(frame, f"SPEED CONTROL: {speed_percentage:.1f}%", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.putText(frame, f"Command: {speed_command}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                cv2.putText(frame, f"Pinch Distance: {pinch_distance:.3f}", (10, 110), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(frame, f"Fingers: {fingers}", (10, 140), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                print(f"🎛️  Speed: {speed_percentage:.1f}% | Command: {speed_command} | Distance: {pinch_distance:.3f}")
                
                try:
                    sock.sendto(speed_command.encode(), (ESP32_IP, ESP32_PORT))
                    last_speed_command = speed_command  # Update last speed command
                    print(f"📤 Sent speed '{speed_command}' to ESP32")
                except Exception as e:
                    print(f"❌ Failed to send speed: {e}")
                    
            elif gesture:
                # Regular gesture mode
                cv2.putText(frame, f"Gesture: {gesture}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(frame, f"Fingers: {fingers}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                print(f"🤚 Gesture: {gesture} | Fingers: {fingers}")
                
                try:
                    sock.sendto(gesture.encode(), (ESP32_IP, ESP32_PORT))
                    print(f"📤 Sent '{gesture}' to ESP32")
                except Exception as e:
                    print(f"❌ Failed to send gesture: {e}")
            else:
                cv2.putText(frame, "No gesture detected", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(frame, f"Fingers: {fingers}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                print(f"❓ No recognized gesture | Fingers: {fingers}")
    else:
        cv2.putText(frame, "No hand detected", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    # Add instructions and last speed command on screen
    cv2.putText(frame, "ESC to quit", (frame.shape[1] - 150, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, f"Last Speed: {last_speed_command}", (frame.shape[1] - 200, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    cv2.imshow("Enhanced Hand Gesture Control", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
sock.close()
print("👋 Enhanced gesture control stopped")