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
GAME_REGION = {'left': 660, 'top': 518, 'width': 603, 'height': 64}


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


# 4. NASTAVENÍ PRO DYNAMICKÉ ČASOVÁNÍ
#    Tato nastavení řídí novou logiku, která měří rychlost kostky
#    a podle toho předvídá, kdy stisknout mezerník.
# ==============================================================================

#    SPUŠTĚNÍ AKCE (TRIGGER)
#    Kolik sloupců PŘED cílovým sloupcem má bot začít s výpočtem.
#    Pokud je cíl sloupec 8 a TRIGGER_COLUMN_OFFSET = 2, bot se "aktivuje",
#    když kostka dorazí do sloupce 6 (při pohybu zleva doprava).
#    Větší hodnota dává botovi více času na výpočet, ale vyžaduje
#    stabilnější rychlost kostky.
#    Doporučená hodnota: 1 nebo 2.
TRIGGER_COLUMN_OFFSET = 2


#    DÁVKA VSTUPŮ (INPUT BURST)
#    Abychom měli jistotu, že náš stisk hra zaregistruje, pošleme jich
#    několik ve velmi rychlém sledu. Tím pokryjeme případné malé
#    nepřesnosti v časování nebo zpoždění ve hře.

#    Počet stisků v jedné dávce.
#    Doporučená hodnota: 3 až 5.
INPUT_BURST_COUNT = 3

#    Prodleva mezi jednotlivými stisky v dávce (v milisekundách).
#    Cílem je trefit herní okno pro vstup, které je často velmi krátké.
#    Doporučená hodnota: 5 až 10 ms.
INPUT_BURST_DELAY_MS = 7

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
    Pokud kostku nenajde, vrátí None.
    """
    try:
        img = sct_instance.grab(GAME_REGION)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

        lower_bound = np.maximum(0, BLOCK_COLOR_BGR - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, BLOCK_COLOR_BGR + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        if area < 50:
            return None

        M = cv2.moments(largest_contour)
        if M["m00"] == 0:
            return None

        center_x = int(M["m10"] / M["m00"])
        column_index = int(center_x / COLUMN_WIDTH)

        return column_index

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
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

    # --- Stavové proměnné bota ---
    # Tři hlavní stavy:
    # 'AWAITING_CYCLE': Čeká, až kostka dorazí na startovní pozici (sloupec 0).
    # 'MEASURING': Sleduje pohyb kostky, aby změřila její rychlost.
    # 'ARMED': Rychlost je změřena, bot je připraven k akci.
    state = 'AWAITING_CYCLE'

    last_column = -1
    direction = 1
    dwell_time_s = None  # Průměrný čas, který kostka stráví v jednom sloupci
    column_timestamps = {} # Záznamy časů pro měření rychlosti

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):
            current_column = find_block_column(sct)
            if current_column is None:
                continue

            # Detekce změny sloupce je klíčová pro veškerou logiku
            if current_column != last_column:
                detection_time = time.perf_counter()

                # Aktualizace směru pohybu
                if last_column != -1:
                    new_direction = 1 if current_column > last_column else -1
                    if new_direction != direction:
                        print(f"Změna směru: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                print(f"Stav: {state}, Sloupec: {current_column}")

                # --- STAV: ČEKÁNÍ NA NOVÝ CYKLUS ---
                if state == 'AWAITING_CYCLE':
                    if current_column == 0:
                        print("Detekován začátek cyklu (sloupec 0). Zahajuji měření rychlosti.")
                        state = 'MEASURING'
                        column_timestamps = {0: detection_time}

                # --- STAV: MĚŘENÍ RYCHLOSTI ---
                elif state == 'MEASURING':
                    column_timestamps[current_column] = detection_time

                    # Vypočítáme rychlost z několika po sobě jdoucích skoků
                    if len(column_timestamps) > 3:
                        # Seřadíme sloupce a časy, abychom mohli počítat rozdíly
                        sorted_cols = sorted(column_timestamps.keys())
                        time_diffs = [column_timestamps[sorted_cols[i]] - column_timestamps[sorted_cols[i-1]] for i in range(1, len(sorted_cols))]

                        # Odstraníme případné odlehlé hodnoty (např. při změně směru)
                        stable_diffs = [d for d in time_diffs if d > 0.01]
                        if not stable_diffs:
                            continue

                        dwell_time_s = np.mean(stable_diffs)
                        print(f"Změřena rychlost: {dwell_time_s * 1000:.2f} ms na sloupec.")
                        print("Bot je nyní aktivován a připraven k akci (ARMED).")
                        state = 'ARMED'

                # --- STAV: PŘIPRAVEN K AKCI ---
                elif state == 'ARMED':
                    trigger_column = TARGET_COLUMN - (TRIGGER_COLUMN_OFFSET * direction)

                    if current_column == trigger_column:
                        columns_to_go = abs(TARGET_COLUMN - current_column)
                        time_to_target_s = columns_to_go * dwell_time_s

                        # VÝPOČET ČASU DOPADU:
                        # Náš `detection_time` je čas, kdy kostka *vstoupila* do `trigger_column`.
                        # `time_to_target_s` je doba, za kterou dorazí ke *vstupu* do `TARGET_COLUMN`.
                        # Chceme však stisknout uprostřed doby, kdy je v cílovém sloupci,
                        # proto přičteme polovinu změřeného času na sloupec (`dwell_time_s`).
                        time_to_target_center_s = time_to_target_s + (dwell_time_s / 2.0)
                        predicted_arrival_time = detection_time + time_to_target_center_s

                        print(f"Kostka v trigger sloupci {current_column}. Cíl: {TARGET_COLUMN}")
                        print(f"Predikovaný čas dopadu za: {(predicted_arrival_time - time.perf_counter()) * 1000:.1f} ms")

                        # Přesné čekání na vypočítaný čas
                        wait_time = predicted_arrival_time - time.perf_counter()
                        if wait_time > 0:
                            time.sleep(wait_time)

                        # --- DÁVKA VSTUPŮ (INPUT BURST) ---
                        print(f"==> MEZERNÍK! (Dávka {INPUT_BURST_COUNT} stisků)")
                        for i in range(INPUT_BURST_COUNT):
                            pyautogui.press('space')
                            # Krátká pauza mezi stisky v dávce
                            time.sleep(INPUT_BURST_DELAY_MS / 1000.0)

                        # Po akci se bot resetuje a čeká na další cyklus
                        print("-" * 20)
                        print("Akce provedena. Čekám na další cyklus od sloupce 0.")
                        state = 'AWAITING_CYCLE'
                        dwell_time_s = None
                        column_timestamps = {}
                        # Krátká pauza, abychom znovu nedetekovali stejnou kostku
                        time.sleep(0.3)

                last_column = current_column

        print("\nKlávesa 'q' stisknuta, bot se ukončuje.")

if __name__ == "__main__":
    print("Vítejte v botovi pro skládání věže!")
    print("Před spuštěním prosím nastavte hodnoty v sekci 'NASTAVENÍ BOTA'.")
    print("\nPotřebné knihovny: pip install numpy opencv-python pyautogui keyboard mss")

    # Zeptáme se uživatele, zda chce spustit bota
    run_bot = input("Chcete spustit bota nyní? (ano/ne): ")
    if run_bot.lower() in ['a', 'ano', 'y', 'yes']:
        main()
    else:
        print("Bot nebyl spuštěn. Upravte nastavení a zkuste to znovu.")