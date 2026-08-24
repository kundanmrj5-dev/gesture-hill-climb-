# Gesture Hill Climb

An original webcam-controlled hill-driving game built with Python, Pygame, OpenCV, and MediaPipe Hands. Drive with two hands, choose a vehicle, collect coins and fuel, and travel through changing landscapes.

## Features

- Two-hand gesture controls with real-time webcam feedback
- Start menu, car selection, and in-game Exit button
- Three vehicles with different power and top-speed profiles
- Coins, fuel pickups, sound effects, and a saved high score
- Three changing original landscapes: Alpine Pass, Sunset Canyon, and Midnight Valley
- Marked cliff-gap challenges with a palm-close jump gesture
- Keyboard fallback and a webcam-free mode for testing

## Controls

| Gesture | Effect |
| --- | --- |
| Raise your open right hand | Accelerate forward; height controls strength |
| Raise your open left hand | Brake / reverse; height controls strength |
| Make a closed right fist briefly | Jump over a cliff gap |
| Raise both open hands after a crash | Restart the run |

The webcam preview is mirrored. First hold both hands at a comfortable resting height and press **C**. Then raise the right palm to drive and the left palm to brake. Keeping a hand low, closing it, or taking it out of frame releases that control.

Keyboard fallback: **Right / D** accelerate, **Left / A** brake, **Up / J** jump, **Space** boost, **Esc** returns to the menu, and **F11** toggles full-screen mode. Press **C** to recalibrate. The normal game window can also be maximized with the Windows maximize button.

## Cliff gaps

Cliff gaps are the only crash hazard. First drive with a raised open right palm. Then, when the on-screen warning appears, close the right hand into a fist and hold it still for a moment (about 5 camera frames). The car jumps once. Then reopen and raise the right palm before attempting the next jump. A fist is ignored until the game has first seen intentional open-palm driving, preventing accidental jumps caused by a blurry or briefly lost hand. If you miss a jump and fall into a gap, click **RESTART**, press **R**, or raise both hands to start again.

## Setup

Use Python 3.11 (recommended for the included MediaPipe version):

```powershell
git clone <your-repository-url>
cd gesture-hill-climb
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

The project intentionally pins MediaPipe to version 0.10.21 because it provides the stable Hands API used by the game.

Allow webcam permission when Windows asks. The camera preview opens in a separate **Gesture Camera** window; press **Q** there or use the in-game Exit button to quit.

For a webcam-free test, run `.\.venv\Scripts\python.exe main.py --no-camera`. It starts the game in keyboard-only mode.

## How the gesture control works

MediaPipe Hands finds 21 landmarks for each hand every frame. The program identifies right and left open palms separately, compares their heights with the calibrated resting position, and smooths the output over several frames so brief tracking noise does not change the vehicle controls.

If MediaPipe cannot start or no webcam is found, the game stays playable with the keyboard.

## Project files

- `main.py` — game, gesture control, and original visuals
- `requirements.txt` — Python dependencies
- `high_score.json` — created locally at runtime and intentionally not committed

## License

This project is released under the [MIT License](LICENSE).
