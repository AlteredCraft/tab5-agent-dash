"""Turn the Tab5 off. Its power button turns it back on."""

import argparse

import serial

from tools.board import Board, BoardError, ask_over_wifi

POWER_OFF = "import M5\nM5.begin()\nM5.Power.powerOff()\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    try:
        board = Board(args.port, wait=10)
    except BoardError as error:
        if ask_over_wifi("off"):
            print("The Tab5 is not answering on USB. Asked it to power off over Wi-Fi; allow about ten seconds.")
            return
        raise SystemExit("%s\nOr hold the Tab5's power button to switch it off." % error) from None
    try:
        board.run(POWER_OFF, timeout=5)
    except (BoardError, serial.SerialException, OSError):
        pass  # the connection drops as the device powers down
    print("Asked the Tab5 to power off. Press its power button to turn it on again.")


if __name__ == "__main__":
    main()
