import sys

if "/flash" not in sys.path:
    sys.path.append("/flash")

try:
    from dash import app

    app.run()
except Exception as error:
    import M5

    sys.print_exception(error)
    M5.begin()
    M5.Lcd.setRotation(1)
    M5.Lcd.fillScreen(0x000000)
    M5.Lcd.setCursor(20, 20)
    M5.Lcd.print("Dashboard stopped: %r" % (error,))
