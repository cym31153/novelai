import time
import random
from typing import Type
from argparse import Namespace

import asyncio
from asyncer import asyncify
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import NoSuchElementException, TimeoutException, NoAlertPresentException

from .access.bce import recognize_audio
from .access.colab import NOTEBOOK_URL, run_colab
from .access.cpolar import get_cpolar_authtoken, get_cpolar_url
from .access.naifu import txt2img
from .config import plugin_config
from .utils import chrome_driver as driver, wait_and_click_element


# ———————————————————— interval jobs ———————————————————— #
@asyncify
def handle_recaptcha() -> None:
    # listen to recaptcha frame
    try:
        driver.switch_to.frame(driver.find_element(By.XPATH, '/html/body/colab-recaptcha-dialog/div/div/iframe'))
    except NoSuchElementException:
        return

    # click recaptcha checkbox
    checkbox = WebDriverWait(driver, 3).until(ec.element_to_be_clickable(
        (By.CSS_SELECTOR, "div.recaptcha-checkbox-checkmark")
    ))
    driver.execute_script("arguments[0].click();", checkbox)
    driver.switch_to.default_content()

    # click "audio auth" button
    try:
        driver.switch_to.frame(driver.find_element(
            By.XPATH, '//iframe[contains(@src,"https://www.google.com/recaptcha/api2/bframe")]'
        ))
    except NoSuchElementException:
        logger.success("Colab ReCaptcha passed!")
        return
    wait_and_click_element(
        driver,
        by=By.CSS_SELECTOR, value='button#recaptcha-audio-button'
    )

    # analyze audio
    while True:
        # get audio link
        try:
            recap_audio_link = WebDriverWait(driver, 3).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="rc-audio"]/div[7]/a'
                )
            ).get_attribute("href")
        # if blocked by Google
        except TimeoutException:
            # refresh page
            driver.get(NOTEBOOK_URL)
            try:
                driver.switch_to.alert.accept()
            except NoAlertPresentException:
                pass

            logger.error("获取Colab ReCaptcha语音时被拦截！")
            return

        answer = recognize_audio(url=recap_audio_link)
        # input answer
        answer_box = wait_and_click_element(
            driver,
            by=By.XPATH, value='//*[@id="audio-response"]'
        )
        answer_box.send_keys(answer, Keys.ENTER)

        try:
            # if answer is wrong
            WebDriverWait(driver, 3).until(ec.visibility_of_element_located(
                (By.XPATH, '//div[@class="rc-audiochallenge-error-message"]')
            ))
            # refresh audio
            wait_and_click_element(
                driver,
                by=By.XPATH, value='//*[@id="recaptcha-reload-button"]'
            )
            logger.warning("Colab ReCaptcha音频验证答案错误！")
        # answer is correct
        except TimeoutException:
            logger.success("Colab ReCaptcha passed!")
            break

    driver.switch_to.default_content()


async def access_colab_with_accounts() -> None:
    cpolar_authtoken = await get_cpolar_authtoken()

    # iter Google accounts
    for gmail, password in plugin_config.google_accounts.items():
        try:
            await run_colab(gmail, password, cpolar_authtoken)
        except RuntimeError as e:
            logger.error(e)
            logger.info("尝试切换Google账号中...")
            continue

        # wait 10min until application startup complete
        start = time.time()
        while time.time() - start < 600:
            try:
                await get_cpolar_url()
                break
            except RuntimeError:
                logger.info(f"等待APP启动中... ({round(time.time() - start, 1)}s/600s)")
                await asyncio.sleep(5)
        if time.time() - start >= 600:
            logger.error("Colab未成功启动，可能是因为ReCaptcha验证失败！")
            logger.info("尝试切换Google账号中...")
            continue

        logger.success("成功连接至APP！")
        while True:
            await asyncio.sleep(30)

            try:
                await get_cpolar_url()
                logger.info("当前账号的Colab在线中...")
            except RuntimeError:
                logger.warning("当前Colab账号已掉线！")
                logger.info("尝试切换Google账号中...")
                break


# ———————————————————— user interactions ———————————————————— #
async def naifu_txt2img(matcher: Type[Matcher], event: MessageEvent, args: Namespace) -> None:
    # check the arguments
    try:
        assert args.size in [
            "384x640", "512x768", "512x1024",  # Portrait
            "640x384", "768x512", "1024x512",  # Landscape
            "512x512", "640x640", "1024x1024"  # Square
        ], "暂不支持输入的图片大小！"
        assert 1 <= args.num <= plugin_config.naifu_max, "图片数量超过上限！"
        assert -1 <= args.seed <= 2**32 - 1, "设置的种子需要在-1与2^32-1之间！"
    except AssertionError as e:
        await matcher.finish(str(e), at_sender=True)

    # get the images
    try:
        await matcher.send("少女作画中...", at_sender=True)
        images = await txt2img(
            prompt=' '.join(args.prompt).replace('，', ','),
            width=int(args.size.split('x')[0]),
            height=int(args.size.split('x')[1]),
            n_samples=args.num,
            seed=random.randint(0, 2**32 - 1) if args.seed == -1 else args.seed
        )
        image_segment = MessageSegment.at(event.get_user_id())
        for image in images:
            image_segment += MessageSegment.image(image)
        await matcher.finish(image_segment)
    except RuntimeError as e:
        await matcher.finish(str(e), at_sender=True)


# Upcoming!
async def naifu_img2img(matcher: Type[Matcher], event: MessageEvent, args: Namespace) -> None:
    pass
