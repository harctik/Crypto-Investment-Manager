import os, io, sys, time, datetime, random, threading
import contextlib
from PIL import Image, ImageDraw, ImageFont

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Seed Fake History for backtest
import database
coins = database.list_tracked()
if not coins:
    import main
    main.run_milestone1()
    coins = database.list_tracked()

for c in coins:
    base_price = database.get_history(c["coin_id"], limit=1)[0]["price_usd"]
    with database.conn() as conn:
        for i in range(40, 0, -1):
            change = random.uniform(-0.05, 0.05)
            base_price *= (1 + change)
            dt = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                INSERT INTO price_history
                    (coin_id,symbol,name,price_usd,market_cap,volume_24h,change_24h,fetched_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (c["coin_id"], c["symbol"], c["name"], base_price,
                  1000000, 500000, change*100, dt))

# Set encoding to prevent unicode errors
sys.stdout.reconfigure(encoding='utf-8')

def render_terminal_image(text, filename):
    lines = text.strip().split('\n')
    # fallback to default font
    try:
        font = ImageFont.truetype("consola.ttf", 14)
    except:
        font = ImageFont.load_default()
    
    # Calculate image dimensions
    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    max_width = 800
    total_height = 40
    
    for line in lines:
        try:
            bbox = draw.textbbox((0,0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except:
            w = len(line) * 8
            h = 16
        max_width = max(max_width, w + 40)
        total_height += (h + 4)
        
    img = Image.new('RGB', (max_width, total_height), color='#1e1e1e')
    draw = ImageDraw.Draw(img)
    
    y = 20
    for line in lines:
        draw.text((20, y), line, font=font, fill='#d4d4d4')
        try:
            bbox = draw.textbbox((0,0), "A", font=font)
            h = bbox[3] - bbox[1]
        except:
            h = 16
        y += h + 4
        
    img.save(filename)
    print(f"Saved {filename}")

import main
from config import WATCHLIST

def capture_and_render(func, args, filename):
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        try:
            res = func(*args)
        except Exception as e:
            print(f"Error: {e}")
            res = None
    output = f.getvalue()
    render_terminal_image(output, filename)
    return res

print("Generating Milestone 1...")
coins_m1 = capture_and_render(main.run_milestone1, (), "Milestone1_Init.png")

print("Generating Milestone 2...")
capture_and_render(main.run_milestone2, (), "Milestone2_Mix.png")

print("Generating Milestone 3...")
capture_and_render(main.run_milestone3, (coins_m1,), "Milestone3_Risk.png")

print("Generating Milestone 4...")
capture_and_render(main.run_milestone4, (coins_m1,), "Milestone4_Rules.png")

print("Generating Milestone 5...")
capture_and_render(main.run_milestone5, (), "Milestone5_Backtest.png")

# Now Flask App Screenshot
print("Generating Flask Dashboard Screenshot...")
from werkzeug.serving import make_server
import app as flask_app

class ServerThread(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.server = make_server('127.0.0.1', 5000, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()

server = ServerThread(flask_app.app)
server.start()

time.sleep(3) # Wait for server to start

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto('http://127.0.0.1:5000/dashboard')
    page.wait_for_timeout(3000) # wait for websockets and live prices
    page.screenshot(path="Flask_Dashboard.png")
    browser.close()

server.shutdown()
server.join()
print("All screenshots generated!")
