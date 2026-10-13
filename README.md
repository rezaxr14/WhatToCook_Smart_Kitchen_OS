# 🍳 WhatToCook — AI-Powered Intelligent Recipe Studio & Smart Pantry

> **Zero Food Waste AI Recipe Engine**, visual camera ingredient scanner powered by **Generative AI**, real-time culinary generation streaming, interactive Telegram bot assistant, smart grocery lists with 1-click WhatsApp & Telegram exports, dynamic portion scaling, an offline Progressive Web App (PWA), and a **5-language interface (English, Türkçe, فارسی, العربية, Español)** with full RTL support.

[![Django 5.2](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker Alpine](https://img.shields.io/badge/Docker-Alpine_Lean-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com/)

---

## 🖼️ Screenshots

<p align="center">
  <img src="docs/screenshots/landing-hero.png" alt="WhatToCook landing page — 'You already have dinner.' 3D kitchen hero" width="100%">
  <br>
  <em>Cinematic 3D landing page — "You already have dinner."</em>
</p>

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/screenshots/recipes-catalog.png" alt="Kitchen dashboard and recipe catalog with search, filters and cook-time slider">
      <br><sub><b>Kitchen Dashboard &amp; Recipe Catalog</b> — search, category filters and a max-cook-time slider</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/screenshots/pantry-shelf.png" alt="My Pantry Shelf with stocked ingredients, fridge photo scanner and ingredient catalog">
      <br><sub><b>My Pantry Shelf</b> — stocked ingredients, fridge-photo scanner and a 73-item catalog</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/screenshots/can-cook.png" alt="What You Can Cook Right Now — zero-waste recipe matching with missing ingredients">
      <br><sub><b>What You Can Cook Right Now</b> — 100% matches and "missing 1 or 2 items" recipes</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/screenshots/ai-chef-studio.png" alt="AI Chef Studio — pick pantry ingredients and generate chef recipes">
      <br><sub><b>AI Chef Studio</b> — pick ingredients and generate recipes with Cloud or Local AI</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/screenshots/sign-in.png" alt="Sign-in page with one-click guest demo">
      <br><sub><b>Sign In</b> — with an instant 1-click guest demo</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/screenshots/landing-mobile.png" alt="WhatToCook landing page on a mobile viewport" height="320">
      <br><sub><b>Mobile</b> — fully responsive layout</sub>
    </td>
  </tr>
</table>

### 🎬 The 3D Landing Journey

Scrolling the landing page tells the whole story in eight chapters: open the fridge, let the AI connect the dots, and watch dinner get discovered.

<table>
  <tr>
    <td width="25%" align="center"><img src="docs/screenshots/journey/01-arrival.png" alt="Chapter 1 — Arrival"><br><sub>1 · Arrival</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/02-fridge-door.png" alt="Chapter 2 — Fridge door"><br><sub>2 · Fridge door</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/03-ai-awakens.png" alt="Chapter 3 — AI awakens"><br><sub>3 · AI awakens</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/04-galaxy.png" alt="Chapter 4 — Galaxy of possibilities"><br><sub>4 · Galaxy</sub></td>
  </tr>
  <tr>
    <td width="25%" align="center"><img src="docs/screenshots/journey/05-cooking.png" alt="Chapter 5 — Cooking"><br><sub>5 · Cooking</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/06-dish.png" alt="Chapter 6 — The dish"><br><sub>6 · The dish</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/07-homecoming.png" alt="Chapter 7 — Homecoming"><br><sub>7 · Homecoming</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/08-finale.png" alt="Chapter 8 — Finale"><br><sub>8 · Finale</sub></td>
  </tr>
</table>

<details>
<summary>📜 Full-length landing page</summary>
<br>
<p align="center">
  <img src="docs/screenshots/landing-full.png" alt="Full-length WhatToCook landing page" width="60%">
</p>
</details>

---

## 🌟 Architecture & Key Features

```
WhatToCook Ecosystem
├── 🌐 React 18 + TypeScript + TailwindCSS + TanStack Query Frontend (Vite)
│   └── 🧊 React Three Fiber 3D hero · react-i18next (EN/TR/FA/AR/ES + RTL) · PWA
├── 🛡️ nginx reverse proxy → serves the SPA build, proxies /api /admin /static /media /legacy
├── ⚡ Django 5.2 REST Framework API Backend (Python 3.11, gunicorn + WhiteNoise)
├── 🤖 Multimodal AI Vision & Generative Recipe Streaming Engine
├── 💬 Telegram Bot Webhook & Interactive Pantry Handshake
├── 📱 Smart Grocery Exporter (WhatsApp, Telegram, Markdown, Print)
├── 🗄️ PostgreSQL 15 (Docker) / SQLite3 (Auto-fallback local dev)
└── 🚀 Redis 7 → Celery task queue + Django cache (stats, health probes)
```

### ✨ Core Features
1. **📸 AI Vision Pantry Scanner**: Snap a photo of your fridge or countertop; AI detects recognized food items and automatically stocks your digital pantry shelf.
2. **🧠 Smart Zero-Waste Recipe Matching**: Instantly computes 100% matched recipes you can cook right now with no extra groceries needed, plus partial matches (missing only 1 or 2 items).
3. **⚡ Live SSE Generative Streaming**: Watch recipes, macro breakdowns, and master chef secrets stream in real-time.
4. **🤖 Telegram AI Chef Bot**: Link your Telegram account with 1-click. Send `/cook`, `/pantry`, `/add Garlic`, or `/remove Butter` from your phone on the go.
5. **🛒 Smart Grocery List & 1-Click Social Exporter**: Add missing ingredients from any recipe or partial match with 1 click. Export formatted grocery lists to **WhatsApp**, **Telegram**, Clipboard, or Print slip.
6. **⚖️ Dynamic Portion Scaler (1x, 2x, 4x, 6x, 8x)**: Scalable ingredient measurements (e.g. `2 tbsp`, `250g`, `1/2 cup`) dynamically recalibrate portions in real-time without boundary overflows.
7. **💡 AI Substitution Assistant**: Missing buttermilk, eggs, heavy cream, or parmesan? Instant culinary swaps and ratio tips.
8. **📱 Progressive Web App (PWA)**: Installable on iOS & Android with offline pantry viewing.
9. **🌍 Multilingual UI (EN / TR / FA / AR / ES)**: First-visit language chooser, floating quick-switcher and footer dropdown; Persian & Arabic get full right-to-left layouts and dedicated fonts (Vazirmatn, Noto Sans Arabic).

---

## ⚡ Superfast Quickstart with Docker (Recommended)

Run the complete multi-service stack with a single command:

```bash
# 1. Clone the repository
git clone https://github.com/rezaxr14/WhatToCook_Smart_Kitchen_OS.git
cd WhatToCook_Smart_Kitchen_OS

# 2. Configure environment variables
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY (from https://aistudio.google.com)

# (If your network requires an HTTP proxy for internet egress, add your overrides:
#  docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d --build)

# 3. Build and launch all lightweight containers
#    (migrations, idempotent seeding and collectstatic run automatically on boot)
docker compose up -d --build
```

### 🌐 Access Points:
- **Frontend Web App**: [http://localhost:4173](http://localhost:4173)
- **Django REST API**: [http://localhost:8000/api/](http://localhost:8000/api/)
- **Landing Page Health**: [http://localhost:8000/api/health/](http://localhost:8000/api/health/)
- **Django Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/) or [http://localhost:4173/admin/](http://localhost:4173/admin/)
- **Legacy Server-Rendered Pages**: [http://localhost:8000/legacy/](http://localhost:8000/legacy/)

---

## 💻 Local Development Setup (Without Docker)

### 1. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# IMPORTANT: if your .env has DB_HOST set (Docker config), force SQLite locally:
#   PowerShell:  $env:USE_POSTGRES="false"
#   bash:        USE_POSTGRES=false

# Run migrations & seed recipes
python manage.py migrate
python manage.py seed_recipes

# Start backend server
python manage.py runserver 127.0.0.1:8000
```

### 2. Frontend Setup
```bash
cd frontend

# Install node dependencies
npm install

# Start Vite development server
npm run dev
```

---

## 🧪 Testing Suite

Run the comprehensive Django REST API test suite:

```bash
# Bare-metal (SQLite): make sure Postgres is not forced via .env
USE_POSTGRES=false python manage.py test GetFood tests
```

Target: **100% passing tests** covering:
- Authentication & Auto-Pantry Creation
- Pantry Ingredient Operations & Optimistic Handshakes
- Zero-Waste Match Engine Algorithms (100% & Partial matches)
- Multimodal Vision Scanner & Fallback Resiliency
- Live AI Recipe Generation & Streaming Endpoints
- Platform endpoints (/api/stats/, /api/health/) & legacy route namespacing
- Rate limiting: every scope trips a clean `429` with `Retry-After`
  (`tests/test_throttling.py`)

Frontend production build + end-to-end Playwright suite (23 tests across the 3D
landing journey, full user flows, i18n/RTL and responsive viewports):

```bash
cd frontend
npm run build          # typecheck + vite build
npm run test:e2e       # starts Vite automatically; backend on :8000 required
# refresh the journey screenshots in docs/screenshots (dev servers running):
node scripts/recapture-journey.cjs && node scripts/recapture-landing.cjs
```

## 🛡️ Production hardening

All API traffic is rate-limited per endpoint scope with anon/user-aware
buckets and `Retry-After` responses — see `GetFood/rate_limits.py` (rates
tunable via env), `GetFood/throttles.py`, and `WhatToCook/settings.py`
(`USE_RATE_LIMITS=1` enables; on by default). Cache uses a dummy local
backend when Redis is absent.

## 🖼️ Curated dish photography

Every recipe, dish suggestion and pantry ingredient resolves to an
accurate, verified photo (no placeholder repeats): the 12 catalog recipes
ship with original self-hosted photos under `media/recipes/`, while
keyword maps in `GetFood/utils.py` and `frontend/src/utils/imageUtils.ts`
are audited against real stock imagery. Run
`python manage.py seed_recipes` after a fresh DB to bind the photos.

---

## 📄 License

Copyright © 2026. All rights reserved. This project is proprietary software — see [LICENSE.md](LICENSE.md) for the full license terms.
