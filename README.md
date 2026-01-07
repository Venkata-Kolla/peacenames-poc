# PeaceNames POC - C-Grid Archive Browser

## What is This?

This is a **Level 1 Proof of Concept** for PeaceNames, demonstrating the core C-Grid navigation concept.

### What C-Grid Does

Instead of organizing files in folders like:
```
/Family/2023/Vacation/Photos/beach.jpg
```

C-Grid lets you **tag files across multiple dimensions**:
- **WHO**: Family
- **WHEN**: 2023
- **WHAT**: Photo
- **WHERE**: Europe
- **HOW**: Vacation

Now you can find `beach.jpg` by clicking ANY combination:
- Family → 2023 → Photos ✓
- Vacation → Europe → Photos ✓
- 2023 → Family → Vacation ✓

**Result**: Find any file in 3-4 clicks, regardless of archive size!

---

## Quick Start (5 minutes)

### Prerequisites

You need **Docker** installed. That's it!

- **Mac**: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Windows**: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux**: `sudo apt install docker.io docker-compose` (Ubuntu/Debian)

### Step 1: Start the Application

Open a terminal in this folder and run:

```bash
docker-compose up --build
```

**First run takes 2-3 minutes** (downloading images, building, loading database).

You'll see logs scrolling. Wait until you see:
```
peacenames-backend  |  * Running on http://0.0.0.0:5000
```

### Step 2: Open the Browser

Go to: **http://localhost:5000**

You should see the PeaceNames C-Grid interface with:
- 5 dimensions on the left (WHO, WHEN, WHAT, WHERE, HOW)
- 8 sample files pre-loaded
- Bilingual labels (English + Chinese)

### Step 3: Try C-Grid Navigation!

1. Click **WHO** → Click **Family** 
   - Notice the file count changes
2. Click **WHEN** → Click **2023**
   - Count narrows further
3. Click **WHAT** → Click **Photos**
   - You've found specific files in 3 clicks!

### Step 4: Upload a File

1. Click the orange **Upload** button
2. Select any file from your computer
3. Assign tags from each dimension
4. Click Upload
5. Your file appears in the grid!

---

## Stopping the Application

Press `Ctrl+C` in the terminal, then run:

```bash
docker-compose down
```

To completely reset (delete all data):

```bash
docker-compose down -v
```

---

## Project Structure

```
peacenames-poc/
├── backend/
│   ├── app.py              # Flask API server (all the backend logic)
│   └── requirements.txt    # Python dependencies
├── frontend/
│   └── index.html          # C-Grid UI (single HTML file with CSS/JS)
├── database/
│   └── schema.sql          # MySQL schema with sample data
├── docker-compose.yml      # Docker orchestration
├── Dockerfile              # Backend container build
└── README.md               # This file
```

---

## Development Mode

### Running Without Docker

If you prefer to run locally without Docker:

**1. Install MySQL 8.0**
- Mac: `brew install mysql`
- Windows: Download from mysql.com
- Linux: `sudo apt install mysql-server`

**2. Create Database**
```bash
mysql -u root -p < database/schema.sql
```

**3. Install Python Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

**4. Run the Server**
```bash
# Set environment variables
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=peacenames

# Run
python app.py
```

**5. Open Browser**
Go to http://localhost:5000

---

## API Endpoints

The backend provides these REST endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dimensions` | GET | List all C-Grid dimensions |
| `/api/tags` | GET | List tags (filter by dimension) |
| `/api/tags/tree` | GET | Full tag hierarchy |
| `/api/files` | GET | List files (filter by tags) |
| `/api/files` | POST | Upload new file |
| `/api/files/<id>/tags` | POST | Assign tags to file |
| `/api/cgrid/navigate` | GET | C-Grid navigation with counts |
| `/api/health` | GET | Health check |

### Example API Calls

```bash
# Get all dimensions
curl http://localhost:5000/api/dimensions

# Get files tagged with "Family" (tag_id=1) AND "2023" (tag_id=13)
curl "http://localhost:5000/api/files?tags=1,13"

# C-Grid navigation - see counts for each tag given current selection
curl "http://localhost:5000/api/cgrid/navigate?tags=1"
```

---

## 🧪 Sample Data

The database comes pre-loaded with:

**Users:**
- Sarah Lee (李静) - Demo user with files

**Files:**
- family_vacation_paris.jpg
- birthday_party_2023.jpg
- quarterly_report_q3.pdf
- house_purchase_contract.pdf
- kids_school_play.mp4
- travel_receipt_hotel.pdf
- wedding_anniversary.jpg
- project_presentation.pptx

Each file is tagged across multiple dimensions, demonstrating C-Grid navigation.

---

## 🌐 Bilingual Support

Toggle between English and Chinese using the **EN/中** button in the header.

All tags have bilingual labels:
- Family / 家人
- Photos / 照片
- 2023 / 2023年

This demonstrates PeaceNames' core bilingual design for cross-cultural families.

---

## 📊 Database Schema

Key tables:

```sql
-- Dimensions: WHO, WHEN, WHAT, WHERE, HOW
dimensions (id, code, name_en, name_zh)

-- Tags within each dimension (hierarchical)
tags (id, dimension_id, name_en, name_zh, parent_id, level)

-- User files
files (id, user_id, original_filename, storage_path, mime_type)

-- The magic: file-to-tag associations
file_tags (file_id, tag_id)  -- Many-to-many
```

The C-Grid query (finding files with ALL selected tags):
```sql
SELECT f.* FROM files f
JOIN file_tags ft ON f.id = ft.file_id
WHERE ft.tag_id IN (1, 13, 21)  -- Family, 2023, Photos
GROUP BY f.id
HAVING COUNT(DISTINCT ft.tag_id) = 3  -- Must match ALL tags
```

---

## ❓ Troubleshooting

### "Cannot connect to server"
- Make sure Docker is running
- Check `docker-compose logs` for errors
- Wait 30 seconds for MySQL to initialize

### "Port 5000 already in use"
- Another app is using port 5000
- Change the port in docker-compose.yml: `"5001:5000"`

### "Database not initialized"
- Run `docker-compose down -v` then `docker-compose up --build`
- This resets the database

### Files not showing after upload
- Check the browser console for errors
- Ensure tags are assigned during upload

---

## 🎯 What This POC Demonstrates

✅ **C-Grid multi-dimensional navigation**
✅ **Bilingual tag display (EN/中)**
✅ **File upload with tag assignment**
✅ **MySQL-based storage (not graph DB)**
✅ **REST API architecture**
✅ **3-4 click file discovery**

## What This POC Does NOT Include

❌ DNS/Identity management (/NAME)
❌ Email ingestion
❌ Quartet federation
❌ Volunteer orchestration
❌ StepCode ASCII conversion
❌ Blockchain ownership proofs

These are planned for Level 2 and Level 3 POCs.

---

## 📚 Learn More

- **Architecture Understanding**: See the project documentation
- **ACM Q&A Guide**: Comprehensive answers for presentations
- **Liana's Original Slides**: United Homotopic Integer Bagels

---

## 👩‍💻 Credits

- **Liana Ye** - Inventor of C-Grid, StepCode, and PeaceNames vision
- **POC Implementation** - Built to demonstrate the core concepts

---

*🕊️ PeaceNames - 和合注册 - Ethical, Bilingual, Transparent Personal Cloud*
