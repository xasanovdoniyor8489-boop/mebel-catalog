import os, sqlite3, shutil, uuid
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

os.makedirs("static/uploads", exist_ok=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass

DB = "catalog.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, icon TEXT DEFAULT '📦')")
    conn.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, name TEXT NOT NULL, icon TEXT DEFAULT '📁')")
    conn.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT NOT NULL, description TEXT, colors TEXT DEFAULT '', sizes TEXT DEFAULT '', photo TEXT DEFAULT '')")
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def admin_panel():
    with open("templates/admin.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page():
    with open("templates/catalog.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/groups")
async def get_groups():
    conn = get_db()
    groups = conn.execute("SELECT * FROM groups ORDER BY id").fetchall()
    conn.close()
    return [dict(g) for g in groups]

@app.post("/api/groups")
async def create_group(name: str = Form(...), icon: str = Form("📦")):
    conn = get_db()
    conn.execute("INSERT INTO groups (name, icon) VALUES (?, ?)", (name, icon))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int):
    conn = get_db()
    conn.execute("DELETE FROM groups WHERE id=?", (group_id,))
    conn.execute("DELETE FROM categories WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/categories")
async def get_categories(group_id: Optional[int] = None):
    conn = get_db()
    if group_id:
        cats = conn.execute("SELECT * FROM categories WHERE group_id=? ORDER BY id", (group_id,)).fetchall()
    else:
        cats = conn.execute("SELECT c.*, g.name as group_name FROM categories c LEFT JOIN groups g ON c.group_id=g.id ORDER BY c.id").fetchall()
    conn.close()
    return [dict(c) for c in cats]

@app.post("/api/categories")
async def create_category(name: str = Form(...), group_id: int = Form(...), icon: str = Form("📁")):
    conn = get_db()
    conn.execute("INSERT INTO categories (name, group_id, icon) VALUES (?, ?, ?)", (name, group_id, icon))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/categories/{cat_id}")
async def delete_category(cat_id: int):
    conn = get_db()
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.execute("DELETE FROM products WHERE category_id=?", (cat_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/products")
async def get_products(category_id: Optional[int] = None, search: Optional[str] = None):
    conn = get_db()
    if category_id:
        products = conn.execute("SELECT * FROM products WHERE category_id=? ORDER BY id", (category_id,)).fetchall()
    elif search:
        products = conn.execute("SELECT * FROM products WHERE name LIKE ? OR description LIKE ?", (f"%{search}%", f"%{search}%")).fetchall()
    else:
        products = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id ORDER BY p.id").fetchall()
    conn.close()
    return [dict(p) for p in products]

@app.post("/api/products")
async def create_product(name: str = Form(...), description: str = Form(""), category_id: int = Form(...), colors: str = Form(""), sizes: str = Form(""), photo: UploadFile = File(None)):
    photo_path = ""
    if photo and photo.filename:
        ext = photo.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        path = f"static/uploads/{filename}"
        with open(path, "wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_path = f"/static/uploads/{filename}"
    conn = get_db()
    conn.execute("INSERT INTO products (name, description, category_id, colors, sizes, photo) VALUES (?,?,?,?,?,?)", (name, description, category_id, colors, sizes, photo_path))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return {"success": True}
