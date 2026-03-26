from fastapi import FastAPI, Query, APIRouter, HTTPException, status, Depends, Request
from sqlalchemy import select, text  # para conseguir manipular a base de dados
from models import User as UserModel
from models import UserIn as UserModelIn
from schema import User as UserSchema
from schema import UserValidate as UserSchemaValidate
from database import SessionDB, create_db_and_tables
from typing import List, Annotated
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os


from schema import Token, TokenData
from router import router_user


# modelo pydantic que vai ser usado para a token endpoint response


# faz codigo abaixo para criar os banco de dados quando a aplicação é inciada


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(router_user, prefix="/usuarios", tags=["Usuarios"])
