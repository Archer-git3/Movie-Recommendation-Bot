import json
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

# Налаштування веб-драйвера для Microsoft Edge
options = webdriver.EdgeOptions()
options.add_argument("--headless")
options.page_load_strategy = 'normal'  # Налаштування стратегії завантаження сторінки
#options.add_argument('--disable-dev-shm-usage')  # Уникає проблеми з пам'яттю
#options.add_argument('--no-sandbox')  # Запускає браузер без пісочниці
driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)



def load_existing_movies(filename):
    """Завантажуємо існуючі дані з файлу, якщо файл існує."""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Помилка при читанні JSON файлу.")
                return []
    return []


# Функція для отримання інформації про фільм з окремої сторінки з повторною спробою
def get_movie_info(movie_url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(movie_url)
            time.sleep(1)  # Затримка для повного завантаження сторінки
            genre_container = driver.find_element(By.CSS_SELECTOR, '.movie__genres__container')
            genres = [genre.text for genre in
                      genre_container.find_elements(By.CSS_SELECTOR, '.selection__badge--border.selection__badge--fill') if
                      genre.tag_name == 'a']

            # Збираємо країни
            countries = []
            try:
                country_container = driver.find_element(By.CSS_SELECTOR, '.movie-data-item--country .value')
                country_elements = country_container.find_elements(By.CSS_SELECTOR, 'a')
                countries = [country.text for country in country_elements if country.tag_name == 'a']
                if not countries:
                    countries.append("Країна не вказана")
            except NoSuchElementException:
                countries.append("Країна не вказана")

            # Отримуємо рік
            try:
                year = driver.find_element(By.CSS_SELECTOR, '.movie-data-item--date .value a').text
            except NoSuchElementException:
                year = "Рік не вказано"

            # Отримуємо теги
            tags = []
            try:
                tag_container = driver.find_element(By.CSS_SELECTOR, '.movie__tags__container')
                tags = [tag.text for tag in tag_container.find_elements(By.CSS_SELECTOR, '.selection__badge--fill') if
                        tag.tag_name == 'a']
            except NoSuchElementException:
                tags = ["Теги відсутні"]

            # Опис
            description = driver.find_element(By.CSS_SELECTOR, '.text').text
            description = description.replace("<br>", "\n").strip()

            return {
                "description": description,
                "genres": genres,
                "tags": tags,
                "country": countries,
                "year": year,
                "url": movie_url
            }

        except NoSuchElementException:
            print(f"Опис фільму не знайдено на сторінці: {movie_url}")
            return None

        except Exception as e:
            print(f"Error collecting movie data from {movie_url} (спроба {attempt+1}): {e}")
            if attempt < retries - 1:
                print("Спроба перезавантаження сторінки...")
                time.sleep(5)  # Затримка перед повторною спробою
                continue  # Спробувати ще раз
            return None



def collect_movie_data_from_main_page(url, existing_movies):
    driver.get(url)
    time.sleep(1)  # Затримка для завантаження сторінки

    movies_data = []
    existing_titles = {movie['title'] for movie in existing_movies}  # Вже зібрані фільми

    while True:
        try:
            # Знаходимо всі елементи з класом "item", що містять фільми
            movie_elements = driver.find_elements(By.CSS_SELECTOR, '.col > .item')
            visible_movies = [movie for movie in movie_elements if movie.is_displayed()]

            print(f"Знайдено {len(visible_movies)} видимих фільмів")
            for index in range(len(movie_elements)):
                try:
                    movie_element = movie_elements[index]
                    try:
                        movie_element.find_element(By.CSS_SELECTOR, '.img-wrap img')  # Перевірка на постер
                    except NoSuchElementException:
                        print(f"Елемент без постера пропущено")
                        continue

                    title = movie_element.find_element(By.CSS_SELECTOR, 'a[title]').get_attribute('title')

                    # Пропускаємо фільми, які вже зібрані
                    if title in existing_titles:
                        print(f"Пропускаємо вже зібраний фільм: {title}")
                        continue

                    movie_url = movie_element.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')

                    # Отримуємо рейтинг
                    try:
                        rating = movie_element.find_element(By.CSS_SELECTOR, '.movie-mark').text
                    except NoSuchElementException:
                        rating = "Рейтинг відсутній"

                    print(f"Збираємо інформацію для: {title}")
                    detailed_info = get_movie_info(movie_url)

                    if detailed_info:
                        movies_data.append({
                            "type": "anime",
                            "title": title,
                            "url": movie_url,
                            "year": detailed_info.get("year"),
                            "country": detailed_info.get("country"),
                            "genres": detailed_info.get("genres"),
                            "tags": detailed_info.get("tags"),
                            "rating": rating,
                            "description": detailed_info.get("description")
                        })

                    # Повертаємося на головну сторінку після збирання інформації про фільм
                    driver.get(url)
                    time.sleep(1)
                    movie_elements = driver.find_elements(By.CSS_SELECTOR, '.col .item')

                except StaleElementReferenceException:
                    print(f"Застарілий елемент, оновлюємо сторінку і продовжуємо з елемента {index}")
                    driver.refresh()
                    time.sleep(2)
                    movie_elements = driver.find_elements(By.CSS_SELECTOR, '.col .item')

            # Переходимо на наступну сторінку
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, '.pagination .next a')
                next_url = next_button.get_attribute('href')
                if next_url:
                    print(f"Перехід на наступну сторінку: {next_url}")
                    driver.get(next_url)
                    time.sleep(1)
                    url = next_url
                else:
                    break  # Вихід з циклу, якщо немає кнопки для переходу
            except NoSuchElementException:
                print("Кнопка для переходу на наступну сторінку не знайдена.")
                break

        except Exception as e:
            print(f"Error collecting movie data from page: {e}")
            break

    return movies_data


# Основна логіка для збору даних
def collect_movies():
    base_url = "https://uaserial.tv/anime"
    filename = 'movies.json'

    # Завантажуємо існуючі фільми
    existing_movies = load_existing_movies(filename)
    movies_data = collect_movie_data_from_main_page(base_url, existing_movies)

    # Об'єднуємо нові фільми з тими, що вже є
    all_movies = existing_movies + movies_data

    # Зберігаємо об'єднані дані у JSON файл
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=4)

    return all_movies


# Збираємо дані
movies = collect_movies()

# Закриваємо браузер
driver.quit()

print(f"Зібрано {len(movies)} фільмів!")
