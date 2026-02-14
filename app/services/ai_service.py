import os
import json
import httpx
import re
from typing import Dict, Any, List


class AIService:
    @staticmethod
    def _extract_json_from_response(text: str) -> str:
        """Извлечь JSON из ответа AI (может быть обернут в markdown)"""
        # Убираем markdown блоки ```json ... ``` или ``` ... ```
        text = text.strip()

        # Паттерн для markdown кодблока
        markdown_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(markdown_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Ищем просто JSON объект
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return text.strip()

    @staticmethod
    def _extract_text_from_response(text: str) -> str:
        """Извлечь текст из ответа AI (может быть JSON или просто текст)"""
        text = text.strip()

        # Убираем markdown блоки сначала
        markdown_pattern = r'```(?:json)?\s*(.*?)\s*```'
        match = re.search(markdown_pattern, text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        # Пробуем парсить как JSON
        try:
            data = json.loads(text)
            # Если JSON - ищем поля с текстом
            if isinstance(data, dict):
                # Ищем поля: message, greeting, text, content
                for key in ['message', 'greeting', 'text', 'content', 'response']:
                    if key in data:
                        return str(data[key]).strip()
            return text
        except:
            # Не JSON - просто текст
            # Убираем кавычки если есть
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            return text.strip()
    def __init__(self):
        # API ключи для разных провайдеров
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        self.last_used_provider = None  # Для tracking

        print(f"AI Service initialized:")
        print(f"  - GitHub Models: {'✅' if self.github_token else '❌'}")
        print(f"  - Gemini: {'✅' if self.gemini_api_key else '❌'}")

    async def _make_github_request(self, prompt: str) -> str:
        """Запрос к GitHub Models API"""
        if not self.github_token:
            raise Exception("GitHub token не настроен")

        try:
            print(f"📤 Sending request to GitHub Models...")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://models.inference.ai.azure.com/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.github_token}"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful AI assistant. Always respond with valid JSON when requested."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    timeout=30.0
                )

                print(f"GitHub Models response status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        text = result["choices"][0]["message"]["content"]
                        print(f"✅ GitHub Models response: {text[:100]}...")
                        self.last_used_provider = "github_models"
                        return text
                    raise Exception("Invalid GitHub Models response format")
                else:
                    error_msg = f"GitHub Models error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg += f" - {error_data['error'].get('message', '')}"
                    except:
                        error_msg += f" - {response.text[:200]}"
                    raise Exception(error_msg)

        except httpx.TimeoutException:
            raise Exception("GitHub Models timeout")
        except Exception as e:
            raise Exception(f"GitHub Models error: {str(e)}")

    async def _make_gemini_request(self, prompt: str) -> str:
        """Запрос к Google Gemini API"""
        if not self.gemini_api_key:
            raise Exception("Gemini API key не настроен")

        try:
            print(f"📤 Sending request to Gemini...")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [{
                                "text": f"You are a nutrition expert. {prompt}"
                            }]
                        }],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 2000
                        }
                    },
                    timeout=30.0
                )

                print(f"Gemini response status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and len(result["candidates"]) > 0:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"✅ Gemini response: {text[:100]}...")
                        self.last_used_provider = "gemini"
                        return text
                    raise Exception("Invalid Gemini response format")
                else:
                    error_msg = f"Gemini error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg += f" - {error_data['error'].get('message', '')}"
                    except:
                        error_msg += f" - {response.text[:200]}"
                    raise Exception(error_msg)

        except httpx.TimeoutException:
            raise Exception("Gemini timeout")
        except Exception as e:
            raise Exception(f"Gemini error: {str(e)}")

    async def _make_ai_request(self, prompt: str) -> str:
        """
        Универсальный метод для AI запросов с fallback цепочкой.
        Пробует GitHub Models → Gemini
        """
        providers = []

        if self.github_token:
            providers.append(("GitHub Models", self._make_github_request))
        if self.gemini_api_key:
            providers.append(("Gemini", self._make_gemini_request))

        if not providers:
            raise Exception("Нет доступных AI провайдеров. Настройте GITHUB_TOKEN или GEMINI_API_KEY")

        last_error = None

        for provider_name, provider_func in providers:
            try:
                print(f"🔄 Trying {provider_name}...")
                response = await provider_func(prompt)
                return response
            except Exception as e:
                print(f"❌ {provider_name} failed: {e}")
                last_error = e
                continue

        # Все провайдеры упали
        raise Exception(f"Все AI провайдеры недоступны. Последняя ошибка: {last_error}")

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

        energy_analysis = ""
        if energy_data:
            recent_energy = [item.get('energy', 0) for item in energy_data[-3:]]  # Последние 3 дня
            avg_energy = sum(recent_energy) / len(recent_energy) if recent_energy else 0
            energy_analysis = f"Средний уровень энергии: {avg_energy:.1f}/10"
            if avg_energy >= 8:
                energy_analysis += " - отлично! 💪"
            elif avg_energy <= 5:
                energy_analysis += " - нужно больше отдыхать 😴"

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
            response = await self._make_ai_request(prompt)

            # Извлекаем текст (может быть JSON или просто текст)
            text = self._extract_text_from_response(response)

            print(f"🎯 AI Greeting Response: {text}")
            return text

        except Exception as e:
            print(f"🎯 AI Greeting Error: {e}")
            # Fallback приветствие
            user_name = user_data.get('name', 'Спортсмен')
            return f"Привет, {user_name}! Рад видеть тебя снова! 💪"

    async def generate_last_training_message(self, last_workout: Dict[str, Any] = None) -> str:
        """Сгенерировать короткое сообщение о последней тренировке"""
        if not last_workout:
            return "Начни свою первую тренировку! 💪"
        
        workout_date = last_workout.get('date', '')
        workout_type = last_workout.get('type', 'тренировка')
        duration = last_workout.get('duration', 60)
        
        prompt = f"""
        Создай ОДНО короткое предложение (максимум 10 слов) о последней тренировке пользователя.
        
        ДАННЫЕ:
        - Дата: {workout_date}
        - Тип: {workout_type}
        - Длительность: {duration} минут
        
        ТРЕБОВАНИЯ:
        - Только одно короткое предложение
        - Максимум 10 слов
        - Будь мотивирующим и позитивным
        - Используй эмодзи (1-2 штуки)
        - Формат: "Your last training was [описание]"
        
        ПРИМЕРЫ:
        - "Your last training was upper body push yesterday 💪"
        - "Your last training was 60 min workout 2 days ago 🔥"
        - "Your last training was leg day on Monday 🦵"
        
        СФОРМУЛИРУЙ СООБЩЕНИЕ:
        """
        
        try:
            response = await self._make_ai_request(prompt)
            response = response.strip()
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]
            # Ограничиваем длину
            words = response.split()
            if len(words) > 12:
                response = ' '.join(words[:12])
            return response
        except Exception as e:
            print(f"AI Last Training Message Error: {e}")
            return f"Your last training was {workout_type} on {workout_date} 💪"

    async def generate_weekly_progress_message(
        self, 
        weekly_progress: Dict[str, Any],
        quick_stats: Dict[str, Any]
    ) -> str:
        """Сгенерировать короткое сообщение под прогресс-баром"""
        completed = weekly_progress.get('completed_workouts', 0)
        planned = weekly_progress.get('planned_workouts', 0)
        completion_rate = weekly_progress.get('completion_rate', 0)
        weight_lifted = quick_stats.get('total_weight_lifted', 0)
        
        prompt = f"""
        Создай ОДНО короткое мотивирующее предложение (максимум 8 слов) о прогрессе тренировок за неделю.
        
        ДАННЫЕ:
        - Выполнено тренировок: {completed} из {planned}
        - Процент выполнения: {completion_rate}%
        - Поднятый вес: {weight_lifted} кг
        
        ТРЕБОВАНИЯ:
        - Только одно короткое предложение
        - Максимум 8 слов
        - Будь мотивирующим
        - Используй эмодзи (1 штука)
        - Если прогресс хороший - похвали, если плохой - мотивируй
        
        ПРИМЕРЫ:
        - "Отличная неделя! Продолжай в том же духе! 🔥"
        - "Хороший прогресс! Еще немного усилий! 💪"
        - "Ты на правильном пути! Так держать! ⚡"
        - "Добавь еще одну тренировку на этой неделе! 🎯"
        
        СФОРМУЛИРУЙ СООБЩЕНИЕ:
        """
        
        try:
            response = await self._make_ai_request(prompt)

            # Извлекаем текст (может быть JSON или просто текст)
            text = self._extract_text_from_response(response)

            # Ограничиваем длину
            words = text.split()
            if len(words) > 10:
                text = ' '.join(words[:10])
            return text
        except Exception as e:
            print(f"AI Weekly Progress Message Error: {e}")
            if completion_rate >= 80:
                return "Отличная неделя! Продолжай! 🔥"
            elif completion_rate >= 50:
                return "Хороший прогресс! Так держать! 💪"
            else:
                return "Добавь еще тренировку на этой неделе! 🎯"

    async def generate_profile_tips(self, user_data: Dict[str, Any], progress_data: Dict[str, Any]) -> List[str]:
        """Сгенерировать персональные советы для профиля через AI"""
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

        response = await self._make_ai_request(prompt)
        print(f"=== FULL AI RESPONSE ===")
        print(response)
        print(f"=== END AI RESPONSE ===")

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
        """
        Проанализировать блюдо и рассчитать БЖУ через AI с fallback цепочкой.
        Порядок: GitHub Models → Gemini
        """
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

        # Fallback chain: пробуем провайдеров по порядку
        providers = []

        if self.github_token:
            providers.append(("GitHub Models", self._make_github_request))
        if self.gemini_api_key:
            providers.append(("Gemini", self._make_gemini_request))

        last_error = None

        for provider_name, provider_func in providers:
            try:
                print(f"🔄 Trying {provider_name} for dish analysis...")
                response = await provider_func(prompt)
                print(f"Response from {provider_name}: {response[:200]}...")

                # Парсим JSON из ответа (убираем markdown блоки если есть)
                json_str = self._extract_json_from_response(response)
                nutrition_data = json.loads(json_str)

                required_fields = ["calories", "protein", "fat", "carbs"]
                if all(field in nutrition_data for field in required_fields):
                    print(f"✅ Success with {provider_name}!")
                    return nutrition_data

            except Exception as e:
                print(f"❌ {provider_name} failed: {e}")
                last_error = e
                continue

        # Все провайдеры упали
        error_msg = f"Все AI провайдеры недоступны. Последняя ошибка: {last_error}"
        raise Exception(error_msg)

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

        response = await self._make_ai_request(prompt)
        print(f"=== AI PROGRESS ANALYSIS RESPONSE ===")
        print(response)
        print(f"=== END PROGRESS ANALYSIS RESPONSE ===")

        # Извлекаем текст (может быть JSON или markdown)
        text = self._extract_text_from_response(response)

        return text

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

        ТРЕБОВАНИЯ К ТРЕНИРОВКЕ:
        - Создай тренировку из 3-4 упражнений
        - Упражнения должны быть безопасными и эффективными
        - Учитывай уровень подготовки пользователя
        - Учти историю тренировок: избегай повторов, предлагай прогрессию
        - Для начинающих: фокус на технике, базовые упражнения с собственным весом
        - Для продвинутых: более сложные упражнения, добавляй оборудование

        ТРЕБОВАНИЯ К УПРАЖНЕНИЯМ:
        - Название должно быть понятным и описательным (не "Супермен", а "Подъем корпуса лежа на животе (супермен)")
        - Description - ОБЯЗАТЕЛЬНО короткая (1-2 предложения) инструкция КАК ВЫПОЛНЯТЬ упражнение
        - Equipment - укажи какое оборудование нужно: "bodyweight" (собственный вес), "dumbbells" (гантели), "barbell" (штанга), "resistance_band" (резинка), "none" (без оборудования)
        - Weight - указывай ТОЛЬКО если equipment требует вес (гантели/штанга), иначе 0
        - Интенсивность: варьируй между low/medium/high в рамках одной тренировки
        - Sets/Reps: подбирай под уровень пользователя (начинающий: 3x8-10, средний: 3-4x10-12, продвинутый: 4-5x12-15)

        ПРИМЕРЫ ХОРОШИХ УПРАЖНЕНИЙ:
        {{
            "name": "Отжимания от пола",
            "description": "Прими упор лежа, руки на ширине плеч. Опустись вниз, коснувшись грудью пола, затем выпрямись.",
            "equipment": "bodyweight",
            "muscle_group": "upper_body_push",
            "sets": 3,
            "reps": 10,
            "weight": 0,
            "intensity": "medium"
        }}

        {{
            "name": "Приседания с гантелями",
            "description": "Держи гантели в руках, ноги на ширине плеч. Присядь до параллели с полом, затем вернись в исходное положение.",
            "equipment": "dumbbells",
            "muscle_group": "lower_body",
            "sets": 4,
            "reps": 12,
            "weight": 10,
            "intensity": "high"
        }}

        ФОРМАТ JSON:
        {{
            "name": "Название тренировки",
            "description": "Краткое описание тренировки (1 предложение)",
            "exercises": [
                {{
                    "name": "Название упражнения",
                    "description": "Как выполнять (1-2 предложения)",
                    "equipment": "bodyweight/dumbbells/barbell/resistance_band/none",
                    "muscle_group": "{muscle_group}",
                    "sets": 3,
                    "reps": 10,
                    "weight": 0,
                    "intensity": "low/medium/high"
                }}
            ]
        }}

        ВАЖНО: Верни ТОЛЬКО JSON без дополнительного текста. Обязательно заполни description для каждого упражнения!
        """

        print(f"🔧 Sending request to AI API...")

        try:
            response = await self._make_ai_request(prompt)
            print(f"🔧 AI API response: {response}")

            # Извлекаем JSON из ответа (убираем markdown блоки если есть)
            json_str = self._extract_json_from_response(response)
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

        return await self._make_ai_request(prompt)


ai_service = AIService()