from datetime import timedelta, datetime, timezone
from http.client import HTTPException
from typing import Annotated

from pycparser.ply.yacc import token
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import  Depends, APIRouter
from starlette import status
from passlib.context import CryptContext
from database import SessionLocal
# decode JWT OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from models import Users
# Đầu tiên cần pip install "python-jose[cryptography]"
from jose import jwt, JWTError


router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

# openssl rand -hex 32
SECRET_KEY = '197b2c37c391bed93fe80344fe73b806947a65e36206e05a1a23c2fa12702fe3'
ALGORITHM = 'HS256'


# use our hasing algorithm of Bcrypt
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')


class CreateUserRequest(BaseModel):
    username:str
    email: str
    first_name: str
    last_name: str
    password: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str

def get_db():
    #Đây là một đối tượng session được tạo ra từ SQLAlchemy để kết nối với cơ sở dữ liệu.
    db = SessionLocal()
    try:
        #Câu lệnh này trả về session cho một lần sử dụng trong các endpoint API
       # trả về ngay lập tức thay về lặp qua tất cả rồi mới trả về
        yield db
    finally:
        # Đảm bảo rằng kết nối cơ sở dữ liệu sẽ được đóng sau khi hoàn thành việc sử dụng
        db.close()

def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {'sub':username, 'id': user_id}
    expires = datetime.now(timezone.utc) +expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

db_dependency = Annotated[Session, Depends(get_db)]

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        return {'username': username, 'id': user_id }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user.')


def authenticate_user(username:str, password:str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password,user.hashed_password):
        return False
    return user


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db:db_dependency, create_user_request: CreateUserRequest):
    create_user_model = Users(
        email=create_user_request.email,
        username=create_user_request.username,
        first_name=create_user_request.first_name,
        last_name=create_user_request.last_name,
        role=create_user_request.role,
        hashed_password=bcrypt_context.hash(create_user_request.password),
        is_active=True
    )

    db.add(create_user_model)
    db.commit()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                 db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)

    if not user:
        return 'Failed Authentication'
    token = create_access_token(user.username, user.id, timedelta(minutes=20))

    return {'access_token': token, 'token_type': 'bearer'}


