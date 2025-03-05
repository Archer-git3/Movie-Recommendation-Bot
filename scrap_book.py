import json
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# Setup WebDriver for Microsoft Edge
options = webdriver.EdgeOptions()
# options.add_argument("--headless")
options.page_load_strategy = 'normal'
driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)

def load_existing_books(filename):
    """Load existing book data from a JSON file if it exists."""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Error reading JSON file.")
                return []
    return []

def scroll_down(driver, times=3):
    """Function to scroll down the page to load more recommendations."""
    for _ in range(times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # Scroll to the bottom
        time.sleep(2)

# Function to collect detailed book information, including genres and recommendations
def get_book_info(book_url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(book_url)
            time.sleep(3)  # Wait for the page to load
            scroll_down(driver, times=3)  # Adjust times as necessary to load more items

            # Get genres
            try:
                genre_elements = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="genresList"] .BookPageMetadataSection__genreButton')
                genres = [genre.find_element(By.CSS_SELECTOR, '.Button__labelItem').text for genre in genre_elements if genre.text]  # Collect non-empty genres
            except NoSuchElementException:
                genres = ["No genres found"]

            # Get the publication year
            try:
                publication_info = driver.find_element(By.CSS_SELECTOR, 'p[data-testid="publicationInfo"]').text
                year = publication_info.split("First published")[-1].strip()  # Extract the year
            except NoSuchElementException:
                year = "Year not available"

            # Get Readers also enjoyed (Recommendations)
            try:
                recommendations_section = driver.find_element(By.CSS_SELECTOR, 'div.Carousel__itemsArea')
                if recommendations_section:
                    recommendations_elements = recommendations_section.find_elements(By.CSS_SELECTOR, 'li.CarouselGroup__item')

                    readers_also_enjoyed = []
                    for rec in recommendations_elements[:4]:
                        title = rec.find_element(By.CSS_SELECTOR, '.BookCard__title').text
                        author = rec.find_element(By.CSS_SELECTOR, '.BookCard__authorName').text
                        url = rec.find_element(By.CSS_SELECTOR, '.BookCard__clickCardTarget').get_attribute('href')
                        readers_also_enjoyed.append({
                            "title": title,
                            "author": author,
                            "url": url
                        })

                    if not readers_also_enjoyed:
                        readers_also_enjoyed = ["No recommendations available"]

            except NoSuchElementException:
                readers_also_enjoyed = ["No recommendations section available"]

            # Get book description
            try:
                description = driver.find_element(By.CSS_SELECTOR, 'span.Formatted').text.strip()
            except NoSuchElementException:
                description = "No description available"

            return {
                "description": description,
                "genres": genres,
                "year": year,
                "readers_also_enjoyed": readers_also_enjoyed,
                "url": book_url
            }

        except NoSuchElementException:
            print(f"Details not found on page: {book_url}")
            return None
        except Exception as e:
            print(f"Error fetching book data from {book_url} (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                print("Retrying page load...")
                time.sleep(5)
                continue
            return None


def collect_book_data_from_main_page(url, existing_books):
    driver.get(url)
    time.sleep(3)
    i=0
    books_data = []
    existing_titles = {book['title'] for book in existing_books}

    while True:
        try:
            book_elements = driver.find_elements(By.CSS_SELECTOR, 'tr[itemtype="http://schema.org/Book"]')
            if not book_elements:
                print("No book elements found on the page.")
                break

            print(f"Found {len(book_elements)} books on the page")

            for index, book_element in enumerate(book_elements):
                try:
                    title_element = book_element.find_element(By.CSS_SELECTOR, '.bookTitle span')
                    title = title_element.text if title_element else None

                    if title is None or title in existing_titles:
                        print(f"Skipping already collected or missing title for book at index {index}: {title}")
                        continue

                    book_url = book_element.find_element(By.CSS_SELECTOR, '.bookTitle').get_attribute('href')
                    author_element = book_element.find_element(By.CSS_SELECTOR, '.authorName span')
                    author = author_element.text if author_element else "Author not available"

                    try:
                        rating = book_element.find_element(By.CSS_SELECTOR, '.minirating').text
                    except NoSuchElementException:
                        rating = "Rating not available"

                    print(f"Collecting info for: {title}")

                    # Open book details in new tab
                    ActionChains(driver).key_down(Keys.CONTROL).click(book_element.find_element(By.CSS_SELECTOR, '.bookTitle')).key_up(Keys.CONTROL).perform()
                    driver.switch_to.window(driver.window_handles[1])  # Switch to new tab

                    # Get detailed info
                    detailed_info = get_book_info(driver.current_url)

                    # Close the details tab and switch back
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    i=0
                    if detailed_info:
                        books_data.append({
                            "title": title,
                            "author": author,
                            "url": book_url,
                            "rating": rating,
                            "year": detailed_info.get("year"),
                            "genres": detailed_info.get("genres"),
                            "readers_also_enjoyed": detailed_info.get("readers_also_enjoyed"),
                            "description": detailed_info.get("description")
                        })

                except StaleElementReferenceException:
                    print(f"Stale element, refreshing at index {index}.")
                    break  # Break to refresh if elements are stale

            # Check for next page
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, '.next_page')
                if next_button.is_enabled():
                    next_url = next_button.get_attribute('href')
                    print(f"Moving to next page: {next_url}")
                    driver.get(next_url)
                    time.sleep(3)
                else:
                    break
            except NoSuchElementException:
                print("Next page button not found.")
                break

        except Exception as e:
            print(f"Error collecting book data from page: {e}")
            i+=1
            if i ==3 :
                break
            

    return books_data



# Main function to collect books
def collect_books():
    base_url = "https://www.goodreads.com/list/show/6.Best_Books_of_the_20th_Century?page=77"
    filename = 'books.json'

    # Load existing books
    existing_books = load_existing_books(filename)
    books_data = collect_book_data_from_main_page(base_url, existing_books)

    # Merge new books with existing ones
    all_books = existing_books + books_data

    # Save all data to a JSON file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_books, f, ensure_ascii=False, indent=4)

    return all_books

# Collect the books
books = collect_books()

# Close the browser
driver.quit()

print(f"Collected {len(books)} books!")
