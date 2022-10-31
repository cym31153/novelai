import time

from asyncer import asyncify

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoAlertPresentException

from ..utils import chrome_driver as driver, wait_and_click_element, PLUGIN_DIR

NOTEBOOK_URL = "https://colab.research.google.com/drive/1oAMaO-0_SxFSr8OEC1jJVkC84pGFzw-I?usp=sharing"


def login_google_acc(gmail: str, password: str) -> None:
    try:
        # No account logged in yet
        try:
            # click "Sign in"
            login = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(By.XPATH, '//*[@id="gb"]/div/div/a')
            )
            driver.get(login.get_attribute('href'))

        # Already logged in
        except TimeoutException:
            # logout current account
            logout = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="gb"]/div/div[1]/div[2]/div/a'
                )
            )
            driver.get(logout.get_attribute('href'))
            driver.find_element(By.XPATH, '//*[@id="signout"]').click()

            # click "Sign in"
            login = driver.find_element(By.XPATH, '//*[@id="gb"]/div/div/a')
            driver.get(login.get_attribute('href'))

            # choose "Use another account" when login
            use_another_acc = driver.find_element(
                By.XPATH,
                '//*[@id="view_container"]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div/div/ul'
                '/li[@class="JDAKTe eARute W7Aapd zpCp3 SmR8" and not(@jsname="fKeql")]'
            )
            use_another_acc.click()

        # input gmail and password
        gmail_input = wait_and_click_element(driver, by=By.XPATH, value='//*[@id="identifierId"]')
        gmail_input.send_keys(gmail, Keys.ENTER)

        pwd_input = wait_and_click_element(driver, by=By.XPATH, value='//*[@id="password"]/div[1]/div/div[1]/input')
        pwd_input.send_keys(password, Keys.ENTER)

        # check if the password is incorrect
        try:
            WebDriverWait(driver, 3).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div[2]/div/div[1]/div/form/span/div[1]/div[2]/div[1]'
                )
            )
            raise RuntimeError("Google账号的密码填写有误！")
        except TimeoutException:
            pass

    except TimeoutException:
        raise RuntimeError("登陆Google账号发生超时，请检查网络，账号可用性和账密！")

    # In case of Google asking you to complete your account info
    try:
        # Wait for "not now" button occurs
        wait_and_click_element(
            driver,
            by=By.XPATH, value='//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[4]/div[1]/button'
        )

    # If that doesn't happen
    except TimeoutException:
        pass


@asyncify
def run_colab(gmail: str, password: str, cpolar_authtoken: str) -> None:
    driver.get(NOTEBOOK_URL)
    # handle webpage refresh alert
    try:
        driver.switch_to.alert.accept()
    except NoAlertPresentException:
        pass

    login_google_acc(gmail, password)

    # input cpolar authtoken
    time.sleep(3)
    authtoken_box = driver.execute_script(
        'return document.querySelector("#cell-54WF-Om0X6tf > div.main-content > div.codecell-input-output > '
        'div.inputarea.horizontal.layout.both > colab-form > div > colab-form-input > div.layout.horizontal.grow > '
        'paper-input").shadowRoot.querySelector("#input-1 > input")'
    )
    authtoken_box.clear()
    authtoken_box.send_keys(cpolar_authtoken)

    # run all cells
    driver.find_element(By.XPATH, '/html/body').send_keys(Keys.CONTROL + Keys.F9)

    # If Google asks you to confirm running this notebook
    try:
        wait_and_click_element(
            driver,
            by=By.XPATH, value='/html/body/colab-dialog/paper-dialog/div[2]/paper-button[2]'
        )
    except TimeoutException:
        pass

    # keep webpage active
    with open(PLUGIN_DIR / "js" / "keepPageActive.js", 'r', encoding='utf-8') as js:
        driver.execute_script(js.read())