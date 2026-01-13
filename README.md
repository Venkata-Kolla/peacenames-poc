# 🕊️ PeaceNames POC v2 - Visual C-Grid

## What's New in v2

This version includes **Liana's 5x5 C-Grid visual layout** with the 25 official icons!

### Features
- ✅ **Visual 5x5 C-Grid** with clickable icons
- ✅ **25 official icons** from Liana's design
- ✅ **Bilingual labels** (English/Chinese)
- ✅ **Multi-select filtering** - click multiple icons
- ✅ **Mobile-friendly** layout
- ✅ **Upload with category selection**

---

## 5x5 Grid Layout

| Col 1 (WHERE) | Col 2 (WHEN) | Col 3 (WHAT) | Col 4 (HOW) | Col 5 (WHO) |
|---------------|--------------|--------------|-------------|-------------|
| gold 金 | edu 学 | res 农 | pub 版 | biz 计 |
| arch 拱 | mot 式 | dir 档 | job 职 | com 商 |
| lan 文 | exp 示 | **name 名** | post 邮 | sys 系 |
| loc 址 | info 息 | tree 树 | net 网 | gov 政 |
| neon 霓 | dic 典 | proj 项 | org 团 | cir 群 |

**Center cell (name/名)** = Identity/PeaceNames logo

---

## Quick Start

### Option 1: Local with Docker
```bash
cd peacenames-poc-v2
docker-compose up --build
```
Open: http://localhost:5001

### Option 2: Deploy to Railway
1. Push to GitHub
2. Connect to Railway
3. Add MySQL database
4. Set environment variables
5. Deploy!

---

## File Structure

```
peacenames-poc-v2/
├── frontend/
│   ├── index.html          # Main UI with 5x5 C-Grid
│   └── icons/              # 25 icon images
│       ├── gold.jpg
│       ├── edu.jpg
│       ├── res.jpg
│       └── ... (25 total)
├── backend/
│   ├── app.py              # Flask API
│   └── requirements.txt
├── database/
│   └── schema.sql
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## How C-Grid Works

1. **Click any icon** to filter files by that category
2. **Click multiple icons** to narrow down further
3. **Selected icons** appear as chips below the grid
4. **Files update** in real-time to show matches
5. **Toggle EN/中** for bilingual display

---

## Credits

- **Liana Ye** - C-Grid concept & icon designs
- **PeaceNames** - 和合注册

🕊️ *Ethical, Bilingual, Transparent Personal Cloud*
