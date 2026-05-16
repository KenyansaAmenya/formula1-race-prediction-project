from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.utils.db import get_db
from src.utils.logger import get_logger
from src.utils.security import UserContext, get_current_user

logger = get_logger(__name__)
router = APIRouter()
db = get_db()


@router.get("/drivers")
async def get_drivers(
    year: Optional[int] = Query(None, description="Filter by season"),
    current_user: UserContext = Depends(get_current_user)
):
    if year:
        query = """
        SELECT DISTINCT d.* 
        FROM drivers d
        JOIN results res ON d.driver_id = res.driver_id
        JOIN races r ON res.race_id = r.race_id
        WHERE r.year = :year
        ORDER BY d.surname
        """
        params = {"year": year}
    else:
        query = "SELECT * FROM drivers ORDER BY surname"
        params = {}
    
    return db.execute_query(query, params)


@router.get("/drivers/{driver_id}")
async def get_driver(
    driver_id: int,
    current_user: UserContext = Depends(get_current_user)
):
    query = "SELECT * FROM drivers WHERE driver_id = :driver_id"
    result = db.execute_query(query, {"driver_id": driver_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    return result[0]

@router.get("/races")
async def get_races(
    year: Optional[int] = Query(None, description="Filter by season"),
    current_user: UserContext = Depends(get_current_user)
):
    if year:
        query = """
        SELECT r.*, c.name as circuit_name, c.country
        FROM races r
        JOIN circuits c ON r.circuit_id = c.circuit_id
        WHERE r.year = :year
        ORDER BY r.round
        """
        params = {"year": year}
    else:
        query = """
        SELECT r.*, c.name as circuit_name, c.country
        FROM races r
        JOIN circuits c ON r.circuit_id = c.circuit_id
        ORDER BY r.year DESC, r.round
        """
        params = {}
    
    return db.execute_query(query, params)


@router.get("/constructors")
async def get_constructors(
    year: Optional[int] = Query(None),
    current_user: UserContext = Depends(get_current_user)
):
    if year:
        query = """
        SELECT DISTINCT c.*
        FROM constructors c
        JOIN results res ON c.constructor_id = res.constructor_id
        JOIN races r ON res.race_id = r.race_id
        WHERE r.year = :year
        """
        params = {"year": year}
    else:
        query = "SELECT * FROM constructors ORDER BY name"
        params = {}
    
    return db.execute_query(query, params)


@router.get("/standings/{year}")
async def get_standings(
    year: int,
    current_user: UserContext = Depends(get_current_user)
):
    query = """
    SELECT 
        d.driver_id,
        d.forename || ' ' || d.surname as driver_name,
        c.name as constructor_name,
        SUM(res.points) as total_points,
        COUNT(CASE WHEN res.position = 1 THEN 1 END) as wins,
        COUNT(CASE WHEN res.position <= 3 THEN 1 END) as podiums,
        AVG(res.position_order) as avg_finish
    FROM results res
    JOIN races r ON res.race_id = r.race_id
    JOIN drivers d ON res.driver_id = d.driver_id
    JOIN constructors c ON res.constructor_id = c.constructor_id
    WHERE r.year = :year
    GROUP BY d.driver_id, d.forename, d.surname, c.name
    ORDER BY total_points DESC
    """
    
    return db.execute_query(query, {"year": year})