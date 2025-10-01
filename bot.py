# Tento skript je bot pro hru, kde stavíte věž z kostek.
# Bot dynamicky měří rychlost pohybující se kostky a na základě toho
# přesně předvídá, kdy stisknout mezerník pro umístění kostky.

# --- Potřebné knihovny ---
# Ujistěte se, že máte nainstalované všechny potřebné knihovny.
# Otevřete terminál (příkazový řádek) a spusťte:
# pip install numpy opencv-python pyautogui keyboard mss

import time
import keyboard
import numpy as np
import cv2
import mss
import pyautogui

# ==============================================================================
# --- NASTAVENÍ BOTA ---
# Tuto část musíte upravit podle vaší hry a obrazovky.
# ==============================================================================

# 1. OBLAST HRY (GAME_REGION)
#    Toto je nejdůležitější nastavení. Musíte botovi říct, kde na obrazovce
#    se hra nachází. Je to obdélník definovaný:
#    - 'left': počet pixelů od levého okraje obrazovky
#    - 'top': počet pixelů od horního okraje obrazovky
#    - 'width': šířka herní oblasti v pixelech
#    - 'height': výška herní oblasti v pixelech
#
#    JAK ZJISTIT HODNOTY?
#    Spusťte si Python v terminálu a napište:
#    >>> import pyautogui
#    >>> pyautogui.displayMousePosition()
#    Poté hýbejte myší a terminál vám bude ukazovat její souřadnice (X, Y).
#    - Najeďte myší na LEVÝ HORNÍ roh herní plochy a zapište si X a Y.
#      To jsou vaše hodnoty 'left' a 'top'.
#    - Najeďte myší na PRAVÝ DOLNÍ roh a zapište si X a Y.
#    - 'width' = (pravý dolní X) - (levý horní X)
#    - 'height' = (pravý dolní Y) - (levý horní Y)
#
# Příklad:
# Toto je základní nastavení pro Level 1.
GAME_REGION = {'left': 880, 'top': 675, 'width': 795, 'height': 75}


# 2. BARVA KOSTKY (BLOCK_COLOR_RGB)
#    Zadejte barvu kostky, kterou má bot hledat.
#    Hodnoty jsou v RGB formátu (červená, zelená, modrá).
#    Tvůj příklad byl RGB (236, 168, 44).
BLOCK_COLOR_RGB = (236, 168, 44)

#    Jak moc se může skutečná barva lišit od zadané.
#    Větší číslo znamená větší toleranci (např. pro různé odstíny).
COLOR_TOLERANCE = 25


# 3. HERNÍ PARAMETRY
#    Počet sloupců, mezi kterými kostka přeskakuje.
NUM_COLUMNS = 10

#    CÍLOVÝ SLOUPEC (TARGET_COLUMN)
#    Do kterého sloupce má bot mířit? Čísluje se od 0.
#    Pokud máte 10 sloupců (0 až 9), sloupec 4 je pátý zleva.
#    Toto je nejdůležitější hodnota pro míření.
TARGET_COLUMN = 8


# 4. POKROČILÉ NASTAVENÍ PRO ČASOVÁNÍ
#    Tato nastavení řídí logiku, která dynamicky měří rychlost kostky
#    a podle toho předvídá, kdy stisknout mezerník.
# ==============================================================================

#    PŘEDVÍDÁNÍ (PREDICTION_OFFSET)
#    Kolik sloupců PŘED cílovým sloupcem má bot reagovat.
#    Pokud je cíl sloupec 8 a PREDICTION_OFFSET = 1, bot stiskne mezerník,
#    když je kostka ve sloupci 7. To kompenzuje zpoždění.
#    Doporučená hodnota: 1 nebo 2.
PREDICTION_OFFSET = 1

#    ZPOŽDĚNÍ STISKU (PRESS_DELAY_MS_AFTER_JUMP)
#    Kolik milisekund má bot počkat po PŘEDPOVĚZENÉM skoku do cílového
#    sloupce, než stiskne mezerník. Cílem je trefit začátek
#    okna pro vstup.
#    Doporučená hodnota: 5-15 ms.
PRESS_DELAY_MS_AFTER_JUMP = 10

