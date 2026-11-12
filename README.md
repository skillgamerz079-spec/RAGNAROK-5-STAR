# Eat 5 Star (web version)

Browser port of the Tkinter "do nothing" challenge. Flask serves one static page;
the game runs in the browser and your personal best is saved in localStorage.

## Run locally
    pip install -r requirements.txt
    python app.py        # http://localhost:5000

## Deploy on Render
1. Push this folder to a GitHub repo (files must be at the repo root):
       git init
       git add .
       git commit -m "Eat 5 Star"
       git branch -M main
       git remote add origin https://github.com/<you>/<repo>.git
       git push -u origin main
2. On render.com: New + > Blueprint > pick the repo > Apply.
   (Or New + > Web Service with Build `pip install -r requirements.txt`
   and Start `gunicorn app:app --bind 0.0.0.0:$PORT`.)
3. Open the .onrender.com URL. Free instances sleep when idle, so the first load can be slow.

## Differences from the desktop version
Browsers cannot watch your whole desktop. The round ends if you move the mouse,
click, tap, scroll, press a key, or switch tab/window while the page is active.

## Install as an app (PWA)
The page has an **Install app** button (needs HTTPS, which Render provides, or localhost).
Once installed it shows **App already installed**. On iPhone/iPad use Share > Add to Home Screen.
