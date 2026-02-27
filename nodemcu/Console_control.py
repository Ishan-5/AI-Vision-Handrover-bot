import cv2
import mediapipe as mp
import socket
import math
import numpy as np

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

# ==== Function to calculate palm center ====
def calculate_palm_center(hand_landmarks):
    """Calculate the center of the palm using key landmarks"""
    landmarks = hand_landmarks.landmark
    
    # Use wrist and base of fingers to calculate palm center
    wrist = landmarks[0]
    thumb_base = landmarks[1]
    index_base = landmarks[5]
    middle_base = landmarks[9]
    ring_base = landmarks[13]
    pinky_base = landmarks[17]
    
    # Calculate average position
    center_x = (wrist.x + thumb_base.x + index_base.x + middle_base.x + ring_base.x + pinky_base.x) / 6
    center_y = (wrist.y + thumb_base.y + index_base.y + middle_base.y + ring_base.y + pinky_base.y) / 6
    
    return center_x, center_y

# ==== Function to define screen regions ====
def define_regions(frame_width, frame_height):
    """Define 5 regions: center rectangle and 4 trapeziums"""
    
    # Center rectangle (50% of screen width and height) - BIGGER STOP AREA
    center_margin_x = int(frame_width * 0.25)
    center_margin_y = int(frame_height * 0.25)
    
    center_rect = {
        'x1': center_margin_x,
        'y1': center_margin_y,
        'x2': frame_width - center_margin_x,
        'y2': frame_height - center_margin_y
    }
    
    regions = {
        'CENTER': center_rect,
        'UP': {  # Trapezium above center
            'points': np.array([[0, 0], [frame_width, 0], 
                               [center_rect['x2'], center_rect['y1']], 
                               [center_rect['x1'], center_rect['y1']]], np.int32)
        },
        'DOWN': {  # Trapezium below center
            'points': np.array([[center_rect['x1'], center_rect['y2']], 
                               [center_rect['x2'], center_rect['y2']], 
                               [frame_width, frame_height], 
                               [0, frame_height]], np.int32)
        },
        'LEFT': {  # Trapezium left of center
            'points': np.array([[0, 0], [center_rect['x1'], center_rect['y1']], 
                               [center_rect['x1'], center_rect['y2']], 
                               [0, frame_height]], np.int32)
        },
        'RIGHT': {  # Trapezium right of center
            'points': np.array([[center_rect['x2'], center_rect['y1']], 
                               [frame_width, 0], 
                               [frame_width, frame_height], 
                               [center_rect['x2'], center_rect['y2']]], np.int32)
        }
    }
    
    return regions

# ==== Function to detect which region palm is in ====
def detect_region(palm_x, palm_y, regions, frame_width, frame_height):
    """Detect which region the palm center is in"""
    
    # Convert normalized coordinates to pixel coordinates
    pixel_x = int(palm_x * frame_width)
    pixel_y = int(palm_y * frame_height)
    
    # Check center rectangle first
    center = regions['CENTER']
    if (center['x1'] <= pixel_x <= center['x2'] and 
        center['y1'] <= pixel_y <= center['y2']):
        return "STOP"
    
    # Check trapeziums using point-in-polygon test
    point = (pixel_x, pixel_y)
    
    if cv2.pointPolygonTest(regions['UP']['points'], point, False) >= 0:
        return "FORWARD"
    elif cv2.pointPolygonTest(regions['DOWN']['points'], point, False) >= 0:
        return "BACKWARD"
    elif cv2.pointPolygonTest(regions['LEFT']['points'], point, False) >= 0:
        return "LEFT"
    elif cv2.pointPolygonTest(regions['RIGHT']['points'], point, False) >= 0:
        return "RIGHT"
    
    return "STOP"  # Default to stop if not in any region