#    DÁVKA VSTUPŮ (INPUT BURST)
#    Abychom měli jistotu, že náš stisk hra zaregistruje, pošleme jich
#    několik ve velmi rychlém sledu.
#    Počet stisků v jedné dávce. Doporučená hodnota: 3 až 5.
INPUT_BURST_COUNT = 3
#    Prodleva mezi jednotlivými stisky v dávce (v milisekundách). Doporučená hodnota: 5 až 10.
INPUT_BURST_DELAY_MS = 7


# 5. DEBUG OKNO
#    Pokud nastavíte na True, zobrazí se okno, které v reálném čase ukazuje,
#    co bot "vidí". Užitečné pro ladění a kontrolu, zda správně
#    detekuje herní oblast a kostku.
SHOW_DEBUG_WINDOW = True

# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Převedení barvy z RGB na BGR (formát, který používá OpenCV)
BLOCK_COLOR_BGR = np.array(BLOCK_COLOR_RGB[::-1])
COLUMN_WIDTH = GAME_REGION['width'] / NUM_COLUMNS

def find_block_column(sct_instance):
    """
    Snímá herní obrazovku, najde kostku a vrátí index jejího sloupce (0-9).
    Pokud je zapnuté debug okno, vizualizuje detekci.
    Pokud kostku nenajde, vrátí None.
    """
    try:
        img = sct_instance.grab(GAME_REGION)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

        # Vytvoření masky pro detekci barvy
        lower_bound = np.maximum(0, BLOCK_COLOR_BGR - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, BLOCK_COLOR_BGR + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        column_index = None
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)

            if area >= 50:  # Minimální plocha pro detekci kostky
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    column_index = int(center_x / COLUMN_WIDTH)

                    # Vykreslení do debug okna, pokud je aktivní
                    if SHOW_DEBUG_WINDOW:
                        cv2.drawContours(frame, [largest_contour], -1, (0, 255, 0), 2)
                        center_y = int(M["m01"] / M["m00"])
                        cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

        # Zobrazení debug okna, pokud je aktivní
        if SHOW_DEBUG_WINDOW:
            cv2.imshow("Bot Vision - Debug", frame)
            # Nutné pro obnovení okna, čeká 1 ms
            cv2.waitKey(1)

        return column_index

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        # Při chybě zavřeme okno, aby nezůstalo viset
        if SHOW_DEBUG_WINDOW:
            cv2.destroyAllWindows()
        return None

