from fastapi import APIRouter

from src.logging_ import logger
from src.schedule_assistant.dependencies import VerifyTokenDep
from src.schedule_assistant.modules.issues import service
from src.schedule_assistant.modules.issues.schemas import CheckParameters, CheckResults

router = APIRouter(prefix="/issues", tags=["Issues"])


@router.post(
    "/check",
    responses={
        200: {"description": "Schedule issues"},
        401: {"description": "Invalid token OR no credentials provided"},
    },
)
async def check_schedule_issues(_user_and_token: VerifyTokenDep, params: CheckParameters) -> CheckResults:
    logger.info(f"Checking schedule issues with options: {params}")
    return await service.check_schedule_issues(params)
