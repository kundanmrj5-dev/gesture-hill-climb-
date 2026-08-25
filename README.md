# Gesture Hill Climb

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Pygame](https://img.shields.io/badge/Pygame-Game%20Development-green)](https://www.pygame.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-red?logo=opencv&logoColor=white)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Hand%20Tracking-orange)](https://ai.google.dev/edge/mediapipe/solutions/guide)
[![GitHub](https://img.shields.io/badge/GitHub-Source%20Code-black?logo=github)](https://github.com/kundanmrj5-dev/gesture-hill-climb-)

An original webcam-controlled hill-driving game built with Python, Pygame, OpenCV, and MediaPipe Hands. Drive with two hands, choose a vehicle, collect coins and fuel, and travel through changing landscapes.
🎥 **[Watch Gameplay Demo](https://github.com/kundanmrj5-dev/gesture-hill-climb-/releases/tag/v1.0.0)**

![Gesture Hill Climb Gameplay](assets/gameplay.gif)
## ✨ Features

- 🖐️ **Real-Time Hand Gesture Control** — Control the vehicle using live hand gestures detected through the webcam.
- 🚗 **Multiple Vehicles** — Choose from three vehicles with different power and top-speed characteristics.
- 🏎️ **Gesture-Based Driving** — Use the right-hand palm to accelerate, right-hand fist to jump, and left-hand palm to brake.
- 🏔️ **Dynamic Landscapes** — Explore three original environments: Alpine Pass, Sunset Canyon, and Midnight Valley.
- 🪙 **Coin Collection System** — Collect coins while driving and improve your score.
- ⛽ **Fuel Management** — Collect fuel pickups to keep the vehicle running.
- 🚧 **Cliff-Gap Challenges** — Use the jump gesture to overcome gaps and difficult sections of the terrain.
- 🏆 **High-Score System** — Track and save your best performance.
- 🔊 **Immersive Game Experience** — Includes sound effects, vehicle movement, obstacles, and interactive environments.
- 🎮 **Keyboard Fallback** — Play and test the game using keyboard controls when a webcam is unavailable.
- 📷 **Webcam-Free Testing Mode** — Test core gameplay mechanics without requiring a camera.
- 🖥️ **Resizable & Fullscreen Window** — Supports flexible game window sizes for a better gameplay experience.

The webcam preview is mirrored. First hold both hands at a comfortable resting height and press **C**. Then raise the right palm to drive and the left palm to brake. Keeping a hand low, closing it, or taking it out of frame releases that control.

Keyboard fallback: **Right / D** accelerate, **Left / A** brake, **Up / J** jump, **Space** boost, **Esc** returns to the menu, and **F11** toggles full-screen mode. Press **C** to recalibrate. The normal game window can also be maximized with the Windows maximize button.

## 🎮 Controls

### 🖐️ Gesture Controls

| Gesture | Action |
|---|---|
| ✋ Right Open Palm | Accelerate / Drive |
| ✊ Right Closed Fist | Jump |
| ✋ Left Open Palm | Brake |
| 👋 Both Hands | Gesture-based interaction |

### ⌨️ Keyboard Controls

| Key | Action |
|---|---|
| `W` / `↑` | Accelerate |
| `S` / `↓` | Brake |
| `Space` | Jump |
| `Esc` | Exit / Pause |

> 💡 **Tip:** For the best gesture-control experience, keep your hands clearly visible to the webcam and maintain a reasonable distance from the camera.

- 💡 **Tip:** For the best gesture-control experience, keep your hands clearly visible to the webcam and maintain a reasonable distance from the camera.

- 🚧 **Cliff-Gap Challenges** — Jump across dangerous terrain gaps by closing your right hand into a fist at the right moment.

## ⚙️ Setup

### Prerequisites

- Windows 10/11
- Python 3.11
- Webcam (required for gesture controls)
- Git

### 1. Clone the Repository

```powershell
git clone https://github.com/kundanmrj5-dev/gesture-hill-climb-.git
cd gesture-hill-climb-
```

### 2. Create a Virtual Environment

```powershell
py -3.11 -m venv .venv
```

### 3. Activate the Virtual Environment

```powershell
.venv\Scripts\activate
```

### 4. Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Run the Game

```powershell
python main.py
```

### Webcam-Free Mode

```powershell
python main.py --no-camera
```

## How the gesture control works

MediaPipe Hands finds 21 landmarks for each hand every frame. The program identifies right and left open palms separately, compares their heights with the calibrated resting position, and smooths the output over several frames so brief tracking noise does not change the vehicle controls.

If MediaPipe cannot start or no webcam is found, the game stays playable with the keyboard.
## 🧠 How It Works

The game uses real-time hand tracking to convert gestures into vehicle controls.

```text
Webcam
   ↓
OpenCV
   ↓
MediaPipe Hands
   ↓
Hand Landmark Detection
   ↓
Gesture Recognition
   ↓
Game Controls
   ↓
Pygame

## 📂 Project Structure

```text
gesture-hill-climb-/
│
├── assets/              # Game assets and screenshots
├── main.py              # Main game entry point
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation
└── .gitignore           # Ignored files

## Project files

- `main.py` — game, gesture control, and original visuals
- `requirements.txt` — Python dependencies
- `high_score.json` — created locally at runtime and intentionally not committed

## 🚀 Future Improvements

- 🤖 Improve gesture recognition accuracy and reliability
- 🎮 Add more gesture-based controls
- 🚗 Add more vehicles with unique abilities
- 🏔️ Introduce more maps, levels, and terrain challenges
- 🏆 Add online leaderboard and player statistics
- ⚡ Optimize real-time hand tracking for better performance
- 👥 Add multiplayer gameplay

## License

This project is released under the [MIT License](LICENSE).
## 👨‍💻 Author

**Kundan Pandey**  
B.Tech Computer Science & Engineering

Interested in **Data Science, Machine Learning, Computer Vision, and AI**.

- 🐙 GitHub: [kundanmrj5-dev](https://github.com/kundanmrj5-dev)
