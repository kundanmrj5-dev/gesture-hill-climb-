"""Gesture Hill Climb — webcam hand gestures drive a small Pygame vehicle.

Run: python main.py
"""

from __future__ import annotations

import math
import sys
import json
from array import array
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import cv2
import pygame

try:
    import mediapipe as mp
except ImportError:
    mp = None


WIDTH, HEIGHT = 1100, 650
FPS = 60
GROUND_Y = 490

VEHICLES = (
    {"name": "Trail Buggy", "color": (226, 73, 40), "engine": 900, "max_speed": 430, "note": "Balanced and easy to control"},
    {"name": "Mountain Truck", "color": (46, 122, 216), "engine": 1120, "max_speed": 385, "note": "Powerful on steep hills"},
    {"name": "Sprint Rover", "color": (247, 186, 40), "engine": 820, "max_speed": 510, "note": "Fast on smoother terrain"},
)

SCENES = (
    {"name": "ALPINE PASS", "sky": (96, 190, 239), "sun": (255, 224, 124), "far": (109, 151, 172), "near": (71, 117, 119), "ground": (84, 127, 45), "line": (47, 91, 33)},
    {"name": "SUNSET CANYON", "sky": (238, 129, 93), "sun": (255, 231, 142), "far": (173, 89, 78), "near": (132, 65, 55), "ground": (154, 92, 50), "line": (103, 57, 34)},
    {"name": "MIDNIGHT VALLEY", "sky": (25, 42, 94), "sun": (225, 236, 248), "far": (46, 66, 112), "near": (30, 48, 75), "ground": (40, 91, 75), "line": (23, 62, 54)},
)
COIN_POSITIONS = tuple(430 + step * 155 for step in range(220))
FUEL_POSITIONS = tuple(690 + step * 610 for step in range(56))
CLIFF_GAPS = tuple(2400 + step * 3000 for step in range(9))
SCORE_FILE = Path(__file__).with_name("high_score.json")


def terrain_y(world_x: float) -> float:
    """Original, gently varied terrain in world coordinates."""
    return (
        GROUND_Y
        + 55 * math.sin(world_x * 0.010)
        + 24 * math.sin(world_x * 0.026 + 1.3)
        + 10 * math.sin(world_x * 0.071)
    )


def terrain_slope(world_x: float) -> float:
    return (
        55 * 0.010 * math.cos(world_x * 0.010)
        + 24 * 0.026 * math.cos(world_x * 0.026 + 1.3)
        + 10 * 0.071 * math.cos(world_x * 0.071)
    )


@dataclass
class Controls:
    throttle: float = 0.0
    brake: float = 0.0
    boost: bool = False
    jump: bool = False
    restart: bool = False
    hand_found: bool = False
    message: str = "Starting camera…"


class SoundEffects:
    """Short synthesized sounds; the game still works when no audio device is available."""

    def __init__(self) -> None:
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self.sounds = {
                "start": self._tone(660, 0.14),
                "coin": self._tone(980, 0.08),
                "fuel": self._tone(460, 0.20),
                "boost": self._tone(220, 0.10),
                "jump": self._tone(540, 0.12),
                "crash": self._tone(105, 0.32),
                "checkpoint": self._tone(760, 0.16),
            }
        except pygame.error:
            pass

    @staticmethod
    def _tone(frequency: int, duration: float) -> pygame.mixer.Sound:
        frames = int(44100 * duration)
        samples = array("h", (int(0.22 * 32767 * math.sin(2 * math.pi * frequency * i / 44100) * (1 - i / frames)) for i in range(frames)))
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound:
            sound.play()


