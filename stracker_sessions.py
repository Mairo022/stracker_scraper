import os
import uuid
import psycopg2
from time import sleep
from psycopg2 import extras
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = ""
SESSIONS_URL = f"{BASE_URL}/sessionstat"

load_dotenv()

def main():
    options = webdriver.ChromeOptions()
    options.binary_location = '/usr/bin/brave-browser'
    options.page_load_strategy = 'eager'

    browser = webdriver.Chrome(options=options)

    handleSessions(browser)
    print("Program has finished")


def db():
    connection = psycopg2.connect(
        host=os.environ.get('PG_HOST'),
        port=os.environ.get('PG_PORT'),
        user=os.environ.get('PG_USER'),
        password=os.environ.get('PG_PASSWORD'),
        dbname=os.environ.get('PG_DATABASE'),
    )
    cursor = connection.cursor()
    psycopg2.extras.register_uuid()

    return connection, cursor


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


# /sessionstat
def sessionsPage(browser):
    sessions = (WebDriverWait(browser, 10)
                .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tbody > tr'))))

    sessions_links = [session.get_attribute("href") for session in sessions]

    for session_link in sessions_links:
        sessionPage(browser, f"{BASE_URL}/{session_link}")
        sleep(1)

    browser.execute_script("window.history.go(-1)")


def sessionPage(browser, url):
    # Leads to /sessiondetails?sessionid
    browser.get(url)

    session_id = uuid.uuid4()
    # extractAndWriteSessionDetailsData(browser, session_id)
    # extractAndWriteLapsData
    extractAndWriteSessionInfo(browser, url, session_id)

    sleep(1)
    browser.execute_script("window.history.go(-1)")


# /sessiondetails?sessionid=
def extractAndWriteSessionInfo(browser, url, session_id):
    connection, cursor = db()

    try:
        session_dict = {}
        session_info_keys = [
            "Track",
            "Session",
            "Duration",
            "Date and time",
            "Penalties",
            "Tyre wear factor",
            "Fuel rate",
            "Mechanical damage",
            "Ambient temperature",
            "Track temperature",
            "Server name"
        ]

        tables = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tbody")))
        session_overview = tables[0].find_elements(By.TAG_NAME, "tr")
        session_details_row = tables[1].find_element(By.TAG_NAME, "tr")

        session_overview_headers = session_overview[0].find_elements(By.TAG_NAME, "th")
        session_overview_data = session_overview[1].find_elements(By.TAG_NAME, "td")

        for i in range(0, 5):
            key = session_overview_headers[i].text
            value = session_overview_data[i].text

            if key in session_info_keys:
                session_dict[key] = value

        # Leads to /sessiondetails?playerInSessionId=
        session_details_row.click()
        lap_row = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".clickableRow")))
        # Leads to /lapdetails?lapid=
        lap_row.click()

        session_info = (WebDriverWait(browser, 10)
                        .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".col-md-3:nth-of-type(3) table tr"))))

        for row in session_info:
            key, value = row.find_elements(By.TAG_NAME, "td")

            if key.text in session_info_keys:
                session_dict[key.text] = value.text

        # Adjust session value types
        num_keys_to_adjust = ["Tyre wear factor", "Fuel rate", "Mechanical damage", "Ambient temperature", "Track temperature"]
        for key in num_keys_to_adjust:
            try:
                session_dict[key] = session_dict.get(key).split(" ")[0]
            except KeyError:
                session_dict[key] = 0

        session_dict["Penalties"] = True if session_dict.get("Penalties") == "yes" else False
        session_dict["Date and time"] = datetime.strptime(session_dict.get("Date and time"), "%Y-%m-%d %H:%M")

        cursor.execute(
            "INSERT INTO sessions "
            "(id, type, date, fuel_rate, tyre_wear_rate, air_temp, road_temp, track, penalties, damage, duration, server) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",(
                session_id,
                session_dict.get("Session"),
                session_dict.get("Date and time"),
                float(session_dict.get("Fuel rate")),
                float(session_dict.get("Tyre wear factor")),
                int(session_dict.get("Ambient temperature")),
                int(session_dict.get("Track temperature")),
                session_dict.get("Track"),
                session_dict.get("Penalties"),
                int(session_dict.get("Mechanical damage")),
                session_dict.get("Duration"),
                session_dict.get("Server name")
            ))

        connection.commit()

    finally:
        connection.close()
        cursor.close()
        browser.get(url)


# /sessiondetails?sessionid=
def extractAndWriteSessionDetailsData(browser, session_id):
    connection, cursor = db()

    try:
        tables = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tbody")))
        session_overview = tables[0].find_elements(By.TAG_NAME, "td")
        session_details = tables[1].find_elements(By.TAG_NAME, "tr")

        session = session_overview[1].text

        # Session details part
        if session == "Qualify":
            for row in session_details:
                items = row.find_elements(By.TAG_NAME, "td")
                position = items[0].text
                driver = items[1].text
                car = items[2].text
                fastest_lap = items[3].text
                gap_to_first = items[4].text

                cursor.execute("INSERT INTO laps "
                               "(session_id, position, driver, car, fastest_lap, gap_to_first)"
                               "VALUES (%s, %s, %s, %s, %s, %s)",
                               (session_id, position, driver, car, fastest_lap, gap_to_first))

        if session == "Race":
            for row in session_details:
                items = row.find_elements(By.TAG_NAME, "td")
                position = items[0].text
                driver = items[1].text
                car = items[2].text
                total_time = items[3].text
                gap_to_first = items[4].text
                fastest_lap = items[5].text

                cursor.execute("INSERT INTO laps "
                               "(session_id, position, driver, car, fastest_lap, gap_to_first, total_time)"
                               "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                               (session_id, position, driver, car, fastest_lap, gap_to_first, total_time))

        connection.commit()

    finally:
        connection.close()
        cursor.close()


main()
