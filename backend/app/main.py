"""FastAPI Application Entry Point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.database import Base, Trade, Presale, Rental, SyncLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import os

# 載入 .env（支援專案根目錄或 backend/ 目錄）
for env_path in [".env", "../.env"]:
    load_dotenv(env_path, override=False)

# Support both PostgreSQL and SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hermes@localhost:5432/housing_tracker")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=5,           # 固定 5 個連線
    max_overflow=10,       # 高峰時最多再開 10 個
    pool_recycle=3600,     # 1 小時回收舊連線
    pool_pre_ping=True,    # 自動檢測斷線重連
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="房屋實價追蹤系統", version="1.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create tables on startup
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database initialized: {DATABASE_URL}")


# Import routers (lazy to avoid circular imports)
@app.on_event("startup")
def startup_routers():
    from app.routers import trades, stats, sync, rankings, amenities, radial_search, commute, scorecard, find, location_poi
    app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
    app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
    app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
    app.include_router(rankings.router, tags=["rankings"])
    app.include_router(amenities.router, prefix="/api", tags=["amenities"])
    app.include_router(radial_search.router, prefix="/api", tags=["radial-search"])
    app.include_router(commute.router, prefix="/api", tags=["commute"])
    app.include_router(scorecard.router, prefix="/api", tags=["scorecard"])
    app.include_router(find.router, prefix="/api", tags=["find"])
    app.include_router(location_poi.router, prefix="/api", tags=["location-poi"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ─── Batch scorecard endpoint (runs in backend env with sqlalchemy) ────
@app.post("/api/batch/scorecard")
def trigger_batch_scorecard():
    """Trigger batch scorecard computation for all trades without scores."""
    from datetime import datetime
    import threading
    
    def run_batch():
        from app.routers.scorecard import compute_scorecard_for_location, GLOBAL_REQUEST_COUNT
        from app.main import SessionLocal, engine
        from app.models.database import Trade
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            # Ensure columns exist
            db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='trades' AND column_name='score_overall') THEN
                        ALTER TABLE trades ADD COLUMN score_overall INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_transit INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_education INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_medical INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_shopping INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_leisure INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_dining INTEGER DEFAULT NULL;
                        ALTER TABLE trades ADD COLUMN score_updated_at TIMESTAMP DEFAULT NULL;
                    END IF;
                END $$;
            """))
            db.commit()
            
            trades = db.query(Trade).filter(
                Trade.lat != None, Trade.lon != None,
                Trade.score_overall == None
            ).order_by(Trade.id).all()
            
            success = 0
            failed = 0
            for i, t in enumerate(trades):
                try:
                    scores = compute_scorecard_for_location(t.lat, t.lon)
                    t.score_overall = scores["overall"]
                    t.score_transit = scores["transit"]
                    t.score_education = scores["education"]
                    t.score_medical = scores["medical"]
                    t.score_shopping = scores["shopping"]
                    t.score_leisure = scores["leisure"]
                    t.score_dining = scores["dining"]
                    t.score_updated_at = datetime.now()
                    success += 1
                    if (i + 1) % 10 == 0:
                        db.commit()
                        print(f"[{i+1}/{len(trades)}] ✓ {t.city}{t.district} → Overall: {scores['overall']}")
                except Exception as e:
                    failed += 1
                    print(f"[{i+1}/{len(trades)}] ✗ {t.city}{t.district} → {e}")
            
            db.commit()
            print(f"Done! Success: {success}, Failed: {failed}")
        finally:
            db.close()
    
    thread = threading.Thread(target=run_batch, daemon=True)
    thread.start()
    return {"status": "started", "message": "批次評分已在背景執行"}
