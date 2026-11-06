from fastapi import APIRouter

from app.api.routes import ask, documents, journals, me, tickets, utils

api_router = APIRouter()
api_router.include_router(me.router)
api_router.include_router(journals.router)
api_router.include_router(documents.router)
api_router.include_router(ask.router)
api_router.include_router(tickets.router)
api_router.include_router(utils.router)
