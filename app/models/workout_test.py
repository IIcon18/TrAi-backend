from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import Base

class WorkoutTest(Base):
    __tablename__ = "workout_tests"

    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False, index=True)
    q1 = Column(Integer, nullable=False)
    q2 = Column(Integer, nullable=False)
    q3 = Column(Integer, nullable=False)
    q4 = Column(Integer, nullable=False)
    q5 = Column(Integer, nullable=False)
    q6 = Column(Integer, nullable=False)
    q7 = Column(Integer, nullable=False)
    q8 = Column(Integer, nullable=False)

    workout = relationship("Workout", back_populates="tests")