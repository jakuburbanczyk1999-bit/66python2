"""
Admin middleware - sprawdzanie uprawnień administratora
"""
from fastapi import HTTPException, Depends
from dependencies import get_current_user


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """
    Dependency do sprawdzania czy użytkownik jest adminem.
    Używaj tego zamiast get_current_user w endpointach admina.
    
    Usage:
        @router.get("/admin/something")
        async def admin_endpoint(admin: dict = Depends(get_current_admin)):
            # Tylko admin może to wywołać
            pass
    """
    # Sprawdź czy użytkownik ma uprawnienia admina
    # Zakładam że masz tabelę admins z id_uzytkownika
    from database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id_uzytkownika 
            FROM admins 
            WHERE id_uzytkownika = %s
        """, (current_user['id'],))
        
        is_admin = cursor.fetchone()
        
        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Brak uprawnień administratora"
            )
        
        return current_user
        
    finally:
        cursor.close()
        conn.close()