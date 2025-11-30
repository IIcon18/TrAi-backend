import os
import json
import httpx
from typing import Dict, Any, List


class AIService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

        print(f"Groq AI Service initialized. API Key: {'PRESENT' if self.api_key else 'NOT FOUND'}")

    async def _make_groq_request(self, prompt: str) -> str:
        if not self.api_key:
            raise Exception("AI сервис не настроен. Добавьте GROQ_API_KEY в .env файл")

        try:
            print(f"Sending request to Groq API...")
            print(f"Prompt: {prompt[:100]}...")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 500,
                        "stream": False
                    },
                    timeout=30.0
                )

                print(f"Groq API response status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    print(f"Groq response success!")

                    if "choices" in result and len(result["choices"]) > 0:
                        choice = result["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            text = choice["message"]["content"]
                            print(f"Groq response text: {text}")
                            return text
                    raise Exception("Неверный формат ответа от Groq API")
                else:
                    error_msg = f"Ошибка Groq API: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg += f" - {error_data['error']['message']}"
                    except:
                        error_msg += f" - {response.text}"
                    raise Exception(error_msg)

        except httpx.TimeoutException:
            raise Exception("Таймаут подключения к Groq API")
        except Exception as e:
            raise Exception(f"Ошибка подключения к Groq API: {str(e)}")

    def _analyze_workout_history(self, workout_history: List[Dict[str, Any]], target_muscle: str) -> str:
        """Проанализировать историю тренировок для промпта"""
        if not workout_history:
            return "История тренировок отсутствует. Это первая тренировка пользователя."

        recent_workouts = workout_history[-5:]
        muscle_frequency = {}
        common_exercises = []

        for workout in recent_workouts:
            exercises = workout.get('exercises', [])
            for exercise in exercises:
                muscle = exercise.get('muscle_group', '')
                exercise_name = exercise.get('name', '')
                if muscle:
                    muscle_frequency[muscle] = muscle_frequency.get(muscle, 0) + 1
                if exercise_name:
                    common_exercises.append(exercise_name)

        analysis = f"История тренировок: {len(recent_workouts)} последних записей\n"
        analysis += f"Частота тренируемых групп мышц: {muscle_frequency}\n"

        if target_muscle in muscle_frequency:
            analysis += f"Группа мышц '{target_muscle}' тренировалась {muscle_frequency[target_muscle]} раз в последних тренировках. "
            if muscle_frequency[target_muscle] >= 2:
                analysis += "Рекомендуется предложить новые упражнения для разнообразия.\n"
            else:
                analysis += "Можно продолжить развитие с прогрессией нагрузки.\n"
        else:
            analysis += f"Группа мышц '{target_muscle}' не тренировалась в последних тренировках. Можно дать базовые упражнения.\n"

        if common_exercises:
            from collections import Counter
            exercise_counts = Counter(common_exercises)
            frequent_exercises = [ex for ex, count in exercise_counts.items() if count >= 2]
            if frequent_exercises:
                analysis += f"Часто повторяющиеся упражнения: {', '.join(frequent_exercises[:3])}. Избегайте их повторения.\n"

        return analysis

    async def generate_dashboard_greeting(
            self,
            user_data: Dict[str, Any],
            quick_stats: Dict[str, Any],
            weekly_progress: Dict[str, Any],
            energy_data: List[Dict[str, Any]],
            last_workout: Dict[str, Any] = None
    ) -> str:
        """Сгенерировать персонализированное приветствие и анализ дашборда"""

        print(f"🎯 GENERATING DASHBOARD GREETING")
        print(f"🎯 User: {user_data.get('name', 'Unknown')}")
        print(f"🎯 Quick stats: {quick_stats}")
        print(f"🎯 Weekly progress: {weekly_progress}")

        # Анализируем последние данные энергии
        energy_analysis = ""
        if energy_data:
            recent_energy = [item.get('energy', 0) for item in energy_data[-3:]]  # Последние 3 дня
            avg_energy = sum(recent_energy) / len(recent_energy) if recent_energy else 0
            energy_analysis = f"Средний уровень энергии: {avg_energy:.1f}/10"
            if avg_energy >= 8:
                energy_analysis += " - отлично! 💪"
            elif avg_energy <= 5:
                energy_analysis += " - нужно больше отдыхать 😴"

        # Анализ последней тренировки
        last_workout_analysis = ""
        if last_workout:
            workout_date = last_workout.get('date', '')
            workout_type = last_workout.get('type', 'тренировка')
            last_workout_analysis = f"Последняя {workout_type} была {workout_date}"

        prompt = f"""
        Ты - персональный фитнес-тренер. Проанализируй данные пользователя и создай короткое, мотивирующее приветствие для дашборда.

        ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
        - Имя: {user_data.get('name', 'Спортсмен')}
        - Уровень: {user_data.get('level', 'beginner')}
        - Цель: {user_data.get('goal', 'general_fitness')}

        СТАТИСТИКА ЗА НЕДЕЛЮ:
        - Запланировано тренировок: {weekly_progress.get('planned_workouts', 0)}
        - Выполнено тренировок: {weekly_progress.get('completed_workouts', 0)}
        - Процент выполнения: {weekly_progress.get('completion_rate', 0)}%
        - Поднятый вес: {quick_stats.get('total_weight_lifted', 0)} кг
        - Восстановление: {quick_stats.get('recovery_score', 0)}%
        - Прогресс по цели: {quick_stats.get('goal_progress', 0)}%

        ДОПОЛНИТЕЛЬНО:
        {energy_analysis}
        {last_workout_analysis}

        ТРЕБОВАНИЯ К ПРИВЕТСТВИЮ:
        - Будь кратким (1-2 предложения)
        - Используй имя пользователя
        - Выдели главное достижение за неделю
        - Добавь мотивацию или рекомендацию
        - Используй эмодзи для выразительности
        - Будь позитивным и поддерживающим
        - Учитывай уровень энергии и восстановление

        ФОРМАТ: Только текст приветствия, без кавычек и дополнительного оформления.

        ПРИМЕРЫ ХОРОШИХ ПРИВЕТСТВИЙ:
        - "Привет, Алекс! На этой неделе ты выполнил 80% тренировок - отлично! 💪 Продолжай в том же духе!"
        - "Привет, Мария! Твое восстановление на высоте (85%) - это ключ к прогрессу! 🌟"
        - "Привет, Иван! Ты поднял 1500 кг за неделю - мощно! 🔥 Сфокусируйся на регулярности."
        - "Привет, Анна! Уровень энергии стабильный, отлично! 😊 Давай добавим еще одну тренировку на неделе!"

        СФОРМУЛИРУЙ ПРИВЕТСТВИЕ:
        """

        try:
            response = await self._make_groq_request(prompt)

            # Очистка ответа
            response = response.strip()
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]

            print(f"🎯 AI Greeting Response: {response}")
            return response

        except Exception as e:
            print(f"🎯 AI Greeting Error: {e}")
            # Fallback приветствие
            user_name = user_data.get('name', 'Спортсмен')
            return f"Привет, {user_name}! Рад видеть тебя снова! 💪"

    async def generate_profile_tips(self, user_data: Dict[str, Any], progress_data: Dict[str, Any]) -> List[str]:
        """Сгенерировать персональные советы для профиля через Groq"""
        print(f"Generating profile tips for user: {user_data}")

        prompt = f"""
        Ты - персональный фитнес-тренер. Сгенерируй 3 коротких практичных совета по фитнесу и питанию для пользователя.

        ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
        - Уровень подготовки: {user_data.get('level', 'начинающий')}
        - Цель: {user_data.get('goal', 'поддержание формы')}
        - Частота тренировок: {progress_data.get('workout_frequency', '3 раза в неделю')}

        ТРЕБОВАНИЯ:
        - Верни ТОЛЬКО 3 совета в формате: 
          1. Первый совет
          2. Второй совет  
          3. Третий совет
        - Каждый совет должен быть коротким (максимум 10 слов)
        - Советы должны быть практичными и конкретными
        - Используй только русский язык
        - Не добавляй никакого дополнительного текста, только нумерованный список

        ПРИМЕР:
        1. Регулярно пей воду во время тренировок
        2. Не пропускай разминку перед занятиями  
        3. Следи за осанкой при выполнении упражнений
        """

        response = await self._make_groq_request(prompt)
        print(f"=== FULL GROQ RESPONSE ===")
        print(response)
        print(f"=== END GROQ RESPONSE ===")

        tips = []
        lines = response.split('\n')

        for line in lines:
            line = line.strip()
            if line and line[0].isdigit():
                if '. ' in line:
                    tip = line.split('. ', 1)[1].strip()
                elif ') ' in line:
                    tip = line.split(') ', 1)[1].strip()
                else:
                    tip = line[1:].strip()

                if tip and len(tip) > 5 and len(tip) < 100:
                    tips.append(tip)

        print(f"Parsed tips: {tips}")

        if not tips:
            raise Exception("Не удалось сгенерировать советы через AI")

        return tips[:3]

    async def analyze_dish_nutrition(self, dish_name: str, grams: float) -> Dict[str, float]:
        """Проанализировать блюдо и рассчитать БЖУ через Groq"""
        prompt = f"""
        Ты - эксперт по питанию. Проанализируй блюдо и рассчитай пищевую ценность на {grams} грамм.

        БЛЮДО: {dish_name}
        ВЕС ПОРЦИИ: {grams} грамм

        ВЕРНИ ТОЛЬКО JSON БЕЗ ЛЮБЫХ ДОПОЛНИТЕЛЬНЫХ ТЕКСТОВ:

        {{
            "calories": число,
            "protein": число, 
            "fat": число,
            "carbs": число
        }}
        """

        response = await self._make_groq_request(prompt)
        print(f"Groq Response for {dish_name}: {response}")

        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                nutrition_data = json.loads(json_str)

                required_fields = ["calories", "protein", "fat", "carbs"]
                if all(field in nutrition_data for field in required_fields):
                    return nutrition_data
        except Exception as e:
            print(f"Nutrition Analysis Error: {e}")

        raise Exception("Не удалось проанализировать питательность блюда")

    async def generate_progress_analysis(
            self,
            chart_data: List[Dict[str, Any]],
            metric: str,
            user_data: Dict[str, Any]
    ) -> str:
        """Генерация AI анализа прогресса на основе данных графика"""
        print(f"Generating progress analysis for metric: {metric}")
        print(f"User data: {user_data}")
        print(f"Chart data points: {len(chart_data)}")

        if not chart_data:
            user_name = user_data.get('name', 'Спортсмен')
            return f"{user_name}, начните отслеживать прогресс, чтобы получать персональные рекомендации! 📊"

        trend_analysis = ""
        if len(chart_data) >= 2:
            first_value = chart_data[0]["value"]
            last_value = chart_data[-1]["value"]
            trend = last_value - first_value

            if metric == "weight":
                trend_percentage = (trend / first_value * 100) if first_value != 0 else 0
                trend_analysis = f"Изменение веса: {trend:+.1f} кг ({trend_percentage:+.1f}%) за период"
            elif metric == "body_fat":
                trend_percentage = (trend / first_value * 100) if first_value != 0 else 0
                trend_analysis = f"Изменение процента жира: {trend:+.1f}% ({trend_percentage:+.1f}%)"
            elif metric == "workouts":
                total_workouts = sum(item["value"] for item in chart_data)
                avg_workouts = total_workouts / len(chart_data)
                trend_analysis = f"Всего тренировок: {total_workouts}, средняя активность: {avg_workouts:.1f} в день"
            elif metric == "recovery":
                avg_recovery = sum(item["value"] for item in chart_data) / len(chart_data)
                min_recovery = min(item["value"] for item in chart_data)
                max_recovery = max(item["value"] for item in chart_data)
                trend_analysis = f"Среднее восстановление: {avg_recovery:.1f}%, диапазон: {min_recovery}-{max_recovery}%"

        prompt = f"""
        Ты - персональный фитнес-тренер. Проанализируй прогресс пользователя и дай краткий, мотивирующий анализ.

        ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
        - Имя: {user_data.get('name', 'Спортсмен')}
        - Уровень: {user_data.get('level', 'beginner')}
        - Цель: {user_data.get('goal', 'не указана')}
        - Метрика: {metric}

        ДАННЫЕ ПРОГРЕССА ({len(chart_data)} записей):
        {trend_analysis}

        ПОСЛЕДНИЕ 5 ЗАПИСЕЙ:
        {chr(10).join([f"{item['date']}: {item['value']} ({item['label']})" for item in chart_data[-5:]])}

        ТРЕБОВАНИЯ К ОТВЕТУ:
        - Будь кратким (2-3 предложения)
        - Анализируй тренд (улучшение/ухудшение/стабильность)
        - Дай конкретную рекомендацию или мотивацию
        - Используй эмодзи для наглядности
        - Будь позитивным и поддерживающим
        - Учитывай цель пользователя: {user_data.get('goal', 'общее развитие')}

        ПРИМЕРЫ ХОРОШИХ ОТВЕТОВ:
        - "Отличный прогресс! Вес снизился на 2.5 кг за месяц 🎉 Продолжайте в том же духе!"
        - "Заметен рост активности 💪 На этой неделе 5 тренировок - так держать!"
        - "Восстановление в норме (75%), но можно улучшить сон 😴"

        СФОРМУЛИРУЙ ОТВЕТ:
        """

        response = await self._make_groq_request(prompt)
        print(f"=== GROQ PROGRESS ANALYSIS RESPONSE ===")
        print(response)
        print(f"=== END GROGRESS ANALYSIS RESPONSE ===")

        response = response.strip()
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]

        return response

    async def generate_ai_workout(
            self,
            user_data: Dict[str, Any],
            muscle_group: str,
            workout_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Сгенерировать персонализированную AI тренировку с учетом истории"""

        print(f"🔧 AI WORKOUT GENERATION CALLED")
        print(f"🔧 User data: {user_data}")
        print(f"🔧 Muscle group: {muscle_group}")
        print(f"🔧 Workout history: {len(workout_history) if workout_history else 0} records")

        history_analysis = self._analyze_workout_history(workout_history, muscle_group)

        prompt = f"""
        Ты - персональный фитнес-тренер. Создай персонализированную тренировку.

        ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
        - Уровень: {user_data.get('level', 'beginner')}
        - Цель: {user_data.get('goal', 'general_fitness')}
        - Пол: {user_data.get('gender', 'not_specified')}
        - Возраст: {user_data.get('age', 'not_specified')}
        - Группа мышц: {muscle_group}

        ИСТОРИЯ ТРЕНИРОВОК:
        {history_analysis}

        ТРЕБОВАНИЯ:
        - Создай тренировку из 3-4 упражнений
        - Учитывай уровень подготовки пользователя
        - Упражнения должны быть безопасными
        - Учти историю тренировок: избегай повторов, предлагай прогрессию
        - Для начинающих: фокус на технике, базовые упражнения
        - Для продвинутых: более сложные упражнения, прогрессия нагрузки
        - Верни ответ в формате JSON:

        {{
            "name": "Название тренировки",
            "description": "Краткое описание",
            "exercises": [
                {{
                    "name": "Название упражнения",
                    "muscle_group": "группа мышц",
                    "sets": 3,
                    "reps": 10,
                    "intensity": "low/medium/high",
                    "reason": "почему выбрано это упражнение"
                }}
            ]
        }}

        ВАЖНО: Верни ТОЛЬКО JSON без дополнительного текста.
        """

        print(f"🔧 Sending request to Groq API...")

        try:
            response = await self._make_groq_request(prompt)
            print(f"🔧 Groq API response: {response}")

            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                workout_data = json.loads(json_str)
                return workout_data
        except Exception as e:
            print(f"🔧 AI Generation Error: {e}")
            raise Exception(f"Не удалось сгенерировать тренировку: {str(e)}")

    async def analyze_workout_performance(
            self,
            workout_data: Dict[str, Any],
            user_feedback: Dict[str, Any]
    ) -> str:
        """Проанализировать эффективность тренировки"""
        prompt = f"""
        Проанализируй эффективность тренировки и дай рекомендации.

        ТРЕНИРОВКА:
        {workout_data}

        ОБРАТНАЯ СВЯЗЬ ОТ ПОЛЬЗОВАТЕЛЯ:
        {user_feedback}

        Дай краткий анализ (2-3 предложения) и 1-2 рекомендации на русском.
        Будь конкретным и поддерживающим.
        """

        return await self._make_groq_request(prompt)


ai_service = AIService()