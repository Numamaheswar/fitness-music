from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

# Initialize FastAPI app
app = FastAPI(title="Fitness and Music App")

# Database configuration - Using SQLite
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'fitness_music.db')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security configuration
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class WorkoutCategory(Base):
    __tablename__ = "workout_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    description = Column(String(200), nullable=True)

# Fitness Models
class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    workout_type = Column(String)
    duration = Column(Float)
    calories_burned = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    music_playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=True)

class UserGoal(Base):
    __tablename__ = "user_goals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    goal_type = Column(String(50))
    target_value = Column(Float)
    deadline = Column(DateTime)

# Music Models
class Song(Base):
    __tablename__ = "songs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    artist = Column(String)
    duration = Column(Float)
    file_path = Column(String)
    genre = Column(String)
    bpm = Column(Integer, nullable=True)

class Playlist(Base):
    __tablename__ = "playlists"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    description = Column(String)
    is_workout_playlist = Column(Boolean, default=False)

class PlaylistSong(Base):
    __tablename__ = "playlist_songs"
    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"))
    song_id = Column(Integer, ForeignKey("songs.id"))
    position = Column(Integer)

# Create database tables
Base.metadata.create_all(bind=engine)

# Create uploads directory for songs
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "songs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GoalCreate(BaseModel):
    goal_type: str
    target_value: float
    deadline: datetime

class WorkoutCreate(BaseModel):
    workout_type: str
    duration: float
    calories_burned: float
    playlist_id: Optional[int] = None

class SongCreate(BaseModel):
    title: str
    artist: str
    duration: float
    genre: str
    bpm: Optional[int] = None

class PlaylistCreate(BaseModel):
    name: str
    description: str
    is_workout_playlist: bool = False

class WorkoutResponse(BaseModel):
    id: int
    workout_type: str
    duration: float
    calories_burned: float
    date: datetime
    music_playlist_id: Optional[int]

    class Config:
        orm_mode = True

class SongResponse(BaseModel):
    id: int
    title: str
    artist: str
    duration: float
    genre: str
    bpm: Optional[int]

    class Config:
        orm_mode = True

class PlaylistResponse(BaseModel):
    id: int
    name: str
    description: str
    is_workout_playlist: bool

    class Config:
        orm_mode = True

