import serial
import time
import pygame
import threading
from datetime import datetime
6

SERIAL_PORT = r"\\.\COM13"
BAUD = 115200

MOVEMENT_FILES = [
    "AC.txt", "SC1.txt", "SA1.txt", "AC.txt", "NN.txt", "CS.txt", "SA.txt",
    "AE.txt"
]


latest_distance = None

z_current = 20.0
z_target = 20.0

pitch_current = -5.0
pitch_target = -5.0

drive_speed = 0.85
z_speed = 3.0
pitch_speed = 2.0

TURN_SPEED = 1.2  # High constant speed for turning in place

mode = "drive"
cancel_replay = False
replay_counter = 0

serial_lock = threading.Lock()

def open_serial():
    return serial.Serial(SERIAL_PORT, BAUD, timeout=2, write_timeout=2)

def parse_timestamp(ts):
    return datetime.strptime(ts, "%Y%m%d_%H%M%S.%f")

def send_line(ser, line):
    with serial_lock:
        ser.write((line + "\n").encode("utf-8"))
        ser.flush()

def listen_ultrasonic(ser):
    global latest_distance
    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line.startswith("DIST:"):
                latest_distance = float(line[5:])
        except:
            time.sleep(0.01)

def smooth_value(current, target, speed, dt):
    diff = target - current
    step = speed * dt
    if abs(diff) <= step:
        return target
    return current + step if diff > 0 else current - step

def drive_and_control_loop(ser, screen):
    global z_target, pitch_target, mode, cancel_replay
    global drive_speed, z_speed, pitch_speed
    global z_current, pitch_current

    last_sent = None
    last_us_print = time.time()
    font = pygame.font.SysFont("Arial", 20)

    prev_time = time.time()

    while True:
        now = time.time()
        dt = now - prev_time
        prev_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    cancel_replay = True
                    mode = "drive"
                    print("🛑 Replay canceled. Returning to drive mode.")

        keys = pygame.key.get_pressed()

        xW, yW, turnL, turnR = 0.0, 0.0, 0.0, 0.0

        if mode == "drive":
            z_target = 20.0
            pitch_target = -5.0

            if keys[pygame.K_UP]:
                yW = drive_speed * 0.6
            elif keys[pygame.K_DOWN]:
                yW = -drive_speed * 0.6

            if keys[pygame.K_LEFT]:
                xW = -drive_speed
            elif keys[pygame.K_RIGHT]:
                xW = drive_speed

            # Turning in place with high speed
            if keys[pygame.K_q]:
                turnL = TURN_SPEED
            if keys[pygame.K_e]:
                turnR = TURN_SPEED

            # Log distance but do not stop movement
            if latest_distance is not None and latest_distance <= 15.0 and yW > 0:
                print(f"🛑 Obstacle at {latest_distance:.2f} cm. (Forward motion allowed)")

            # Check for replay keys
            for i in range(8):
                if keys[pygame.K_1 + i]:
                    mode = "replay"
                    threading.Thread(target=play_replay, args=(i, ser, screen), daemon=True).start()
                    time.sleep(0.2)

            if keys[pygame.K_s]:
                mode = "lower_z"
                z_target = -5.0

        elif mode == "lower_z":
            if keys[pygame.K_UP] or keys[pygame.K_DOWN] or keys[pygame.K_LEFT] or keys[pygame.K_RIGHT] or keys[pygame.K_q] or keys[pygame.K_e]:
                mode = "drive"

        # Smooth transition
        z_current = smooth_value(z_current, z_target, z_speed, dt)
        pitch_current = smooth_value(pitch_current, pitch_target, pitch_speed, dt)

        # Always send pose
        output = f"0.00, 0.00, {z_current:.2f}, {pitch_current:.2f}, 0.00, 0.00, {xW:.2f}, {yW:.2f}, {turnR:.2f}, {turnL:.2f}"

        if output != last_sent:
            send_line(ser, output)
            last_sent = output

        if latest_distance is not None and (time.time() - last_us_print) > 1.0:
            print(f"📏 Ultrasonic: {latest_distance:.2f} cm")
            last_us_print = time.time()

        # Draw window
        screen.fill((0, 0, 0))
        status = f"Mode: {mode} | Z: {z_current:.2f} | Pitch: {pitch_current:.2f}"
        text = font.render(status, True, (255, 255, 255))
        screen.blit(text, (10, 10))
        pygame.display.flip()

        time.sleep(0.01)

def play_replay(index, ser, screen):
    global mode, cancel_replay, z_target, pitch_target
    global drive_speed, z_speed, pitch_speed
    global z_current, pitch_current
    global replay_counter

    mode = "replay"
    cancel_replay = False

    try:
        with open(MOVEMENT_FILES[index], "r") as f:
            lines = f.readlines()

        if not lines:
            print("⚠️ Empty file.")
            mode = "drive"
            return

        first_z = float(lines[0].split(",")[3])
        first_pitch = float(lines[0].split(",")[4])
        z_target = first_z
        pitch_target = first_pitch

        print(f"▶️ Replay {index + 1}: transitioning to Z={first_z}, Pitch={first_pitch}")

        while (abs(z_current - z_target) > 0.1 or abs(pitch_current - pitch_target) > 0.1) and not cancel_replay:
            dt = 0.02
            z_current = smooth_value(z_current, z_target, z_speed, dt)
            pitch_current = smooth_value(pitch_current, pitch_target, pitch_speed, dt)

            output = f"0.00, 0.00, {z_current:.2f}, {pitch_current:.2f}, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00"
            send_line(ser, output)

            time.sleep(0.02)

        first_ts = parse_timestamp(lines[0].split(",")[0])
        start_time = time.time()

        for line in lines:
            if cancel_replay:
                print("🛑 Replay stopped.")
                mode = "drive"
                return

            ts = parse_timestamp(line.split(",")[0])
            delay = (ts - first_ts).total_seconds()
            while time.time() - start_time < delay:
                time.sleep(0.001)

            payload = line.strip().split(",", 1)[-1]
            send_line(ser, payload)

    except Exception as e:
        print(f"❌ Replay error: {e}")

    finally:
        if replay_counter < 3:
            replay_counter += 1

        # Speed logic based on progression
        if replay_counter < 2:
            drive_speed = 0.85
            z_speed = 3.0
            pitch_speed = 2.0
        elif replay_counter < 3:
            drive_speed = 0.95
            z_speed = 4.0
            pitch_speed = 3.0
        else:
            drive_speed = 1.0
            z_speed = 6.0
            pitch_speed = 4.0

        z_target = 20.0
        pitch_target = -5.0
        mode = "drive"
        print("⏹️ Replay finished. Back to drive mode.")

def main():
    pygame.init()
    screen = pygame.display.set_mode((400, 100))
    pygame.display.set_caption("Robot Control")

    ser = open_serial()
    print("✅ Ready. Arrows=drive, Q/E=turn (high speed), 1-8=replay, S=lower Z, ESC=stop replay")

    threading.Thread(target=listen_ultrasonic, args=(ser,), daemon=True).start()
    drive_and_control_loop(ser, screen)

if __name__ == "__main__":
    main()