# ==== Function to draw regions on frame ====
def draw_regions(frame, regions):
    """Draw region boundaries on the frame"""
    
    # Draw center rectangle
    center = regions['CENTER']
    cv2.rectangle(frame, (center['x1'], center['y1']), 
                  (center['x2'], center['y2']), (0, 255, 0), 2)
    cv2.putText(frame, "STOP", (center['x1'] + 20, center['y1'] + 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    # Draw trapeziums
    cv2.polylines(frame, [regions['UP']['points']], True, (255, 0, 0), 2)
    cv2.putText(frame, "FORWARD", (frame.shape[1]//2 - 50, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    cv2.polylines(frame, [regions['DOWN']['points']], True, (255, 0, 0), 2)
    cv2.putText(frame, "BACKWARD", (frame.shape[1]//2 - 60, frame.shape[0] - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    cv2.polylines(frame, [regions['LEFT']['points']], True, (255, 0, 0), 2)
    cv2.putText(frame, "LEFT", (20, frame.shape[0]//2), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    cv2.polylines(frame, [regions['RIGHT']['points']], True, (255, 0, 0), 2)
    cv2.putText(frame, "RIGHT", (frame.shape[1] - 100, frame.shape[0]//2), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

# ==== Enhanced gesture recognition for speed control ====
def check_speed_control(hand_landmarks):
    """Check for speed control gesture (thumb + index up, others down)"""
    landmarks = hand_landmarks.landmark
    fingers = []

    # Thumb (check horizontal position)
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
        min_distance = 0.02  # Minimum pinch distance (0% speed)
        max_distance = 0.25  # Maximum pinch distance (100% speed)
        
        # Clamp the distance within our range
        clamped_distance = max(min_distance, min(max_distance, pinch_distance))
        
        # Convert to speed percentage
        speed_percentage = ((clamped_distance - min_distance) / (max_distance - min_distance)) * 100
        speed_percentage = max(0, min(100, speed_percentage))
        
        # Convert to speed command (0-9 for 0-90%, 'q' for 100%)
        if speed_percentage >= 100:
            speed_command = "q"
        else:
            speed_command = str(int(speed_percentage // 10))
        
        return True, speed_command, speed_percentage, pinch_distance
    
    return False, None, None, None

# ==== Main loop ====
cap = cv2.VideoCapture(0)
last_speed_command = "None"
last_direction_command = "STOP"

print("🎮 Palm Position Gesture Control Started!")
print("📋 Control Method:")
print("   - Move palm to different screen regions:")
print("     • Center rectangle: STOP")
print("     • Top trapezium: FORWARD") 
print("     • Bottom trapezium: BACKWARD")
print("     • Left trapezium: LEFT")
print("     • Right trapezium: RIGHT")
print("   - Speed Control: Thumb + Index pinch (other fingers curled)")
print("   - Press ESC to quit")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame_height, frame_width = frame.shape[:2]
    
    # Define regions for current frame
    regions = define_regions(frame_width, frame_height)
    
    # Draw regions on frame
    draw_regions(frame, regions)
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Calculate palm center
            palm_x, palm_y = calculate_palm_center(hand_landmarks)
            
            # Draw palm center
            palm_pixel_x = int(palm_x * frame_width)
            palm_pixel_y = int(palm_y * frame_height)
            cv2.circle(frame, (palm_pixel_x, palm_pixel_y), 10, (0, 0, 255), -1)
            cv2.putText(frame, "PALM", (palm_pixel_x + 15, palm_pixel_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Check for speed control
            is_speed_control, speed_command, speed_percentage, pinch_distance = check_speed_control(hand_landmarks)
            
            if is_speed_control:
                # Speed control mode
                cv2.putText(frame, f"SPEED CONTROL: {speed_percentage:.1f}%", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.putText(frame, f"Speed Command: {speed_command}", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                cv2.putText(frame, f"Pinch Distance: {pinch_distance:.3f}", (10, 110), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                print(f"🎛️  Speed: {speed_percentage:.1f}% | Command: {speed_command}")
                
                try:
                    sock.sendto(speed_command.encode(), (ESP32_IP, ESP32_PORT))
                    last_speed_command = speed_command
                    print(f"📤 Sent speed '{speed_command}' to ESP32")
                except Exception as e:
                    print(f"❌ Failed to send speed: {e}")
            else:
                # Direction control mode using palm position
                direction = detect_region(palm_x, palm_y, regions, frame_width, frame_height)
                
                cv2.putText(frame, f"Direction: {direction}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(frame, f"Palm Position: ({palm_x:.2f}, {palm_y:.2f})", (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                print(f"🤚 Direction: {direction} | Palm: ({palm_x:.2f}, {palm_y:.2f})")
                
                try:
                    sock.sendto(direction.encode(), (ESP32_IP, ESP32_PORT))
                    last_direction_command = direction
                    print(f"📤 Sent direction '{direction}' to ESP32")
                except Exception as e:
                    print(f"❌ Failed to send direction: {e}")
    else:
        cv2.putText(frame, "No hand detected", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    # Add status information
    cv2.putText(frame, "ESC to quit", (frame_width - 150, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, f"Last Speed: {last_speed_command}", (frame_width - 200, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    cv2.putText(frame, f"Last Direction: {last_direction_command}", (frame_width - 250, 90), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

    cv2.imshow("Palm Position Gesture Control", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
sock.close()
print("👋 Palm position gesture control stopped")