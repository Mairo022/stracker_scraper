from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = ""
SESSIONS_URL = f"{BASE_URL}/sessionstat"


def main():
    options = webdriver.ChromeOptions()
    options.binary_location = '/usr/bin/brave-browser'
    options.page_load_strategy = 'eager'

    browser = webdriver.Chrome(options=options)
    handleSessions(browser)
    print("Program has finished")


def handleSessions(browser):
    browser.get(SESSIONS_URL)

    for page_current in range(0, 50):
        sessionsPage(browser)
        browser.get(SESSIONS_URL + '?page=' + str(page_current + 1))

        pagination = (WebDriverWait(browser, 10)
                      .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".pagination > li"))))

        page_last = int(pagination[-3].text)

        if page_current + 1 == page_last:
            break


def sessionsPage(browser):
    sessions = (WebDriverWait(browser, 10)
                .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tbody > tr'))))

    sessions_links = [session.get_attribute("href") for session in sessions]

    for session_link in sessions_links:
        sessionPage(browser, f"{BASE_URL}/{session_link}")
        sleep(1)

    browser.execute_script("window.history.go(-1)")


def sessionPage(browser, url):
    browser.get(url)
    extractAndWriteSessionData(browser)
    sleep(1)
    browser.execute_script("window.history.go(-1)")


def extractAndWriteSessionData(browser):
    tables = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tbody")))
    session_overview = tables[0].find_elements(By.TAG_NAME, "td")
    session_details = tables[1].find_elements(By.TAG_NAME, "tr")

    track = session_overview[0].text
    session = session_overview[1].text
    duration = session_overview[2].text
    datetime = session_overview[3].text

    for row in session_details:
        items = row.find_elements(By.TAG_NAME, "td")
        position = items[0].text
        driver = items[1].text
        car = items[2].text
        fastest_lap = items[3].text
        gap_to_first = items[4].text
        laps = items[5].text
        cuts = items[6].text
        crashes = items[7].text

    # TODO: Save data


main()
