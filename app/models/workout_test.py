from pydantic import BaseModel, conint, Field, validator
from typing import List

class WorkoutTest(BaseModel):
    answers: List[conint(ge=1, le=10)] = Field(
        ...,
        title="Ответы на вопросы",
        description="Список из 8 чисел (в диапазоне от 1 до 10), отвечающих на вопросы теста",
        examples=[5, 3, 5, 7, 3, 5, 8, 10]
    )

    @validator("answers")
    def check_length(cls, v):
        if len(v) != 8:
            raise ValueError("Все 8 вопросов должны быть заполнены")
        return v