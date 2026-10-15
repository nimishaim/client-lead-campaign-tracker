from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.api.v1.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f'Starting {settings.APP_NAME} v{settings.APP_VERSION}')
    yield
    logger.info('Shutting down...')

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description='API for Client Lead & Campaign Tracker - manage leads, campaigns, and analytics.',
    docs_url='/api/docs',
    redoc_url='/api/redoc',
    openapi_url='/api/openapi.json',
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Routes
app.include_router(api_router, prefix='/api/v1')

@app.get('/health')
def health_check():
    return {'status': 'healthy', 'version': settings.APP_VERSION}

@app.get('/')
def root():
    return {'message': f'Welcome to {settings.APP_NAME}', 'docs': '/api/docs'}