def load_high_score() -> int:
    try:
        return int(json.loads(SCORE_FILE.read_text(encoding="utf-8")).get("distance", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def save_high_score(distance: int) -> None:
    try:
        SCORE_FILE.write_text(json.dumps({"distance": distance}), encoding="utf-8")
    except OSError:
        pass


class GestureController:
    """Reads two webcam-tracked hands and converts them into driving controls."""

    def __init__(self, camera_enabled: bool = True) -> None:
        self.capture = None
        self.hands = None
        self.hand_y_history = {"Right": deque(maxlen=5), "Left": deque(maxlen=5)}
        # A palm must be raised above this resting height to activate its control.
        self.neutral_y = {"Right": 0.62, "Left": 0.62}
        self.last_hands: dict[str, float] = {}
        # Gesture confirmation makes a jump resistant to a single bad camera frame.
        self.right_open_streak = 0
        self.right_fist_streak = 0
        # A jump cannot happen at startup. The player must first show a raised,
        # open right palm, which makes accidental webcam detections harmless.
        self.right_jump_armed = False
        self.error = ""
        self.enabled = False

        if not camera_enabled:
            self.error = "Camera disabled — keyboard mode"
            return
        if mp is None:
            self.error = "MediaPipe not installed — keyboard mode"
            return
        # DirectShow prevents a long silent startup hang with many Windows webcams.
        self.capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.capture.isOpened():
            self.error = "No webcam found — keyboard mode"
            self.capture.release()
            self.capture = None
            return
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            min_detection_confidence=0.65,
            min_tracking_confidence=0.60,
        )
        self.draw = mp.solutions.drawing_utils
        self.hand_connections = mp.solutions.hands.HAND_CONNECTIONS
        self.enabled = True

    @staticmethod
    def _is_open_palm(landmarks) -> bool:
        palm = landmarks.landmark[9]
        tips = (8, 12, 16, 20)
        extended = 0
        for tip_index in tips:
            tip = landmarks.landmark[tip_index]
            if math.hypot(tip.x - palm.x, tip.y - palm.y) > 0.18:
                extended += 1
        return extended >= 3

    @staticmethod
    def _is_fist(landmarks) -> bool:
        """Return True only when at least three fingers are folded near the palm."""
        palm = landmarks.landmark[9]
        folded = 0
        for tip_index in (8, 12, 16, 20):
            tip = landmarks.landmark[tip_index]
            if math.hypot(tip.x - palm.x, tip.y - palm.y) < 0.16:
                folded += 1
        return folded >= 3

    def recalibrate(self) -> None:
        for side, hand_y in self.last_hands.items():
            self.neutral_y[side] = hand_y
            self.hand_y_history[side].clear()

    def update(self) -> Controls:
        control = Controls(message=self.error or "Show one hand to the camera")
        if not self.enabled or self.capture is None:
            return control
        ok, frame = self.capture.read()
        if not ok:
            control.message = "Camera frame unavailable — keyboard mode"
            return control

        frame = cv2.flip(frame, 1)
        result = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        right_hand_seen = False
        if result.multi_hand_landmarks and result.multi_handedness:
            statuses = []
            control.hand_found = True
            for landmarks, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
                side = handedness.classification[0].label  # "Right" or "Left" in mirrored preview.
                palm = landmarks.landmark[9]
                hand_y = palm.y
                self.last_hands[side] = hand_y
                self.hand_y_history[side].append(hand_y)
                smooth_y = sum(self.hand_y_history[side]) / len(self.hand_y_history[side])
                is_open = self._is_open_palm(landmarks)
                # Raising an open palm above its resting position produces 0–100% input.
                amount = max(0.0, min(1.0, (self.neutral_y[side] - smooth_y - 0.06) / 0.30)) if is_open else 0.0
                if side == "Right":
                    right_hand_seen = True
                    is_fist = self._is_fist(landmarks)
                    if is_open:
                        self.right_open_streak += 1
                        self.right_fist_streak = 0
                    elif is_fist:
                        self.right_fist_streak += 1
                        self.right_open_streak = 0
                    else:
                        self.right_open_streak = 0
                        self.right_fist_streak = 0

                    # Require a stable driving palm before arming a jump. A fist must
                    # then remain detected for five frames before it can jump.
                    open_confirmed = self.right_open_streak >= 3
                    driving = open_confirmed and amount >= 0.20
                    if driving:
                        self.right_jump_armed = True
                    control.throttle = amount if driving else 0.0
                    fist_confirmed = self.right_fist_streak >= 5
                    control.jump = fist_confirmed and self.right_jump_armed
                    if control.jump:
                        self.right_jump_armed = False

                    if control.jump:
                        action = "JUMP"
                    elif is_fist:
                        action = "FIST - HOLD"
                    elif driving:
                        action = "DRIVE"
                    else:
                        action = "SHOW OPEN PALM"
                else:
                    control.brake = amount
                    action = "BRAKE"
                statuses.append(f"{side.upper()} {action}: {int(amount * 100)}%")

                self.draw.draw_landmarks(frame, landmarks, self.hand_connections)
                px, py = int(palm.x * frame.shape[1]), int(palm.y * frame.shape[0])
                cv2.putText(frame, f"{side}: {action} {int(amount * 100)}%", (px - 95, max(25, py - 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 255, 80), 2)

            # Two high open palms after a crash is an intentional restart gesture.
            control.restart = control.throttle > 0.65 and control.brake > 0.65
            control.message = "  |  ".join(statuses) or "Show both open palms"
            if control.restart:
                control.message = "BOTH HANDS UP: RESTART"

        # A missing hand never creates a jump. Open the palm again to arm a new one.
        if not right_hand_seen:
            self.right_open_streak = 0
            self.right_fist_streak = 0

        cv2.putText(frame, "Right hand up = DRIVE | Close right palm = JUMP | Left hand up = BRAKE", (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 255, 80), 2)
        cv2.putText(frame, control.message, (14, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 255, 80), 2)
        cv2.imshow("Gesture Camera", frame)
        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        return control

    def close(self) -> None:
        if self.hands:
            self.hands.close()
        if self.capture:
            self.capture.release()
        cv2.destroyAllWindows()


class Car:
    def __init__(self, profile: dict) -> None:
        self.profile = profile
        self.reset()

    def choose(self, profile: dict) -> None:
        self.profile = profile
        self.start_new_run()

    def reset(self) -> None:
        # Start on a nearly level part of the course so the vehicle can move immediately.
        self.x = 266.0
        self.previous_x = self.x
        self.speed = 0.0
        self.fuel = 100.0
        self.distance = 0.0
        self.air_angle = 0.0
        self.angular_velocity = 0.0
        self.airborne = False
        self.air_height = 0.0
        self.vertical_speed = 0.0
        self.jumping = False
        self.jump_cooldown = 0.0
        self.crashed = False
        self.crash_time = 0.0
        self.crash_reason = ""
        self.coins = 0
        self.collected_coins: set[int] = set()
        self.collected_fuel: set[int] = set()
        self.notice = ""
        self.notice_timer = 0.0

    def start_new_run(self) -> None:
        self.reset()

    def restart_at_checkpoint(self) -> None:
        self.reset()

    def crash(self, reason: str) -> bool:
        if self.crashed:
            return False
        self.speed = 0.0
        self.crashed = True
        self.crash_reason = reason
        return True

    def update(self, dt: float, controls: Controls) -> None:
        if self.crashed:
            self.crash_time += dt
            return

        slope = terrain_slope(self.x)
        incline = math.atan(slope)
        acceleration = 0.0
        if controls.throttle and self.fuel > 0:
            acceleration += self.profile["engine"] * controls.throttle
            self.fuel = max(0.0, self.fuel - 4.2 * controls.throttle * dt)
        if controls.brake:
            acceleration -= 590 * controls.brake
        if controls.boost and self.fuel > 0:
            acceleration += 1200
            self.fuel = max(0.0, self.fuel - 11 * dt)

        # Keep hills challenging without making the first slope impossible to climb.
        acceleration -= math.sin(incline) * 580
        acceleration -= self.speed * 0.75
        self.speed = max(-170, min(self.profile["max_speed"], self.speed + acceleration * dt))
        self.previous_x = self.x
        self.x = max(0, self.x + self.speed * dt)
        self.distance = max(self.distance, self.x - 180)

        self.jump_cooldown = max(0.0, self.jump_cooldown - dt)
        jump_started = controls.jump and not self.jumping and self.jump_cooldown <= 0
        if jump_started:
            self.jumping = True
            self.air_height = 1.0
            self.vertical_speed = 480.0
            self.notice, self.notice_timer = "JUMP!", 0.5
        if self.jumping:
            self.air_height += self.vertical_speed * dt
            self.vertical_speed -= 780 * dt
            if self.air_height <= 0:
                self.air_height = 0
                self.vertical_speed = 0
                self.jumping = False
                self.jump_cooldown = 0.35
        else:
            self.air_angle += (incline - self.air_angle) * min(1.0, 9 * dt)
        self.airborne = self.jumping
        self.angular_velocity = 0.0
        self.notice_timer = max(0.0, self.notice_timer - dt)
        return "jump" if jump_started else None

    def collect_pickups(self) -> list[str]:
        events = []
        for index, pos in enumerate(COIN_POSITIONS):
            if index not in self.collected_coins and abs(self.x - pos) < 32:
                self.collected_coins.add(index)
                self.coins += 1
                self.notice, self.notice_timer = "+1 COIN", 1.0
                events.append("coin")
        for index, pos in enumerate(FUEL_POSITIONS):
            if index not in self.collected_fuel and abs(self.x - pos) < 38:
                self.collected_fuel.add(index)
                self.fuel = min(100.0, self.fuel + 34)
                self.notice, self.notice_timer = "FUEL REFILLED", 1.3
                events.append("fuel")
        return events

    def check_hazards(self) -> bool:
        """The only hazard is a cliff gap; close the right palm to jump it."""
        if self.crashed:
            return False
        for gap_x in CLIFF_GAPS:
            crossed_gap = self.previous_x < gap_x <= self.x
            if crossed_gap and not self.jumping:
                return self.crash("FELL INTO A CLIFF GAP! CLOSE RIGHT PALM TO JUMP")
        return False


def draw_text(surface, font, text, pos, color=(255, 255, 255)):
    surface.blit(font.render(text, True, color), pos)


def scene_for(world_x: float) -> dict:
    # Every 1.5 km, a different original landscape appears.
    return SCENES[int(world_x // 1500) % len(SCENES)]


def draw_background(screen, camera_x: float = 0.0, scene: dict | None = None) -> None:
    """Layered original scenery: sky, distant mountains, forest, and warm sunlight."""
    scene = scene or SCENES[0]
    screen.fill(scene["sky"])
    pygame.draw.circle(screen, scene["sun"], (875, 95), 48)
    # Slow-moving distant mountain layers create depth as the car drives.
    far_shift = int(camera_x * 0.12) % 330
    far = [(-330 - far_shift, 395), (-140 - far_shift, 235), (55 - far_shift, 395), (250 - far_shift, 245), (455 - far_shift, 395), (650 - far_shift, 205), (880 - far_shift, 395), (1210, 395)]
    pygame.draw.polygon(screen, scene["far"], far + [(WIDTH, 450), (0, 450)])
    near_shift = int(camera_x * 0.28) % 390
    near = [(-390 - near_shift, 430), (-180 - near_shift, 275), (20 - near_shift, 430), (205 - near_shift, 285), (405 - near_shift, 430), (600 - near_shift, 260), (815 - near_shift, 430), (1200, 430)]
    pygame.draw.polygon(screen, scene["near"], near + [(WIDTH, 470), (0, 470)])
    if scene["name"] == "MIDNIGHT VALLEY":
        for x in range(60, WIDTH, 95):
            y = 75 + (x * 17) % 145
            pygame.draw.circle(screen, (230, 240, 255), (x, y), 2)
    for x in range(-100, WIDTH + 100, 170):
        drift = int(camera_x * 0.06) % 170
        cx = x - drift
        if scene["name"] != "MIDNIGHT VALLEY":
            pygame.draw.circle(screen, (245, 252, 255), (cx, 90 + (x % 3) * 18), 18)
            pygame.draw.circle(screen, (245, 252, 255), (cx + 24, 78 + (x % 3) * 18), 25)
            pygame.draw.circle(screen, (245, 252, 255), (cx + 48, 94 + (x % 3) * 18), 17)


def draw_tree(screen, x: int, y: int, scale: float = 1.0) -> None:
    trunk_w, trunk_h = int(10 * scale), int(30 * scale)
    pygame.draw.rect(screen, (104, 71, 41), (x - trunk_w // 2, y - trunk_h, trunk_w, trunk_h))
    pygame.draw.circle(screen, (35, 102, 59), (x, y - trunk_h - int(12 * scale)), int(22 * scale))
    pygame.draw.circle(screen, (43, 131, 67), (x - int(14 * scale), y - trunk_h), int(17 * scale))
    pygame.draw.circle(screen, (43, 131, 67), (x + int(15 * scale), y - trunk_h), int(17 * scale))


def draw_cactus(screen, x: int, y: int) -> None:
    color = (53, 123, 89)
    pygame.draw.rect(screen, color, (x - 7, y - 52, 14, 52), border_radius=6)
    pygame.draw.rect(screen, color, (x - 22, y - 37, 15, 10), border_radius=5)
    pygame.draw.rect(screen, color, (x - 22, y - 49, 10, 22), border_radius=5)
    pygame.draw.rect(screen, color, (x + 7, y - 25, 16, 10), border_radius=5)
    pygame.draw.rect(screen, color, (x + 13, y - 37, 10, 22), border_radius=5)


def draw_button(screen, rect: pygame.Rect, label: str, font, *, active: bool = False, color=(36, 99, 148)) -> None:
    fill = (70, 145, 205) if active else color
    pygame.draw.rect(screen, (20, 47, 71), rect.inflate(5, 5), border_radius=13)
    pygame.draw.rect(screen, fill, rect, border_radius=10)
    text_img = font.render(label, True, (255, 255, 255))
    screen.blit(text_img, text_img.get_rect(center=rect.center))


def draw_game(screen, car: Car, controls: Controls, fonts, high_score: int) -> None:
    camera_x = max(0.0, car.x - 250)
    scene = scene_for(car.x)
    draw_background(screen, camera_x, scene)

    points = [(sx, terrain_y(camera_x + sx)) for sx in range(-20, WIDTH + 30, 10)]
    pygame.draw.polygon(screen, scene["ground"], points + [(WIDTH + 20, HEIGHT), (-20, HEIGHT)])
    pygame.draw.lines(screen, scene["line"], False, points, 5)
    # Dark cliff gaps are the only crash hazards. Close the right palm to jump.
    for gap_x in CLIFF_GAPS:
        if not camera_x - 60 <= gap_x <= camera_x + WIDTH + 60:
            continue
        sx = int(gap_x - camera_x)
        left_y, right_y = int(terrain_y(gap_x - 42)), int(terrain_y(gap_x + 42))
        pygame.draw.polygon(screen, (18, 25, 36), [(sx - 42, left_y - 5), (sx + 42, right_y - 5), (sx + 56, HEIGHT), (sx - 56, HEIGHT)])
        pygame.draw.lines(screen, (255, 208, 74), False, [(sx - 50, left_y - 8), (sx - 10, left_y - 5)], 5)
        pygame.draw.lines(screen, (255, 208, 74), False, [(sx + 10, right_y - 5), (sx + 50, right_y - 8)], 5)
    for world_x in range(int(camera_x // 190) * 190 - 190, int(camera_x + WIDTH + 190), 190):
        sx = int(world_x - camera_x)
        tree_y = int(terrain_y(world_x) - 4)
        if scene["name"] == "SUNSET CANYON":
            draw_cactus(screen, sx, tree_y)
        else:
            draw_tree(screen, sx, tree_y, 0.75)

    # Collectibles live in the game world and only disappear once collected.
    for index, world_x in enumerate(COIN_POSITIONS):
        if index in car.collected_coins or not camera_x - 30 <= world_x <= camera_x + WIDTH + 30:
            continue
        sx = int(world_x - camera_x)
        sy = int(terrain_y(world_x) - 48)
        pygame.draw.circle(screen, (248, 205, 46), (sx, sy), 13)
        pygame.draw.circle(screen, (255, 239, 128), (sx, sy), 8)
        draw_text(screen, fonts[0], "C", (sx - 6, sy - 9), (139, 96, 22))
    for index, world_x in enumerate(FUEL_POSITIONS):
        if index in car.collected_fuel or not camera_x - 30 <= world_x <= camera_x + WIDTH + 30:
            continue
        sx = int(world_x - camera_x)
        sy = int(terrain_y(world_x) - 56)
        pygame.draw.rect(screen, (239, 78, 54), (sx - 11, sy - 16, 22, 30), border_radius=4)
        pygame.draw.rect(screen, (255, 222, 95), (sx - 4, sy - 9, 8, 13))

    car_sx = car.x - camera_x
    ground = terrain_y(car.x)
    angle = -car.air_angle
    body = pygame.Surface((102, 50), pygame.SRCALPHA)
    pygame.draw.rect(body, car.profile["color"], (8, 14, 86, 26), border_radius=8)
    pygame.draw.polygon(body, (245, 143, 45), [(30, 14), (47, 0), (71, 0), (86, 14)])
    pygame.draw.rect(body, (181, 224, 240), (49, 4, 18, 10), border_radius=2)
    # Visible driver inside the window.
    pygame.draw.circle(body, (238, 183, 134), (58, 9), 6)
    pygame.draw.arc(body, (54, 34, 26), (52, 1, 12, 11), math.pi, math.tau, 3)
    pygame.draw.circle(body, (35, 35, 35), (60, 9), 1)
    pygame.draw.circle(body, (32, 36, 42), (26, 42), 14)
    pygame.draw.circle(body, (32, 36, 42), (78, 42), 14)
    pygame.draw.circle(body, (195, 201, 204), (26, 42), 6)
    pygame.draw.circle(body, (195, 201, 204), (78, 42), 6)
    rotated = pygame.transform.rotozoom(body, math.degrees(angle), 1)
    screen.blit(rotated, rotated.get_rect(center=(car_sx, ground - 36 - car.air_height)))

    draw_text(screen, fonts[1], f"DISTANCE  {int(car.distance / 10)} m", (26, 22))
    draw_text(screen, fonts[1], f"SPEED  {int(abs(car.speed) / 2)}", (26, 53))
    draw_text(screen, fonts[0], car.profile["name"], (26, 84), (255, 242, 131))
    draw_text(screen, fonts[0], scene["name"], (26, 108), (255, 242, 131))
    draw_text(screen, fonts[1], f"COINS  {car.coins}", (230, 22), (255, 239, 128))
    draw_text(screen, fonts[0], f"BEST  {high_score} m", (232, 56), (255, 242, 131))
    pygame.draw.rect(screen, (55, 65, 68), (WIDTH - 220, 27, 175, 23), border_radius=8)
    pygame.draw.rect(screen, (243, 185, 39) if car.fuel > 25 else (225, 72, 48), (WIDTH - 217, 30, int(169 * car.fuel / 100), 17), border_radius=6)
    draw_text(screen, fonts[0], "FUEL", (WIDTH - 280, 29))

    status_color = (255, 242, 131) if controls.hand_found else (245, 245, 245)
    draw_text(screen, fonts[0], controls.message, (26, HEIGHT - 38), status_color)
    draw_text(screen, fonts[0], "Right hand up = drive  •  Left hand up = brake  •  C = calibrate", (WIDTH - 505, HEIGHT - 38), (234, 244, 250))
    if car.distance < 40 and not car.crashed:
        guide = pygame.Surface((480, 74), pygame.SRCALPHA)
        guide.fill((15, 34, 46, 185))
        screen.blit(guide, (WIDTH // 2 - 240, 130))
        draw_text(screen, fonts[1], "First test: hold RIGHT ARROW for 2 seconds", (WIDTH // 2 - 206, 143), (255, 239, 143))
        draw_text(screen, fonts[0], "Then press C with both hands low; raise RIGHT hand to drive.", (WIDTH // 2 - 215, 177))
    if car.notice_timer > 0:
        draw_text(screen, fonts[1], car.notice, (WIDTH // 2 - 70, 235), (255, 239, 128))
    elif not car.crashed:
        next_gap = next((gap for gap in CLIFF_GAPS if gap > car.x), None)
        if next_gap is not None and next_gap - car.x < 420:
            draw_text(screen, fonts[1], "CLIFF GAP AHEAD — CLOSE RIGHT PALM TO JUMP!", (WIDTH // 2 - 280, 142), (255, 231, 123))

    if car.crashed:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((14, 18, 24, 155))
        screen.blit(overlay, (0, 0))
        draw_text(screen, fonts[2], "CRASHED!", (WIDTH // 2 - 125, HEIGHT // 2 - 75), (255, 225, 112))
        draw_text(screen, fonts[1], car.crash_reason or "TRY AGAIN", (WIDTH // 2 - 160, HEIGHT // 2 - 20), (255, 238, 196))
        draw_button(screen, pygame.Rect(WIDTH // 2 - 105, HEIGHT // 2 + 35, 210, 52), "RESTART", fonts[1], active=True)
        draw_text(screen, fonts[0], "Or press R / raise both hands", (WIDTH // 2 - 115, HEIGHT // 2 + 98))


def draw_menu(screen, fonts) -> tuple[pygame.Rect, pygame.Rect]:
    draw_background(screen)
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((9, 31, 48, 90))
    screen.blit(shade, (0, 0))
    draw_text(screen, fonts[2], "GESTURE HILL CLIMB", (WIDTH // 2 - 278, 140), (255, 239, 143))
    draw_text(screen, fonts[1], "Drive hills with your hands", (WIDTH // 2 - 160, 205))
    start = pygame.Rect(WIDTH // 2 - 130, 285, 260, 64)
    exit_button = pygame.Rect(WIDTH // 2 - 130, 370, 260, 55)
    draw_button(screen, start, "START GAME", fonts[1], active=True)
    draw_button(screen, exit_button, "EXIT", fonts[1], color=(157, 71, 63))
    draw_text(screen, fonts[0], "Choose your car, then use right hand = drive and left hand = brake.", (WIDTH // 2 - 310, 485))
    return start, exit_button


def draw_car_select(screen, selected: int, fonts) -> tuple[list[pygame.Rect], pygame.Rect, pygame.Rect]:
    draw_background(screen)
    draw_text(screen, fonts[2], "CHOOSE YOUR CAR", (WIDTH // 2 - 230, 72), (255, 239, 143))
    cards = []
    for index, vehicle in enumerate(VEHICLES):
        rect = pygame.Rect(85 + index * 335, 175, 280, 260)
        cards.append(rect)
        pygame.draw.rect(screen, (255, 236, 151) if index == selected else (25, 67, 92), rect.inflate(6, 6), border_radius=18)
        pygame.draw.rect(screen, (37, 102, 139), rect, border_radius=15)
        pygame.draw.rect(screen, vehicle["color"], (rect.x + 48, rect.y + 72, 184, 55), border_radius=14)
        pygame.draw.circle(screen, (31, 37, 42), (rect.x + 87, rect.y + 135), 23)
        pygame.draw.circle(screen, (31, 37, 42), (rect.x + 195, rect.y + 135), 23)
        draw_text(screen, fonts[1], vehicle["name"], (rect.x + 35, rect.y + 26))
        draw_text(screen, fonts[0], vehicle["note"], (rect.x + 26, rect.y + 180), (231, 244, 250))
        draw_text(screen, fonts[0], f"Power {vehicle['engine']}  •  Top {vehicle['max_speed']}", (rect.x + 20, rect.y + 212), (255, 239, 143))
    back = pygame.Rect(90, 530, 170, 52)
    play = pygame.Rect(WIDTH - 300, 530, 210, 52)
    draw_button(screen, back, "BACK", fonts[1], color=(82, 100, 113))
    draw_button(screen, play, "PLAY", fonts[1], active=True)
    return cards, back, play


def main() -> None:
    camera_enabled = "--no-camera" not in sys.argv
    print("Starting Gesture Hill Climb…", flush=True)
    pygame.init()
    pygame.display.set_caption("Gesture Hill Climb")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    fonts = (pygame.font.SysFont("arial", 18, bold=True), pygame.font.SysFont("arial", 24, bold=True), pygame.font.SysFont("arial", 48, bold=True))
    print("Opening game window…", flush=True)
    gesture = GestureController(camera_enabled=camera_enabled)
    print("Camera ready." if gesture.enabled else gesture.error, flush=True)
    selected_car = 0
    car = Car(VEHICLES[selected_car])
    sounds = SoundEffects()
    high_score = load_high_score()
    boost_was_pressed = False
    game_state = "menu"
    menu_start = pygame.Rect(WIDTH // 2 - 130, 285, 260, 64)
    menu_exit = pygame.Rect(WIDTH // 2 - 130, 370, 260, 55)
    select_cards = [pygame.Rect(85 + index * 335, 175, 280, 260) for index in range(len(VEHICLES))]
    select_back = pygame.Rect(90, 530, 170, 52)
    select_play = pygame.Rect(WIDTH - 300, 530, 210, 52)
    restart_button = pygame.Rect(WIDTH // 2 - 105, HEIGHT // 2 + 35, 210, 52)
    running = True

    try:
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.04)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_state = "menu" if game_state == "playing" else game_state
                    elif event.key == pygame.K_r:
                        if car.crashed:
                            car.restart_at_checkpoint() if car.lives > 0 else car.start_new_run()
                    elif event.key == pygame.K_c:
                        gesture.recalibrate()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse = event.pos
                    if game_state == "menu":
                        if menu_start.collidepoint(mouse):
                            game_state = "select"
                        elif menu_exit.collidepoint(mouse):
                            running = False
                    elif game_state == "select":
                        for index, card in enumerate(select_cards):
                            if card.collidepoint(mouse):
                                selected_car = index
                        if select_back.collidepoint(mouse):
                            game_state = "menu"
                        elif select_play.collidepoint(mouse):
                            car.choose(VEHICLES[selected_car])
                            game_state = "playing"
                            sounds.play("start")
                    elif game_state == "playing":
                        if car.crashed and restart_button.collidepoint(mouse):
                            car.restart_at_checkpoint()
                            sounds.play("start")
                        elif pygame.Rect(WIDTH - 118, 16, 92, 35).collidepoint(mouse):
                            game_state = "menu"

            # These rectangles are drawn on the preceding frame and used for clicks.
            menu_start = pygame.Rect(WIDTH // 2 - 130, 285, 260, 64)
            menu_exit = pygame.Rect(WIDTH // 2 - 130, 370, 260, 55)
            select_cards = [pygame.Rect(85 + index * 335, 175, 280, 260) for index in range(len(VEHICLES))]
            select_back = pygame.Rect(90, 530, 170, 52)
            select_play = pygame.Rect(WIDTH - 300, 530, 210, 52)
            restart_button = pygame.Rect(WIDTH // 2 - 105, HEIGHT // 2 + 35, 210, 52)

            if game_state == "playing":
                controls = gesture.update()
                keys = pygame.key.get_pressed()
                controls.throttle = max(controls.throttle, float(keys[pygame.K_RIGHT] or keys[pygame.K_d]))
                controls.brake = max(controls.brake, float(keys[pygame.K_LEFT] or keys[pygame.K_a]))
                controls.boost = controls.boost or bool(keys[pygame.K_SPACE])
                controls.jump = controls.jump or bool(keys[pygame.K_UP] or keys[pygame.K_j])
                if car.crashed and (keys[pygame.K_r] or controls.restart):
                    car.restart_at_checkpoint()
                    sounds.play("start")
                update_event = car.update(dt, controls)
                if update_event == "jump":
                    sounds.play("jump")
                for pickup in car.collect_pickups():
                    sounds.play(pickup)
                if car.check_hazards():
                    sounds.play("crash")
                boost_pressed = bool(controls.boost and keys[pygame.K_SPACE])
                if boost_pressed and not boost_was_pressed:
                    sounds.play("boost")
                boost_was_pressed = boost_pressed
                current_distance = int(car.distance / 10)
                if current_distance > high_score:
                    high_score = current_distance
                    save_high_score(high_score)
                draw_game(screen, car, controls, fonts, high_score)
                draw_button(screen, pygame.Rect(WIDTH - 118, 16, 92, 35), "EXIT", fonts[0], color=(157, 71, 63))
            elif game_state == "select":
                select_cards, select_back, select_play = draw_car_select(screen, selected_car, fonts)
            else:
                menu_start, menu_exit = draw_menu(screen, fonts)
            pygame.display.flip()
    finally:
        gesture.close()
        pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
