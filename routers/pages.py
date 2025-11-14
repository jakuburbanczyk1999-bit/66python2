"""
Router: Pages
Odpowiedzialność: Static HTML pages (index, lobby, game)
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()

# ============================================
# MAIN PAGES
# ============================================

@router.get("/", response_class=FileResponse)
async def index():
    """Strona główna"""
    return FileResponse("static/index.html")

@router.get("/index.html", response_class=FileResponse)
async def index_alt():
    """Strona główna (alternatywna ścieżka)"""
    return FileResponse("static/index.html")

@router.get("/dashboard", response_class=FileResponse)
@router.get("/dashboard.html", response_class=FileResponse)
async def dashboard_page():
    """Dashboard - lista lobby"""
    return FileResponse("static/dashboard.html")

@router.get("/lobby", response_class=FileResponse)
@router.get("/lobby.html", response_class=FileResponse)
async def lobby_page():
    """Strona lobby"""
    return FileResponse("static/lobby.html")

@router.get("/game", response_class=FileResponse)
@router.get("/game.html", response_class=FileResponse)
async def game_page():
    """Strona gry"""
    return FileResponse("static/game.html")

@router.get("/zasady", response_class=FileResponse)
@router.get("/zasady.html", response_class=FileResponse)
async def zasady_page():
    """Strona z zasadami"""
    return FileResponse("static/zasady.html")

# ============================================
# ADDITIONAL PAGES (opcjonalnie)
# ============================================

@router.get("/rules", response_class=FileResponse)
@router.get("/rules.html", response_class=FileResponse)
async def rules_page():
    """Strona z zasadami gry (alias)"""
    return FileResponse("static/zasady.html")

@router.get("/profile", response_class=FileResponse)
@router.get("/profile.html", response_class=FileResponse)
async def profile_page():
    """Strona profilu gracza"""
    try:
        return FileResponse("static/profile.html")
    except:
        return HTMLResponse(content="""
        <html>
            <head><title>Profil</title></head>
            <body>
                <h1>Profil Gracza</h1>
                <p>Strona w budowie...</p>
                <a href="/">Powrót</a>
            </body>
        </html>
        """)

@router.get("/ranking", response_class=FileResponse)
@router.get("/ranking.html", response_class=FileResponse)
async def ranking_page():
    """Strona rankingu"""
    try:
        return FileResponse("static/ranking.html")
    except:
        return HTMLResponse(content="""
        <html>
            <head><title>Ranking</title></head>
            <body>
                <h1>Ranking Graczy</h1>
                <p>Strona w budowie...</p>
                <a href="/">Powrót</a>
            </body>
        </html>
        """)

# ============================================
# HEALTH CHECK / INFO
# ============================================

@router.get("/health", response_class=HTMLResponse)
async def health_check():
    """Health check endpoint"""
    return HTMLResponse(content="""
    <html>
        <head><title>Health Check</title></head>
        <body>
            <h1>✅ Serwer działa!</h1>
            <p>Miedziowe Karty - Gra w 66</p>
        </body>
    </html>
    """)