def main():
    """
    Hlavní smyčka bota s dynamickým měřením rychlosti a prediktivním časováním.
    """
    print("="*50)
    print("Bot s dynamickým časováním se spouští za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    last_column = -1
    direction = 1
    action_taken = False

    # Proměnné pro dynamické měření rychlosti
    dwell_time_s = None      # Změřený čas na jeden sloupec
    column_timestamps = {}   # Záznamy časů pro měření
    is_calibrated = False    # Zda již máme změřenou rychlost

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):
            current_column = find_block_column(sct)

            # Pokud kostka zmizí (po úspěšné akci), resetujeme stav
            if current_column is None:
                if action_taken:
                    print("-" * 20)
                    print("Akce dokončena. Resetuji pro další kostku.")
                    action_taken = False
                    last_column = -1
                    # Vynulujeme kalibraci, aby se rychlost změřila znovu
                    is_calibrated = False
                    column_timestamps = {}
                    dwell_time_s = None
                continue

            # --- Logika se spouští pouze při změně sloupce ---
            if current_column != last_column:
                detection_time = time.perf_counter()

                # Aktualizace směru pohybu
                if last_column != -1:
                    new_direction = 1 if current_column > last_column else -1
                    if direction != new_direction:
                        direction = new_direction
                        print(f"Změna směru: {'doprava' if direction == 1 else 'doleva'}")
                        # Při změně směru je nejlepší resetovat měření
                        column_timestamps = {}
                        is_calibrated = False

                # --- Měření rychlosti ---
                # Začneme znovu měřit, pokud se vrátíme na začátek
                if current_column == 0:
                    column_timestamps = {}
                    is_calibrated = False

                column_timestamps[current_column] = detection_time

                # Pro měření potřebujeme alespoň pár záznamů
                if not is_calibrated and len(column_timestamps) > 2:
                    sorted_cols = sorted(column_timestamps.keys())
                    time_diffs = [column_timestamps[sorted_cols[i]] - column_timestamps[sorted_cols[i-1]] for i in range(1, len(sorted_cols))]

                    # Odfiltrujeme odlehlé hodnoty (např. po změně směru)
                    stable_diffs = [d for d in time_diffs if 0.001 < d < 1.0] # 1ms - 1s
                    if len(stable_diffs) > 1:
                        dwell_time_s = np.mean(stable_diffs)
                        is_calibrated = True
                        print(f"Bot je zkalibrován. Rychlost: {dwell_time_s * 1000:.2f} ms/sloupec.")

                # --- Predikce a Akce ---
                # Akci provedeme pouze pokud máme změřenou rychlost a ještě jsme nejednali
                if is_calibrated and not action_taken:
                    prediction_trigger_column = TARGET_COLUMN - (PREDICTION_OFFSET * direction)

                    if current_column == prediction_trigger_column:
                        # Vypočítáme čas do dopadu na cílový sloupec
                        jumps_to_go = PREDICTION_OFFSET
                        time_to_target_s = jumps_to_go * dwell_time_s

                        predicted_target_jump_time = detection_time + time_to_target_s

                        # Přidáme uživatelské zpoždění pro finální časování
                        press_delay_s = PRESS_DELAY_MS_AFTER_JUMP / 1000.0
                        target_press_time = predicted_target_jump_time + press_delay_s

                        print(f"Kostka v trigger sloupci {current_column}. Cíl: {TARGET_COLUMN}")
                        print(f"Predikovaný čas stisku za: {((target_press_time - time.perf_counter()) * 1000):.1f} ms")

                        # Přesné čekání na stisk
                        wait_time = target_press_time - time.perf_counter()
                        if wait_time > 0:
                            time.sleep(wait_time)

                        # --- DÁVKA VSTUPŮ (INPUT BURST) ---
                        print(f"==> MEZERNÍK! (Dávka {INPUT_BURST_COUNT} stisků)")
                        for i in range(INPUT_BURST_COUNT):
                            pyautogui.press('space')
                            time.sleep(INPUT_BURST_DELAY_MS / 1000.0)

                        action_taken = True
                        # Krátká pauza, aby se zabránilo opětovné detekci
                        time.sleep(0.2)

                last_column = current_column

    print("\nKlávesa 'q' stisknuta, bot se ukončuje.")
    # Zavřeme debug okno, pokud bylo otevřené
    if SHOW_DEBUG_WINDOW:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    print("Vítejte v botovi pro skládání věže!")
    print("Před spuštěním prosím nastavte hodnoty v sekci 'NASTAVENÍ BOTA'.")

    # --- Výběr Levelu ---
    level = 0
    while True:
        try:
            level_input = input("Zadejte level, který chcete hrát (1-10): ")
            level = int(level_input)
            if 1 <= level <= 10:
                break
            else:
                print("Chyba: Zadejte prosím číslo od 1 do 10.")
        except ValueError:
            print("Chyba: Zadejte prosím platné číslo.")

    # Dynamický výpočet herní oblasti na základě zvoleného levelu.
    # Level 1 a 2 mají specifické 'top' souřadnice.
    # Pro levely 3 a vyšší se 'top' souřadnice snižuje o 100px pro každý
    # další level, vycházeje z hodnoty pro level 2.
    if level == 1:
        GAME_REGION['top'] = 675  # Specifická hodnota pro Level 1
    elif level == 2:
        GAME_REGION['top'] = 1020 # Specifická hodnota pro Level 2
    else: # Pro level > 2
        GAME_REGION['top'] = 1020 - (100 * (level - 2))


    print(f"Úspěšně nastaven level {level}.")
    print(f"Herní oblast pro tento level: {GAME_REGION}")


    # Zeptáme se uživatele, zda chce spustit bota
    run_bot = input("Chcete spustit bota nyní? (ano/ne): ")
    if run_bot.lower() in ['a', 'ano', 'y', 'yes']:
        main()
    else:
        print("Bot nebyl spuštěn. Upravte nastavení a zkuste to znovu.")