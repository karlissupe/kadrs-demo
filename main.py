"""KADRS! Photo challenge game. Python 3.10+, FastAPI, SQLite."""
import base64
import hashlib
import hmac
import io
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('DATA_DIR', str(ROOT / 'data'))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / 'photos'
UPLOAD_DIR.mkdir(exist_ok=True)
REFERENCE_DIR = DATA_DIR / 'references'
REFERENCE_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / 'game.sqlite3'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
APP_SECRET = os.environ.get('APP_SECRET', '') or secrets.token_urlsafe(32)
SECURE_COOKIES = os.environ.get('SECURE_COOKIES', '0') == '1'
MAX_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 32_000_000

if not ADMIN_PASSWORD:
    raise RuntimeError('Norādi ADMIN_PASSWORD vides mainīgo pirms servera palaišanas.')

app = FastAPI(title='KADRS! Foto medības', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

SEED_TASKS = [
    ('Visi vienā kadrā', 'Savāciet visus komandas dalībniekus vienā fotogrāfijā. Jo radošāk, jo labāk!', 50, '📷', 'Komanda'),
    ('Dzīvā skulptūra', 'Izveidojiet kopīgu skulptūru tikai ar savām pozām un nofotografējiet to.', 80, '🗿', 'Poza'),
    ('Kaut kas spilgti sarkans', 'Atrodiet sarkanu objektu un uzņemiet foto, kur tas ir galvenais varonis.', 50, '🔴', 'Objekts'),
    ('Spoguļpasaule', 'Uzņemiet interesantu komandas atspulgu logā, peļķē vai citā spoguļvirsmā.', 70, '🪞', 'Objekts'),
    ('Lēciens vienā sekundē', 'Noķeriet brīdi, kad vismaz trīs dalībnieki vienlaikus atrodas gaisā.', 80, '⚡', 'Poza'),
    ('Milzis un punduris', 'Izmantojot perspektīvu, izveidojiet foto, kur viens dalībnieks izskatās milzīgs.', 90, '🧍', 'Poza'),
    ('Kaut kas ar vēsturi', 'Atrodiet interesantu senu objektu vai ēku un iekļaujiet to komandas foto.', 60, '🏛️', 'Vieta'),
    ('Filmas plakāts', 'Izveidojiet komandas foto kā izdomātas filmas plakātu. Pozējiet ar attieksmi!', 100, '🎬', 'Radošais'),
]
SEED_TEAMS = ['Zibens', 'Lapsas', 'Komētas', 'Pūces', 'Viesuļi', 'Pandas', 'Dzirksteles', 'Raķetes']


def create_code(db):
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    for _ in range(100):
        code = ''.join(secrets.choice(chars) for _ in range(6))
        if not db.execute('SELECT 1 FROM teams WHERE code=?', (code,)).fetchone():
            return code
    raise RuntimeError('Neizdevās ģenerēt unikālu kodu')


def init_db():
    with database() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS teams (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE COLLATE NOCASE,
          code TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL, description TEXT NOT NULL,
          points INTEGER NOT NULL CHECK (points BETWEEN 1 AND 1000),
          emoji TEXT NOT NULL DEFAULT '📸', category TEXT NOT NULL DEFAULT 'Foto',
          sort_order INTEGER NOT NULL, reference_filename TEXT
        );
        CREATE TABLE IF NOT EXISTS submissions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
          task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
          filename TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'approved', 'rejected')),
          note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          reviewed_at TEXT,
          UNIQUE(team_id, task_id)
        );
        CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
        ''')
        if db.execute('SELECT COUNT(*) AS n FROM tasks').fetchone()['n'] == 0:
            for idx, (title, description, points, emoji, category) in enumerate(SEED_TASKS, 1):
                db.execute('INSERT INTO tasks (title,description,points,emoji,category,sort_order) VALUES (?,?,?,?,?,?)',
                           (title, description, points, emoji, category, idx))
        if db.execute('SELECT COUNT(*) AS n FROM teams').fetchone()['n'] == 0:
            for name in SEED_TEAMS:
                db.execute('INSERT INTO teams (name,code) VALUES (?,?)', (name, create_code(db)))

init_db()


def issue_token(role, ident, max_age):
    payload = f'{role}:{ident}:{int(time.time()) + max_age}'.encode()
    sig = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).digest()
    payload64 = base64.urlsafe_b64encode(payload).decode().rstrip('=')
    sig64 = base64.urlsafe_b64encode(sig).decode().rstrip('=')
    return payload64 + '.' + sig64


def read_token(token, expected_role):
    if not token:
        return None
    try:
        encoded_payload, encoded_sig = token.split('.', 1)
        payload = base64.urlsafe_b64decode(encoded_payload + '=' * (-len(encoded_payload) % 4))
        sig = base64.urlsafe_b64decode(encoded_sig + '=' * (-len(encoded_sig) % 4))
        expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        role, ident, expiry = payload.decode().split(':')
        if role != expected_role or int(expiry) < time.time():
            return None
        return ident
    except (ValueError, UnicodeError):
        return None


def current_team(request):
    tid = read_token(request.cookies.get('kadrs_team'), 'team')
    if tid is None:
        return None
    with database() as db:
        row = db.execute('SELECT id,name FROM teams WHERE id=?', (tid,)).fetchone()
        return dict(row) if row else None


def require_team(request):
    team = current_team(request)
    if not team:
        raise HTTPException(status_code=401, detail='Pievienojies komandai ar piekļuves kodu.')
    return team


def is_admin(request):
    return read_token(request.cookies.get('kadrs_admin'), 'admin') == 'ok'


def require_admin(request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail='Nepieciešama administratora pieslēgšanās.')


def set_cookie(response, key, value, max_age):
    response.set_cookie(key, value, max_age=max_age, httponly=True,
                        secure=SECURE_COOKIES, samesite='lax', path='/')


def leaderboard(db):
    rows = db.execute('''
      SELECT t.id, t.name, COALESCE(SUM(CASE WHEN s.status='approved' THEN k.points ELSE 0 END),0) AS points,
             COALESCE(SUM(CASE WHEN s.status='approved' THEN 1 ELSE 0 END),0) AS done
      FROM teams t LEFT JOIN submissions s ON s.team_id=t.id
      LEFT JOIN tasks k ON k.id=s.task_id
      GROUP BY t.id ORDER BY points DESC, done DESC, t.name COLLATE NOCASE
    ''').fetchall()
    return [dict(row) | {'rank': rank} for rank, row in enumerate(rows, 1)]


def process_image(data: bytes, target: Path):
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Attēls pārsniedz 8 MB. Izvēlies mazāku foto.')
    try:
        with Image.open(io.BytesIO(data)) as raw:
            if raw.format not in ('JPEG', 'PNG', 'WEBP', 'HEIF'):
                raise HTTPException(400, 'Atļauti tikai JPG, PNG un WebP attēli.')
            picture = ImageOps.exif_transpose(raw)
            picture.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            if picture.mode in ('RGBA', 'LA') or ('transparency' in picture.info):
                base = Image.new('RGB', picture.size, (255, 255, 255))
                alpha = picture.convert('RGBA')
                base.paste(alpha, mask=alpha.getchannel('A'))
                picture = base
            elif picture.mode != 'RGB':
                picture = picture.convert('RGB')
            picture.save(target, format='JPEG', quality=84, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, 'Neizdevās apstrādāt attēlu. Pamēģini JPG foto.')


class CodeInput(BaseModel):
    code: str = Field(min_length=1, max_length=20)

class PasswordInput(BaseModel):
    password: str

class ReviewInput(BaseModel):
    decision: str
    note: str = Field(default='', max_length=400)

class TaskInput(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=4, max_length=800)
    points: int = Field(ge=1, le=1000)
    emoji: str = Field(default='📸', max_length=12)
    category: str = Field(default='Foto', max_length=40)

class TeamInput(BaseModel):
    name: str = Field(min_length=2, max_length=45)


@app.get('/')
def index():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/admin')
def admin_page():
    return FileResponse(ROOT / 'static' / 'admin.html')

@app.get('/api/state')
def public_state(request: Request):
    team = current_team(request)
    with database() as db:
        tasks = [dict(row) for row in db.execute('SELECT id,title,description,points,emoji,category,reference_filename FROM tasks ORDER BY sort_order,id')]
        for task in tasks:
            task['has_reference'] = bool(task.pop('reference_filename'))
        if team:
            subs = {row['task_id']: dict(row) for row in db.execute('SELECT id,task_id,status,note,created_at FROM submissions WHERE team_id=?', (team['id'],))}
            for task in tasks:
                sub = subs.get(task['id'])
                task['submission'] = (sub | {'photo_url': f"/api/submission/{sub['id']}/photo"}) if sub else None
        return {'team': team, 'tasks': tasks, 'leaderboard': leaderboard(db), 'max_teams': 10, 'max_tasks': 10}

@app.post('/api/team/login')
def team_login(payload: CodeInput):
    with database() as db:
        row = db.execute('SELECT id,name FROM teams WHERE code=?', (payload.code.strip().upper(),)).fetchone()
    if not row:
        raise HTTPException(401, 'Nepareizs komandas kods. Pārbaudi un mēģini vēlreiz.')
    response = JSONResponse({'ok': True, 'team': dict(row)})
    set_cookie(response, 'kadrs_team', issue_token('team', row['id'], 30 * 86400), 30 * 86400)
    return response

@app.post('/api/team/logout')
def team_logout():
    response = JSONResponse({'ok': True})
    response.delete_cookie('kadrs_team', path='/')
    return response

@app.post('/api/team/upload/{task_id}')
async def upload_photo(task_id: int, request: Request, file: UploadFile = File(...)):
    team = require_team(request)
    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(400, 'Izvēlies fotoattēlu.')
    filename = secrets.token_hex(18) + '.jpg'
    path = UPLOAD_DIR / filename
    process_image(data, path)
    old_name = None
    try:
        with database() as db:
            if not db.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone():
                raise HTTPException(404, 'Uzdevums nav atrasts.')
            existing = db.execute('SELECT id,status,filename FROM submissions WHERE team_id=? AND task_id=?',
                                  (team['id'], task_id)).fetchone()
            if existing and existing['status'] != 'rejected':
                raise HTTPException(409, 'Šim uzdevumam foto jau iesniegts.')
            if existing:
                old_name = existing['filename']
                db.execute("UPDATE submissions SET filename=?, status='pending', note='', created_at=CURRENT_TIMESTAMP, reviewed_at=NULL WHERE id=?",
                           (filename, existing['id']))
            else:
                db.execute('INSERT INTO submissions (team_id,task_id,filename) VALUES (?,?,?)',
                           (team['id'], task_id, filename))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if old_name:
        (UPLOAD_DIR / old_name).unlink(missing_ok=True)
    return {'ok': True}

@app.get('/api/submission/{submission_id}/photo')
def submission_photo(submission_id: int, request: Request):
    with database() as db:
        row = db.execute('SELECT team_id,filename FROM submissions WHERE id=?', (submission_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Foto nav atrasts.')
    team = current_team(request)
    if not is_admin(request) and (not team or team['id'] != row['team_id']):
        raise HTTPException(403, 'Nav piekļuves šim foto.')
    path = UPLOAD_DIR / row['filename']
    if not path.is_file():
        raise HTTPException(404, 'Foto fails nav atrasts.')
    return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=60', 'X-Content-Type-Options': 'nosniff'})

@app.get('/api/reference/{task_id}')
def reference_photo(task_id: int):
    with database() as db:
        row = db.execute('SELECT reference_filename FROM tasks WHERE id=?', (task_id,)).fetchone()
    if not row or not row['reference_filename']:
        raise HTTPException(404, 'Uzdevumam nav parauga foto.')
    path = REFERENCE_DIR / row['reference_filename']
    if not path.is_file():
        raise HTTPException(404, 'Parauga foto nav atrasts.')
    return FileResponse(path, media_type='image/jpeg', headers={'X-Content-Type-Options': 'nosniff'})

@app.post('/api/admin/login')
def admin_login(payload: PasswordInput):
    if not hmac.compare_digest(payload.password, ADMIN_PASSWORD):
        raise HTTPException(401, 'Nepareiza administratora parole.')
    response = JSONResponse({'ok': True})
    set_cookie(response, 'kadrs_admin', issue_token('admin', 'ok', 12 * 3600), 12 * 3600)
    return response

@app.post('/api/admin/logout')
def admin_logout():
    response = JSONResponse({'ok': True})
    response.delete_cookie('kadrs_admin', path='/')
    return response

@app.get('/api/admin/state')
def admin_state(request: Request):
    require_admin(request)
    with database() as db:
        tasks = [dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY sort_order,id')]
        for task in tasks:
            task['has_reference'] = bool(task['reference_filename'])
        teams = [dict(r) for r in db.execute('SELECT id,name,code FROM teams ORDER BY id')]
        submissions = [dict(r) for r in db.execute('''
          SELECT s.id,s.team_id,s.task_id,s.status,s.note,s.created_at,s.reviewed_at,
                 t.name AS team_name, k.title AS task_title, k.points
          FROM submissions s JOIN teams t ON t.id=s.team_id JOIN tasks k ON k.id=s.task_id
          ORDER BY CASE s.status WHEN 'pending' THEN 0 WHEN 'rejected' THEN 1 ELSE 2 END,
                   s.created_at DESC, s.id DESC
        ''')]
        for sub in submissions:
            sub['photo_url'] = f"/api/submission/{sub['id']}/photo"
        return {'tasks': tasks, 'teams': teams, 'submissions': submissions, 'leaderboard': leaderboard(db)}

@app.post('/api/admin/review/{submission_id}')
def review(submission_id: int, payload: ReviewInput, request: Request):
    require_admin(request)
    if payload.decision not in ('approved', 'rejected'):
        raise HTTPException(400, 'Atļauts tikai apstiprināt vai noraidīt.')
    with database() as db:
        updated = db.execute('UPDATE submissions SET status=?,note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?',
                             (payload.decision, payload.note.strip(), submission_id))
        if updated.rowcount == 0:
            raise HTTPException(404, 'Iesniegums nav atrasts.')
    return {'ok': True}

@app.post('/api/admin/tasks')
def create_task(payload: TaskInput, request: Request):
    require_admin(request)
    with database() as db:
        if db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] >= 10:
            raise HTTPException(409, 'Spēlē var būt līdz 10 uzdevumiem.')
        order = db.execute('SELECT COALESCE(MAX(sort_order),0)+1 FROM tasks').fetchone()[0]
        cursor = db.execute('INSERT INTO tasks(title,description,points,emoji,category,sort_order) VALUES(?,?,?,?,?,?)',
                            (payload.title.strip(), payload.description.strip(), payload.points, payload.emoji.strip() or '📸',
                             payload.category.strip() or 'Foto', order))
    return {'ok': True, 'id': cursor.lastrowid}

@app.put('/api/admin/tasks/{task_id}')
def update_task(task_id: int, payload: TaskInput, request: Request):
    require_admin(request)
    with database() as db:
        updated = db.execute('UPDATE tasks SET title=?,description=?,points=?,emoji=?,category=? WHERE id=?',
                             (payload.title.strip(), payload.description.strip(), payload.points, payload.emoji.strip() or '📸',
                              payload.category.strip() or 'Foto', task_id))
        if updated.rowcount == 0:
            raise HTTPException(404, 'Uzdevums nav atrasts.')
    return {'ok': True}

@app.delete('/api/admin/tasks/{task_id}')
def delete_task(task_id: int, request: Request):
    require_admin(request)
    with database() as db:
        task = db.execute('SELECT reference_filename FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not task:
            raise HTTPException(404, 'Uzdevums nav atrasts.')
        if db.execute('SELECT 1 FROM submissions WHERE task_id=?', (task_id,)).fetchone():
            raise HTTPException(409, 'Uzdevumu ar iesniegumiem nevar dzēst.')
        db.execute('DELETE FROM tasks WHERE id=?', (task_id,))
    if task['reference_filename']:
        (REFERENCE_DIR / task['reference_filename']).unlink(missing_ok=True)
    return {'ok': True}

@app.post('/api/admin/tasks/{task_id}/reference')
async def task_reference(task_id: int, request: Request, file: UploadFile = File(...)):
    require_admin(request)
    data = await file.read(MAX_BYTES + 1)
    filename = secrets.token_hex(18) + '.jpg'
    path = REFERENCE_DIR / filename
    process_image(data, path)
    old_filename = None
    try:
        with database() as db:
            row = db.execute('SELECT reference_filename FROM tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Uzdevums nav atrasts.')
            old_filename = row['reference_filename']
            db.execute('UPDATE tasks SET reference_filename=? WHERE id=?', (filename, task_id))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if old_filename:
        (REFERENCE_DIR / old_filename).unlink(missing_ok=True)
    return {'ok': True}

@app.delete('/api/admin/tasks/{task_id}/reference')
def delete_task_reference(task_id: int, request: Request):
    require_admin(request)
    with database() as db:
        row = db.execute('SELECT reference_filename FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Uzdevums nav atrasts.')
        db.execute('UPDATE tasks SET reference_filename=NULL WHERE id=?', (task_id,))
    if row['reference_filename']:
        (REFERENCE_DIR / row['reference_filename']).unlink(missing_ok=True)
    return {'ok': True}

@app.post('/api/admin/teams')
def create_team(payload: TeamInput, request: Request):
    require_admin(request)
    with database() as db:
        if db.execute('SELECT COUNT(*) FROM teams').fetchone()[0] >= 10:
            raise HTTPException(409, 'Spēlē var būt līdz 10 komandām.')
        try:
            db.execute('INSERT INTO teams(name,code) VALUES (?,?)', (payload.name.strip(), create_code(db)))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'Komanda ar šādu nosaukumu jau ir.')
    return {'ok': True}

@app.delete('/api/admin/teams/{team_id}')
def delete_team(team_id: int, request: Request):
    require_admin(request)
    with database() as db:
        if db.execute('SELECT 1 FROM submissions WHERE team_id=?', (team_id,)).fetchone():
            raise HTTPException(409, 'Komandu ar iesniegtām bildēm nevar dzēst.')
        result = db.execute('DELETE FROM teams WHERE id=?', (team_id,))
        if result.rowcount == 0:
            raise HTTPException(404, 'Komanda nav atrasta.')
    return {'ok': True}
