from time import sleep
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = "https://stracker.sdrive.club/sessionstat"

def main():
    options = webdriver.ChromeOptions()
    options.binary_location = '/usr/bin/brave-browser'
    options.page_load_strategy = 'eager'

    browser = webdriver.Chrome(options=options)

    browser.get(URL)
    pagination = (WebDriverWait(browser, 10)
                  .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".pagination > li"))))

    page_last = int(pagination[-3].text)

    for page_current in range(0, page_last-1):
        sessionsPage(browser)

        browser.get(URL + '?page=' + str(page_current+1))
        pagination = (WebDriverWait(browser, 10)
                      .until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".pagination > li"))))

        page_last = int(pagination[-3].text)


def sessionsPage(browser):
    sessions = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, 'tbody')))
    sessions_len = len(sessions)

    for i in range(0, sessions_len):
        break
        # sessionPage(browser)

    print("Program has finished")


#def sessionPage(browser):



main()
