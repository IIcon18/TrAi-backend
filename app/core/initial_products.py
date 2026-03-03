"""
Начальная база популярных продуктов для расчета БЖУ.
Данные на 100 грамм продукта.
Источники: USDA, российские таблицы состава продуктов
"""

INITIAL_PRODUCTS = [
    # Крупы и злаки (вареные)
    {
        "name": "Гречка вареная",
        "name_variants": ["гречневая каша", "гречка", "гречневая крупа вареная"],
        "calories_per_100g": 110,
        "protein_per_100g": 4.2,
        "fat_per_100g": 1.1,
        "carbs_per_100g": 21.3,
        "category": "крупы",
        "verified": True
    },
    {
        "name": "Рис белый вареный",
        "name_variants": ["рис", "белый рис", "рисовая каша", "отварной рис"],
        "calories_per_100g": 130,
        "protein_per_100g": 2.7,
        "fat_per_100g": 0.3,
        "carbs_per_100g": 28.2,
        "category": "крупы",
        "verified": True
    },
    {
        "name": "Овсянка вареная",
        "name_variants": ["овсяная каша", "овсянка", "геркулес", "овсяные хлопья вареные"],
        "calories_per_100g": 88,
        "protein_per_100g": 3.0,
        "fat_per_100g": 1.7,
        "carbs_per_100g": 15.0,
        "category": "крупы",
        "verified": True
    },
    {
        "name": "Макароны вареные",
        "name_variants": ["паста", "спагетти", "макароны", "лапша"],
        "calories_per_100g": 158,
        "protein_per_100g": 5.8,
        "fat_per_100g": 0.9,
        "carbs_per_100g": 31.0,
        "category": "крупы",
        "verified": True
    },

    # Мясо и птица
    {
        "name": "Куриная грудка",
        "name_variants": ["курица", "куриное филе", "грудка куриная", "куриная грудка вареная"],
        "calories_per_100g": 165,
        "protein_per_100g": 31.0,
        "fat_per_100g": 3.6,
        "carbs_per_100g": 0.0,
        "category": "мясо",
        "verified": True
    },
    {
        "name": "Говядина",
        "name_variants": ["говядина вареная", "телятина", "говяжье мясо"],
        "calories_per_100g": 250,
        "protein_per_100g": 26.0,
        "fat_per_100g": 16.0,
        "carbs_per_100g": 0.0,
        "category": "мясо",
        "verified": True
    },
    {
        "name": "Свинина",
        "name_variants": ["свиное мясо", "свинина вареная"],
        "calories_per_100g": 242,
        "protein_per_100g": 16.0,
        "fat_per_100g": 21.0,
        "carbs_per_100g": 0.0,
        "category": "мясо",
        "verified": True
    },
    {
        "name": "Индейка",
        "name_variants": ["индейка филе", "мясо индейки", "индюшатина"],
        "calories_per_100g": 157,
        "protein_per_100g": 29.0,
        "fat_per_100g": 4.0,
        "carbs_per_100g": 0.0,
        "category": "мясо",
        "verified": True
    },

    # Рыба
    {
        "name": "Лосось",
        "name_variants": ["семга", "красная рыба", "лосось запеченный"],
        "calories_per_100g": 208,
        "protein_per_100g": 20.0,
        "fat_per_100g": 13.0,
        "carbs_per_100g": 0.0,
        "category": "рыба",
        "verified": True
    },
    {
        "name": "Тунец",
        "name_variants": ["тунец консервированный", "тунец в собственном соку"],
        "calories_per_100g": 132,
        "protein_per_100g": 29.0,
        "fat_per_100g": 1.3,
        "carbs_per_100g": 0.0,
        "category": "рыба",
        "verified": True
    },
    {
        "name": "Треска",
        "name_variants": ["филе трески", "треска вареная"],
        "calories_per_100g": 82,
        "protein_per_100g": 18.0,
        "fat_per_100g": 0.7,
        "carbs_per_100g": 0.0,
        "category": "рыба",
        "verified": True
    },

    # Молочные продукты
    {
        "name": "Творог 5%",
        "name_variants": ["творог", "творог обезжиренный", "творог 5 процентов"],
        "calories_per_100g": 121,
        "protein_per_100g": 16.0,
        "fat_per_100g": 5.0,
        "carbs_per_100g": 1.8,
        "category": "молочное",
        "verified": True
    },
    {
        "name": "Молоко 2.5%",
        "name_variants": ["молоко", "коровье молоко"],
        "calories_per_100g": 52,
        "protein_per_100g": 2.8,
        "fat_per_100g": 2.5,
        "carbs_per_100g": 4.7,
        "category": "молочное",
        "verified": True
    },
    {
        "name": "Йогурт натуральный",
        "name_variants": ["греческий йогурт", "йогурт", "йогурт без добавок"],
        "calories_per_100g": 59,
        "protein_per_100g": 10.0,
        "fat_per_100g": 0.4,
        "carbs_per_100g": 3.6,
        "category": "молочное",
        "verified": True
    },
    {
        "name": "Кефир 2.5%",
        "name_variants": ["кефир"],
        "calories_per_100g": 51,
        "protein_per_100g": 2.9,
        "fat_per_100g": 2.5,
        "carbs_per_100g": 4.0,
        "category": "молочное",
        "verified": True
    },
    {
        "name": "Сыр российский",
        "name_variants": ["сыр", "твердый сыр", "российский сыр"],
        "calories_per_100g": 363,
        "protein_per_100g": 23.0,
        "fat_per_100g": 30.0,
        "carbs_per_100g": 0.0,
        "category": "молочное",
        "verified": True
    },

    # Яйца
    {
        "name": "Яйцо куриное",
        "name_variants": ["яйцо", "куриное яйцо", "яйца"],
        "calories_per_100g": 157,
        "protein_per_100g": 12.7,
        "fat_per_100g": 11.5,
        "carbs_per_100g": 0.7,
        "category": "яйца",
        "verified": True
    },

    # Овощи
    {
        "name": "Картофель вареный",
        "name_variants": ["картошка", "картофель", "отварной картофель"],
        "calories_per_100g": 86,
        "protein_per_100g": 2.0,
        "fat_per_100g": 0.1,
        "carbs_per_100g": 20.0,
        "category": "овощи",
        "verified": True
    },
    {
        "name": "Брокколи",
        "name_variants": ["брокколи вареная", "капуста брокколи"],
        "calories_per_100g": 35,
        "protein_per_100g": 2.8,
        "fat_per_100g": 0.4,
        "carbs_per_100g": 7.0,
        "category": "овощи",
        "verified": True
    },
    {
        "name": "Помидор",
        "name_variants": ["томат", "помидоры", "томаты"],
        "calories_per_100g": 18,
        "protein_per_100g": 0.9,
        "fat_per_100g": 0.2,
        "carbs_per_100g": 3.9,
        "category": "овощи",
        "verified": True
    },
    {
        "name": "Огурец",
        "name_variants": ["огурцы", "свежий огурец"],
        "calories_per_100g": 15,
        "protein_per_100g": 0.8,
        "fat_per_100g": 0.1,
        "carbs_per_100g": 3.6,
        "category": "овощи",
        "verified": True
    },
    {
        "name": "Морковь",
        "name_variants": ["морковка"],
        "calories_per_100g": 41,
        "protein_per_100g": 0.9,
        "fat_per_100g": 0.2,
        "carbs_per_100g": 9.6,
        "category": "овощи",
        "verified": True
    },
    {
        "name": "Капуста белокочанная",
        "name_variants": ["капуста", "свежая капуста"],
        "calories_per_100g": 25,
        "protein_per_100g": 1.8,
        "fat_per_100g": 0.1,
        "carbs_per_100g": 5.8,
        "category": "овощи",
        "verified": True
    },
    {
        "name": "Перец болгарский",
        "name_variants": ["сладкий перец", "болгарский перец", "перец"],
        "calories_per_100g": 27,
        "protein_per_100g": 1.3,
        "fat_per_100g": 0.1,
        "carbs_per_100g": 5.3,
        "category": "овощи",
        "verified": True
    },

    # Фрукты
    {
        "name": "Банан",
        "name_variants": ["бананы"],
        "calories_per_100g": 89,
        "protein_per_100g": 1.1,
        "fat_per_100g": 0.3,
        "carbs_per_100g": 23.0,
        "category": "фрукты",
        "verified": True
    },
    {
        "name": "Яблоко",
        "name_variants": ["яблоки"],
        "calories_per_100g": 52,
        "protein_per_100g": 0.3,
        "fat_per_100g": 0.2,
        "carbs_per_100g": 14.0,
        "category": "фрукты",
        "verified": True
    },
    {
        "name": "Апельсин",
        "name_variants": ["апельсины"],
        "calories_per_100g": 47,
        "protein_per_100g": 0.9,
        "fat_per_100g": 0.1,
        "carbs_per_100g": 12.0,
        "category": "фрукты",
        "verified": True
    },

    # Орехи и семена
    {
        "name": "Миндаль",
        "name_variants": ["орех миндаль", "миндальные орехи"],
        "calories_per_100g": 579,
        "protein_per_100g": 21.0,
        "fat_per_100g": 50.0,
        "carbs_per_100g": 22.0,
        "category": "орехи",
        "verified": True
    },
    {
        "name": "Грецкий орех",
        "name_variants": ["грецкие орехи", "орех грецкий"],
        "calories_per_100g": 654,
        "protein_per_100g": 15.0,
        "fat_per_100g": 65.0,
        "carbs_per_100g": 14.0,
        "category": "орехи",
        "verified": True
    },

    # Хлеб и выпечка
    {
        "name": "Хлеб белый",
        "name_variants": ["белый хлеб", "пшеничный хлеб"],
        "calories_per_100g": 266,
        "protein_per_100g": 8.1,
        "fat_per_100g": 3.2,
        "carbs_per_100g": 50.0,
        "category": "хлеб",
        "verified": True
    },
    {
        "name": "Хлеб цельнозерновой",
        "name_variants": ["черный хлеб", "ржаной хлеб", "цельнозерновой"],
        "calories_per_100g": 247,
        "protein_per_100g": 9.0,
        "fat_per_100g": 3.3,
        "carbs_per_100g": 45.0,
        "category": "хлеб",
        "verified": True
    },

    # Бобовые
    {
        "name": "Фасоль вареная",
        "name_variants": ["фасоль", "красная фасоль", "белая фасоль вареная"],
        "calories_per_100g": 123,
        "protein_per_100g": 8.7,
        "fat_per_100g": 0.5,
        "carbs_per_100g": 22.0,
        "category": "бобовые",
        "verified": True
    },
    {
        "name": "Нут вареный",
        "name_variants": ["нут", "турецкий горох"],
        "calories_per_100g": 164,
        "protein_per_100g": 8.9,
        "fat_per_100g": 2.6,
        "carbs_per_100g": 27.4,
        "category": "бобовые",
        "verified": True
    },
    {
        "name": "Чечевица вареная",
        "name_variants": ["чечевица"],
        "calories_per_100g": 116,
        "protein_per_100g": 9.0,
        "fat_per_100g": 0.4,
        "carbs_per_100g": 20.0,
        "category": "бобовые",
        "verified": True
    },

    # Масла
    {
        "name": "Оливковое масло",
        "name_variants": ["масло оливковое", "оливковое масло extra virgin"],
        "calories_per_100g": 884,
        "protein_per_100g": 0.0,
        "fat_per_100g": 100.0,
        "carbs_per_100g": 0.0,
        "category": "масла",
        "verified": True
    },
    {
        "name": "Подсолнечное масло",
        "name_variants": ["масло подсолнечное", "растительное масло"],
        "calories_per_100g": 884,
        "protein_per_100g": 0.0,
        "fat_per_100g": 100.0,
        "carbs_per_100g": 0.0,
        "category": "масла",
        "verified": True
    },
]
