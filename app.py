import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL tidak ditemukan.\n"
        "Pastikan file .env berisi:\n"
        "DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE"
    )


# ============================================================
# DATABASE ENGINE
# ============================================================

# ini kode lama yang connect ke timesclase db
# engine = create_engine(
#     DATABASE_URL,
#     pool_pre_ping=True,
#     pool_recycle=1800,
# )

# ini kode baru yang connect ke supabase db

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    # Tambahkan ini untuk Supabase:
    connect_args={"sslmode": "require"},
)

# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="AMPERE Smart Plug API",
    description="API untuk menerima data Smart Plug ESP32",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATA MODEL
# ============================================================

class SmartPlugData(BaseModel):
    device_id: str

    voltage: float
    current: float
    power: float
    energy: float
    frequency: float
    power_factor: float


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "AMPERE Smart Plug API is running",
        "version": "1.0.0"
    }


# ============================================================
# HEALTH CHECK DATABASE
# ============================================================

@app.get("/api/smartplug/health")
def health_check():

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text("SELECT 1")
            )

            result.fetchone()

        return {
            "success": True,
            "database": "connected"
        }

    except Exception as e:

        print("\n================================")
        print("DATABASE HEALTH CHECK FAILED")
        print("================================")
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "database": "disconnected",
                "error_type": type(e).__name__,
                "error": str(e)
            }
        )


# ============================================================
# DATABASE INFORMATION
# ============================================================

@app.get("/api/smartplug/db-info")
def database_info():

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text(
                    """
                    SELECT
                        current_database() AS database,
                        current_schema() AS schema,
                        current_user AS user
                    """
                )
            )

            row = result.mappings().first()

        return {
            "success": True,
            "database": row["database"],
            "schema": row["schema"],
            "user": row["user"]
        }

    except Exception as e:

        print("\n================================")
        print("DATABASE INFO FAILED")
        print("================================")
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CHECK TABLE
# ============================================================

@app.get("/api/smartplug/check-table")
def check_table():

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text(
                    """
                    SELECT
                        table_schema,
                        table_name
                    FROM information_schema.tables
                    WHERE table_name = 'smartplug_measurements'
                    ORDER BY table_schema
                    """
                )
            )

            rows = result.mappings().all()

        return {
            "success": True,
            "count": len(rows),
            "tables": rows
        }

    except Exception as e:

        print("\n================================")
        print("CHECK TABLE FAILED")
        print("================================")
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# RECEIVE SMART PLUG DATA
# ============================================================

@app.post("/api/smartplug/data")
def receive_smartplug_data(data: SmartPlugData):

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    timestamp = datetime.now(timezone.utc)


    # --------------------------------------------------------
    # PRINT DATA FROM ESP32
    # --------------------------------------------------------

    print("\n")
    print("========================================")
    print("DATA DARI ESP32")
    print("========================================")

    print("Device ID    :", data.device_id)
    print("Voltage      :", data.voltage, "V")
    print("Current      :", data.current, "A")
    print("Power        :", data.power, "W")
    print("Energy       :", data.energy, "kWh")
    print("Frequency    :", data.frequency, "Hz")
    print("Power Factor :", data.power_factor)
    print("Timestamp    :", timestamp)

    print("========================================")


    # --------------------------------------------------------
    # INSERT QUERY
    # --------------------------------------------------------

    query = text(
        """
        INSERT INTO smartplug_measurements (
            time,
            device_id,
            voltage,
            current,
            power,
            energy,
            frequency,
            power_factor
        )
        VALUES (
            :time,
            :device_id,
            :voltage,
            :current,
            :power,
            :energy,
            :frequency,
            :power_factor
        )
        """
    )


    # --------------------------------------------------------
    # INSERT DATABASE
    # --------------------------------------------------------

    try:

        with engine.begin() as connection:

            connection.execute(
                query,
                {
                    "time": timestamp,
                    "device_id": data.device_id,
                    "voltage": data.voltage,
                    "current": data.current,
                    "power": data.power,
                    "energy": data.energy,
                    "frequency": data.frequency,
                    "power_factor": data.power_factor,
                }
            )


        # ----------------------------------------------------
        # SUCCESS LOG
        # ----------------------------------------------------

        print("DATABASE     : INSERT SUCCESS")
        print("Device       :", data.device_id)
        print("========================================")


        return {
            "success": True,
            "message": "Data berhasil diterima dan disimpan",
            "device_id": data.device_id,
            "timestamp": timestamp
        }


    # --------------------------------------------------------
    # DATABASE ERROR
    # --------------------------------------------------------

    except SQLAlchemyError as e:

        print("\n")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("DATABASE : INSERT FAILED")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("\n")


        # IMPORTANT:
        # Jangan return JSON success=False dengan HTTP 200.
        # Gunakan HTTP 500 supaya ESP32 tahu bahwa server gagal.

        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Data diterima tetapi gagal disimpan ke database",
                "error_type": type(e).__name__,
                "error": str(e)
            }
        )


    except Exception as e:

        print("\n")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("UNEXPECTED ERROR")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("\n")


        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Terjadi error pada server",
                "error_type": type(e).__name__,
                "error": str(e)
            }
        )


