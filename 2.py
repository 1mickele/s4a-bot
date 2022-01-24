from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions

# use context manager
driver = webdriver.Firefox()
driver.get("https://gosafety.web.app/")

WebDriverWait(driver, 30).until(
    expected_conditions.presence_of_element_located(
        (By.ID, 'uid'),
    ))

driver.switch_to.frame(0)
driver.find_element(By.CLASS_NAME, 'search_input').send_keys('username')
driver.find_element(By.CLASS_NAME, 'search_input2').send_keys('password')
driver.find_element(By.CLASS_NAME, 'button_full').click()

def wait_toclick(pid, eid):
    WebDriverWait(driver, 30).until(
        expected_conditions.presence_of_element_located(
            (By.ID, pid),
        ))
    driver.find_element(By.ID, eid).click()

def wait_toclickm(pid, eid, key):
    WebDriverWait(driver, 30).until(
        expected_conditions.presence_of_element_located(
            (By.ID, pid),
        ))
    sls = driver.find_elements(By.ID, eid)
    return next(s for s in sls if key(s))

res = (
    ('SLOT 08.00 - 11.00', 'Edificio A SPAZIO STUDIO 1 piano terra ala sx'),
    ('SLOT 11.00 - 14.00', 'Edificio A SPAZIO STUDIO 1 piano terra ala sx'),
    ('SLOT 14.00 - 17.00', 'Edificio A SPAZIO STUDIO 1 piano terra ala sx'),
    ('SLOT 17.00 - 20.00', 'Edificio A SPAZIO STUDIO 1 piano terra ala sx'),
    ('SLOT 20.00 - 24.00', 'Edificio A SPAZIO STUDIO 1 piano terra ala sx'),
)

input()

for (slot, where) in res:
    try:
        wait_toclick('HOME', 'AULE')
        r = wait_toclickm('BODY', 'SLOT', lambda e : slot in e.text)
        r.click()
        wait_toclick('EDIFICIO', 'EDIFICIO')
        r = wait_toclickm('AULE_STUDIO_C', 'SLOT', lambda e : where in e.text)
        r.click()
        wait_toclick('PRENOTA', 'PRENOTA')
        wait_toclick('PRENOTAZIONE_OK', 'PRENOTA')
        print(f"succeeded {slot}")
    except:
        try:
            print(f"failed {slot}")
            driver.find_element(By.ID, "HOME").click()
        except:
            driver.find_element(By.ID, "BACK").click()
input()
driver.close()