# Helper functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# API endpoints
@app.post("/users/", response_model=dict)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Workout endpoints
@app.post("/workouts/", response_model=dict)
async def create_workout(workout: WorkoutCreate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        db_workout = Workout(
            user_id=user.id,
            workout_type=workout.workout_type,
            duration=workout.duration,
            calories_burned=workout.calories_burned,
            music_playlist_id=workout.playlist_id
        )
        db.add(db_workout)
        db.commit()
        db.refresh(db_workout)
        return {"message": "Workout logged successfully"}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Music endpoints
@app.post("/songs/", response_model=dict)
async def create_song(
    song: SongCreate,
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Save file logic here
        file_path = f"uploads/songs/{file.filename}"
        
        db_song = Song(
            title=song.title,
            artist=song.artist,
            duration=song.duration,
            file_path=file_path,
            genre=song.genre,
            bpm=song.bpm
        )
        db.add(db_song)
        db.commit()
        db.refresh(db_song)
        return {"message": "Song added successfully"}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/playlists/", response_model=dict)
async def create_playlist(
    playlist: PlaylistCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        db_playlist = Playlist(
            user_id=user.id,
            name=playlist.name,
            description=playlist.description,
            is_workout_playlist=playlist.is_workout_playlist
        )
        db.add(db_playlist)
        db.commit()
        db.refresh(db_playlist)
        return {"message": "Playlist created successfully"}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/playlists/{playlist_id}/songs/{song_id}")
async def add_song_to_playlist(
    playlist_id: int,
    song_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        # Get current highest position
        max_position = db.query(PlaylistSong).filter(
            PlaylistSong.playlist_id == playlist_id
        ).count()
        
        playlist_song = PlaylistSong(
            playlist_id=playlist_id,
            song_id=song_id,
            position=max_position + 1
        )
        db.add(playlist_song)
        db.commit()
        return {"message": "Song added to playlist"}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Simple test endpoints to verify routing
@app.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint working"}

@app.get("/workouts/{workout_id}")
async def get_workout(
    workout_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        workout = db.query(Workout).filter(
            Workout.id == workout_id,
            Workout.user_id == user.id
        ).first()
        
        if workout is None:
            raise HTTPException(status_code=404, detail="Workout not found")
            
        return workout
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@app.put("/workouts/{workout_id}")
async def update_workout(
    workout_id: int,
    workout: WorkoutCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        db_workout = db.query(Workout).filter(
            Workout.id == workout_id,
            Workout.user_id == user.id
        ).first()
        
        if db_workout is None:
            raise HTTPException(status_code=404, detail="Workout not found")
            
        db_workout.workout_type = workout.workout_type
        db_workout.duration = workout.duration
        db_workout.calories_burned = workout.calories_burned
        
        db.commit()
        db.refresh(db_workout)
        return db_workout
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@app.delete("/workouts/{workout_id}")
async def delete_workout(
    workout_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        workout = db.query(Workout).filter(
            Workout.id == workout_id,
            Workout.user_id == user.id
        ).first()
        
        if workout is None:
            raise HTTPException(status_code=404, detail="Workout not found")
            
        db.delete(workout)
        db.commit()
        return {"message": "Workout deleted successfully"}
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

# Add some statistics endpoints
@app.get("/workouts/stats/total")
async def get_workout_stats(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        workouts = db.query(Workout).filter(Workout.user_id == user.id).all()
        
        total_workouts = len(workouts)
        total_duration = sum(w.duration for w in workouts)
        total_calories = sum(w.calories_burned for w in workouts)
        
        return {
            "total_workouts": total_workouts,
            "total_duration_minutes": total_duration,
            "total_calories_burned": total_calories
        }
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@app.post("/categories/")
async def create_category(
    category: CategoryCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        db_category = WorkoutCategory(**category.dict())
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return {"message": "Category created successfully"}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/categories/")
async def get_categories(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        categories = db.query(WorkoutCategory).all()
        return categories
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/goals/")
async def create_goal(
    goal: GoalCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        db_goal = UserGoal(
            user_id=user.id,
            goal_type=goal.goal_type,
            target_value=goal.target_value,
            deadline=goal.deadline
        )
        db.add(db_goal)
        db.commit()
        db.refresh(db_goal)
        return {"message": "Goal created successfully"}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/goals/")
async def get_goals(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        goals = db.query(UserGoal).filter(UserGoal.user_id == user.id).all()
        return goals
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/goals/progress")
async def get_goal_progress(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        goals = db.query(UserGoal).filter(UserGoal.user_id == user.id).all()
        workouts = db.query(Workout).filter(Workout.user_id == user.id).all()
        
        progress = []
        for goal in goals:
            if goal.goal_type == "calories":
                total_calories = sum(w.calories_burned for w in workouts)
                progress.append({
                    "goal_type": goal.goal_type,
                    "target": goal.target_value,
                    "current": total_calories,
                    "percentage": (total_calories / goal.target_value) * 100 if goal.target_value > 0 else 0
                })
            elif goal.goal_type == "duration":
                total_duration = sum(w.duration for w in workouts)
                progress.append({
                    "goal_type": goal.goal_type,
                    "target": goal.target_value,
                    "current": total_duration,
                    "percentage": (total_duration / goal.target_value) * 100 if goal.target_value > 0 else 0
                })
        
        return progress
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/workouts/", response_model=List[WorkoutResponse])
async def get_workouts(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        workouts = db.query(Workout).filter(Workout.user_id == user.id).all()
        return workouts
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/songs/", response_model=List[SongResponse])
async def get_songs(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        songs = db.query(Song).all()
        return songs
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/playlists/", response_model=List[PlaylistResponse])
async def get_playlists(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        playlists = db.query(Playlist).filter(Playlist.user_id == user.id).all()
        return playlists
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/playlists/{playlist_id}/songs", response_model=List[SongResponse])
async def get_playlist_songs(
    playlist_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        songs = db.query(Song).join(PlaylistSong).filter(
            PlaylistSong.playlist_id == playlist_id
        ).order_by(PlaylistSong.position).all()
        return songs
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/workouts/recommended_music")
async def get_recommended_music(
    workout_type: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Simple recommendation logic based on workout type
        recommended_bpm = {
            "running": (140, 160),
            "walking": (120, 140),
            "cycling": (130, 150),
            "hiit": (150, 170),
            "yoga": (60, 90),
            "strength": (130, 150)
        }
        
        workout_type = workout_type.lower()
        if workout_type in recommended_bpm:
            min_bpm, max_bpm = recommended_bpm[workout_type]
            songs = db.query(Song).filter(
                Song.bpm >= min_bpm,
                Song.bpm <= max_bpm
            ).all()
            return {
                "workout_type": workout_type,
                "recommended_bpm_range": f"{min_bpm}-{max_bpm}",
                "songs": songs
            }
        else:
            return {"message": "No specific recommendations for this workout type"}
            
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.delete("/playlists/{playlist_id}/songs/{song_id}")
async def remove_song_from_playlist(
    playlist_id: int,
    song_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        
        playlist_song = db.query(PlaylistSong).filter(
            PlaylistSong.playlist_id == playlist_id,
            PlaylistSong.song_id == song_id
        ).first()
        
        if playlist_song:
            db.delete(playlist_song)
            db.commit()
            return {"message": "Song removed from playlist"}
        else:
            raise HTTPException(status_code=404, detail="Song not found in playlist")
            
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token") 

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 
