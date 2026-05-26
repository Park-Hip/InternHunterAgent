from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async  def health_check():
    status_code = 200
    health_status = {"api": "online"}

    return {
        "health_status": health_status,
        "status_code": status_code
    }
