import os
import uuid
import random
import psycopg2
from time import sleep
from psycopg2 import extras
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = ""
SESSIONS_URL = f"{BASE_URL}/sessionstat"

SLEEP_MIN = 0.5
SLEEP_MAX = 5

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
    connection, cursor = db()

    try:
        browser.get(SESSIONS_URL)

        for page_current in range(0, 50):
            sessionsPage(browser, connection, cursor)

            browser.get(SESSIONS_URL + '?page=' + str(page_current + 1))

            pagination = (WebDriverWait(browser, 10)
                          .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".pagination > li"))))

            page_last = int(pagination[-3].text)

            if page_current + 1 == page_last:
                break

    except Exception as e:
        print(e)

    finally:
        cursor.close()
        connection.close()


# /sessionstat
def sessionsPage(browser, connection, cursor):
    try:
        sessions = (WebDriverWait(browser, 10)
                    .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tbody > tr'))))

        sessions_links = [session.get_attribute("href") for session in sessions]

        for session_link in sessions_links:
            sessionPage(browser, f"{BASE_URL}/{session_link}", cursor)
            sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
            connection.commit()

    except psycopg2.Error as e:
        print(e)
        connection.rollback()

    finally:
        browser.execute_script("window.history.go(-1)")


def sessionPage(browser, url, cursor):
    # Leads to /sessiondetails?sessionid
    browser.get(url)
    session_id = uuid.uuid4()

    extractAndWriteSessionInfo(browser, url, session_id, cursor)
    extractAndWriteSessionDetailsData(browser, session_id, cursor)
    extractAndWriteLapsData(browser, url, session_id, cursor)

    sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
    browser.execute_script("window.history.go(-1)")


# /sessiondetails?sessionid=
def extractAndWriteSessionInfo(browser, url, session_id, cursor):
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

        # Example values (session_dict)
        # {'Track': 'Barcelona - GP', 'Session': 'Qualify', 'Duration': '00:08',
        # 'Date and time': datetime.datetime( 2024, 1, 12, 12, 15), 'Penalties': True,
        # 'Tyre wear factor': '1.0', 'Fuel rate': '1.0', 'Mechanical
        # damage': '60', 'Ambient temperature': '22', 'Track temperature': '29',
        # 'Server name': 'server00'}

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

    finally:
        browser.get(url)


# /sessiondetails?sessionid=
def extractAndWriteSessionDetailsData(browser, session_id, cursor):
    tables = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tbody")))
    session_overview = tables[0].find_elements(By.TAG_NAME, "td")
    session_details = tables[1].find_elements(By.TAG_NAME, "tr")

    session = session_overview[1].text

    if session == "Qualify":
        for row in session_details:
            items = row.find_elements(By.TAG_NAME, "td")
            position = int(items[0].text) if items[0].text is not "DNF" else None
            driver = items[1].text
            car = getCar(items[2])
            fastest_lap = items[3].text
            gap_to_first = items[4].text

            cursor.execute("INSERT INTO sessions_details "
                           "(session_id, rank, driver, car, fastest_lap, gap_to_first)"
                           "VALUES (%s, %s, %s, %s, %s, %s)",
                           (session_id, position, driver, car, fastest_lap, gap_to_first))

    if session == "Race":
        for row in session_details:
            items = row.find_elements(By.TAG_NAME, "td")
            position = int(items[0].text) if items[0].text is not "DNF" else None
            driver = items[1].text
            car = getCar(items[2])
            total_time = items[3].text if items[3].text != "--.--.---" else None
            gap_to_first = items[4].text
            fastest_lap = items[5].text

            # Example values
            # session_id: 0e820083-9999-41b0-bb8d-cb0d5deff29b, rank: 1,
            # driver: Lucas, car: Mazda MX5 Cup, gap_to_first: +02.800,
            # fastest_lap: 02:10.987, total_time: 11:20:44

            cursor.execute("INSERT INTO sessions_details "
                           "(session_id, rank, driver, car, fastest_lap, gap_to_first, total_time)"
                           "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (session_id, position, driver, car, fastest_lap, gap_to_first, total_time))


# /sessiondetails?sessionid=
def extractAndWriteLapsData(browser, url, session_id, cursor):
    try:
        lap_keys = [
            "Name",
            "Track",
            "Car",
            "Lap time",
            "Achieved on",
            "Valid",
            "Cuts",
            "Maximum Speed",
            "Pit Lane Time",
            "Pit Time",
            "Tyres used",
            "Grip level",
            "Car collisions",
            "Env collisions",
            "Sector 1",
            "Sector 2",
            "Sector 3"
        ]

        tables = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tbody")))
        session_details = tables[1].find_elements(By.TAG_NAME, "tr")

        driver_links = [driver.get_attribute("href") for driver in session_details]

        for driver_link in driver_links:
            # Leads to /sessiondetails?playerInSessionId=
            browser.get(f"{BASE_URL}/{driver_link}")
            sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

            laps = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tbody > tr")))

            laps_links = [lap.get_attribute("href") for lap in laps]

            for session_link in laps_links:
                lap_dict = {}
                # Leads to /lapdetails?lapid=
                browser.get(f"{BASE_URL}/{session_link}")
                sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

                lap_info = (WebDriverWait(browser, 10)
                            .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".col-md-3:nth-of-type(2) table tr"))))

                driver_info = (WebDriverWait(browser, 10)
                               .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".col-md-3:nth-of-type(1) table tr"))))

                # Driver information table
                for row in driver_info:
                    key, value = row.find_elements(By.TAG_NAME, "td")

                    if key.text == "Car":
                        car = getCar(row)
                        lap_dict["Car"] = car
                        break

                    if key.text in lap_keys:
                        lap_dict[key.text] = value.text

                # Lap information table
                for row in lap_info:
                    key, value = row.find_elements(By.TAG_NAME, "td")

                    if key.text in lap_keys:
                        lap_dict[key.text] = value.text

                # Adjust lap values
                num_keys_to_adjust = ["Maximum Speed", "Grip level", "Sector 1", "Sector 2", "Sector 3"]
                for key in num_keys_to_adjust:
                    try:
                        value = lap_dict.get(key)
                        lap_dict[key] = value.split(" ")[0] if value is not None else 0
                    except KeyError:
                        lap_dict[key] = 0

                lap_dict["Valid"] = True if lap_dict.get("Valid") == "yes" else False
                lap_dict["Date and time"] = datetime.strptime(lap_dict.get("Achieved on"), "%Y-%m-%d %H:%M")

                # Example values (lap_dict)
                # {'Name': 'Lucas', 'Track': 'Barcelona - GP', 'Car': 'Mazda MX5 Cup', 'Lap time': '02:23.866',
                # 'Achieved on': '2024-01-12 12:18', 'Valid': False, 'Cuts': '2', 'Maximum Speed': '170',
                # 'Pit Lane Time': '-', 'Pit Time': '-', 'Tyres used': 'unknown', 'Grip level': '100.0',
                # 'Car collisions': '0', 'Env collisions': '0', 'Sector 1': 0, 'Sector 2': 0, 'Sector 3': 0,
                # 'Date and time': datetime.datetime(2024, 1, 12, 12, 18)}

                cursor.execute(
                    "INSERT INTO laps "
                    "("
                    "session_id, driver, car, track, laptime, s1, s2, s3, valid, cuts, crashes_env, "
                    "crashes_cars, pit_time, pitlane_time, grip, maximum_speed, date"
                    ")"
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (
                        session_id,
                        lap_dict.get("Name"),
                        lap_dict.get("Car"),
                        lap_dict.get("Track"),
                        lap_dict.get("Lap time"),
                        lap_dict.get("Sector 1"),
                        lap_dict.get("Sector 2"),
                        lap_dict.get("Sector 3"),
                        lap_dict.get("Valid"),
                        int(lap_dict.get("Cuts")),
                        int(lap_dict.get("Env collisions")),
                        int(lap_dict.get("Car collisions")),
                        lap_dict.get("Pit Time"),
                        lap_dict.get("Pit Lane Time"),
                        int(float(lap_dict.get("Grip level"))),
                        float(lap_dict.get("Maximum Speed")),
                        lap_dict.get("Achieved on"),
                    ))

    finally:
        browser.get(url)


def getCar(item):
    try:
        return item.find_element(By.TAG_NAME, "img").get_property("title") + " " + item.text
    except NoSuchElementException:
        return item.text


main()