# ============================================================
# GET LATEST DATA
# ============================================================

@app.get("/api/smartplug/latest")
def get_latest_data():

    query = text(
        """
        SELECT
            time,
            device_id,
            voltage,
            current,
            power,
            energy,
            frequency,
            power_factor
        FROM smartplug_measurements
        ORDER BY time DESC
        LIMIT 10
        """
    )


    try:

        with engine.connect() as connection:

            result = connection.execute(query)

            rows = result.mappings().all()


        return {
            "success": True,
            "count": len(rows),
            "data": rows
        }


    except Exception as e:

        print("\n================================")
        print("GET LATEST DATA FAILED")
        print("================================")

        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))


        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error_type": type(e).__name__,
                "error": str(e)
            }
        )


# ============================================================
# GET DATA BY DEVICE
# ============================================================

@app.get("/api/smartplug/{device_id}")
def get_device_data(device_id: str):

    query = text(
        """
        SELECT
            time,
            device_id,
            voltage,
            current,
            power,
            energy,
            frequency,
            power_factor
        FROM smartplug_measurements
        WHERE device_id = :device_id
        ORDER BY time DESC
        LIMIT 100
        """
    )


    try:

        with engine.connect() as connection:

            result = connection.execute(
                query,
                {
                    "device_id": device_id
                }
            )

            rows = result.mappings().all()


        return {
            "success": True,
            "device_id": device_id,
            "count": len(rows),
            "data": rows
        }


    except Exception as e:

        print("\n================================")
        print("GET DEVICE DATA FAILED")
        print("================================")

        print("Device ID  :", device_id)
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))


        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error_type": type(e).__name__,
                "error": str(e)
            }
        )


@app.get("/api/smartplug/{device_id}/latest")
def get_latest_reading(device_id: str):
    

    query = text(
        """
        SELECT
            time,
            device_id,
            voltage,
            current,
            power,
            energy,
            frequency,
            power_factor
        FROM smartplug_measurements
        WHERE device_id = :device_id
        ORDER BY time DESC
        LIMIT 1
        """
    )

    try:

        with engine.connect() as connection:

            result = connection.execute(
                query,
                {
                    "device_id": device_id
                }
            )

            row = result.mappings().first()

        if row is None:

            raise HTTPException(
                status_code=404,
                detail=f"Device '{device_id}' belum memiliki data"
            )

        return {
            "success": True,
            "data": row
        }

    except HTTPException:
        raise

    except Exception as e:

        print("GET LATEST FAILED")
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/api/smartplug/{device_id}/history")
def get_history(
    device_id: str,
    limit: int = 100
):

    if limit < 1:
        limit = 1

    if limit > 1000:
        limit = 1000

    query = text(
        """
        SELECT
            time,
            device_id,
            voltage,
            current,
            power,
            energy,
            frequency,
            power_factor
        FROM smartplug_measurements
        WHERE device_id = :device_id
        ORDER BY time DESC
        LIMIT :limit
        """
    )

    try:

        with engine.connect() as connection:

            result = connection.execute(
                query,
                {
                    "device_id": device_id,
                    "limit": limit
                }
            )

            rows = result.mappings().all()

        return {
            "success": True,
            "device_id": device_id,
            "count": len(rows),
            "data": rows
        }

    except Exception as e:

        print("GET HISTORY FAILED")
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/api/smartplug/{device_id}/summary")
def get_summary(device_id: str):

    query = text(
        """
        SELECT
            COUNT(*) AS total_readings,

            AVG(power) AS average_power,

            MAX(power) AS peak_power,

            MIN(power) AS minimum_power,

            AVG(voltage) AS average_voltage,

            AVG(current) AS average_current,

            AVG(power_factor) AS average_power_factor

        FROM smartplug_measurements

        WHERE device_id = :device_id
        """
    )

    try:

        with engine.connect() as connection:

            result = connection.execute(
                query,
                {
                    "device_id": device_id
                }
            )

            row = result.mappings().first()

        return {
            "success": True,
            "device_id": device_id,
            "data": row
        }

    except Exception as e:

        print("GET SUMMARY FAILED")
        print("Error Type :", type(e).__name__)
        print("Error      :", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )